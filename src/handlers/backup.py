import asyncio
import os
import shutil
import signal
import tempfile
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from sanic.log import logger, Colors

from src.handlers.config import ConfigHandler
from src.cloud_services.base import get_cloud_service

class BackupHandler:
    # Hard ceiling for a full map render (all dimensions in parallel).
    # Guarantees the save hold is never stuck forever if unmined freezes.
    MAP_RENDER_TIMEOUT_SECONDS = 60 * 60
    # Append-only render log on the persisted /server volume (survives
    # container takedowns; never truncated or rotated) — keeps the noisy
    # unmined output off the main log stream.
    MAP_RENDER_LOG_FILE = Path('../server/logs/map-render.log')
    def __init__(self, file_list: tuple, level_name: str):
        self.file_list = file_list
        self.level_name = level_name
        self.server_path = Path('../server/')
        self.world_path = Path('../server/worlds/')
        self.backup_path = Path('../server/backups/')
        self.backup_path.mkdir(parents=True, exist_ok=True)

        self.config = ConfigHandler()
        self.bucket_name = self.config['backup']['bucket_name']

        self.cloud_service = get_cloud_service()

        self.backup_date = datetime.now()

    def __copy_files_to_dir(self, dst: Path) -> Path:
        """
        Copies files to the specified destination directory.
        The copied files will also be truncated to the specified length by the Bedrock Server.

        :param dst: The destination directory path.
        :return: The path to the copied level directory
        """
        for file_name, file_length in self.file_list:
            file_path = self.world_path / Path(file_name)

            target = dst / file_path.relative_to(self.server_path)
            target.parent.mkdir(parents=True, exist_ok=True)

            if file_path.exists():
                shutil.copyfile(file_path, target)

                with open(target, 'a') as f:
                    f.truncate(int(file_length))

        return dst / 'worlds' / self.level_name

    def __copy_extra_files(self, dst: Path):
        extra_files = []

        if self.config['backup']['include_addons']:
            extra_files = extra_files + [x for x in self.world_path.glob('**/*_packs*')]

        if self.config['backup']['include_server_files']:
            server_files = [
                self.server_path / Path('server.properties'),
                self.server_path / Path('allowlist.json'),
                self.server_path / Path('permissions.json'),
                self.server_path / Path('config/default/permissions.json'),
                self.server_path / Path('config/default/variables.json'),
                self.server_path / Path('config/default/secrets.json'),
            ]

            extra_files = extra_files + server_files

        for extra_file in extra_files:
            target = dst / extra_file.relative_to(self.server_path)

            if extra_file.exists() and extra_file.is_dir():
                shutil.copytree(extra_file, target)
            elif extra_file.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(extra_file, target)

    def __zip_files(self, src: Path) -> Path:
        file_date = self.backup_date.strftime("%Y-%m-%d_%H-%M-%S")
        destination = src / Path(f'{self.level_name}_{file_date}.zip')

        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in src.glob('**/*'):
                if file_path.suffix != '.zip':
                    zip_file.write(file_path, file_path.relative_to(src))

        return destination

    def __upload_to_cloud(self, src: Path, file_path: Path):
        backup_type = self._determine_backup_type()
        destination_file_path = self._build_destination_path(backup_type, src, file_path)
        
        logger.info(f'Uploading {file_path} to {destination_file_path}')
        self.cloud_service.upload_backup(self.bucket_name, file_path, destination_file_path)
        logger.info(f'{Colors.GREEN}Backup uploaded successfully!{Colors.END}')

    def _determine_backup_type(self) -> str:
        """
        Determines the appropriate backup type based on current time and configuration.
        
        Returns:
            str: The backup subdirectory name to use
        """
        now = datetime.now()
        
        monthly_config = self.config['backup']['monthly_backups']
        daily_config = self.config['backup']['daily_backups']
        
        # Check for monthly backup (highest priority)
        if (monthly_config['enabled'] and 
            monthly_config['day'] == now.day and 
            now.hour == 0):
            return monthly_config['cloud_subdirectory']
        
        # Check for daily backup (medium priority)
        if (daily_config['enabled'] and 
            daily_config['hour'] == now.hour):
            return daily_config['cloud_subdirectory']
        
        # Default to hourly backup (lowest priority)
        return self.config['backup']['hourly_backups']['cloud_subdirectory']

    def _build_destination_path(self, backup_type: str, src: Path, file_path: Path) -> str:
        """
        Builds the destination path for the backup file.
        
        Args:
            backup_type: The backup subdirectory type
            src: The source directory path
            file_path: The file being backed up
        
        Returns:
            str: The complete destination path
        """
        relative_path = file_path.relative_to(src)
        
        if self.cloud_service.service == "local":
            return f'{self.backup_path}/{backup_type}/{relative_path}'
        
        return f'{backup_type}/{relative_path}'

    @staticmethod
    async def _stream_process_output(proc: asyncio.subprocess.Process, name: str, sink):
        """Drain unmined stdout/stderr line-by-line into the render log file.

        Must run concurrently with wait(): otherwise the OS pipe buffer
        fills up, the child blocks on write, and wait() never returns
        (the "map update freezes" hang). Lines go to `sink` (the dedicated
        render log file), NOT the main log stream.
        """
        try:
            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                try:
                    text = line.decode(errors='replace').rstrip()
                except Exception:
                    text = repr(line)
                if text:
                    try:
                        await sink(f'[{name}] {text}')
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        logger.warning(f'[Map][{name}] render-log write failed: {e.__class__.__name__}: {e}')
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f'[Map][{name}] output streaming failed: {e.__class__.__name__}: {e}')

    @staticmethod
    async def _terminate_process(proc: asyncio.subprocess.Process, name: str):
        """Best-effort terminate -> kill a hung unmined process tree.

        Renders are spawned with start_new_session=True, so killpg takes
        down the shell wrapper AND the unmined child (plain terminate()
        would only kill the shell and orphan unmined-cli).
        """
        try:
            if proc.returncode is not None:
                return
            logger.warning(f'[Map][{name}] terminating hung render (pid={proc.pid})...')
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=30)
                return
            except asyncio.TimeoutError:
                pass
            logger.warning(f'[Map][{name}] did not exit after terminate, killing (pid={proc.pid})...')
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=15)
            except asyncio.TimeoutError:
                logger.error(f'[Map][{name}] process still alive after kill (pid={proc.pid})')
        except ProcessLookupError:
            pass
        except Exception as e:
            logger.warning(f'[Map][{name}] terminate failed: {e.__class__.__name__}: {e}')

    @staticmethod
    async def __run_unmined(world_path: Path, timeout_seconds: float | None = None, log_file: Path | None = None):
        if timeout_seconds is None:
            timeout_seconds = BackupHandler.MAP_RENDER_TIMEOUT_SECONDS
        if log_file is None:
            log_file = BackupHandler.MAP_RENDER_LOG_FILE

        # Append-only render log on the persisted volume: never truncated,
        # so history survives container takedowns. Falls back to the main
        # log stream only if the file can't be opened.
        render_log = None
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            render_log = open(log_file, 'a', encoding='utf-8', buffering=1)
        except Exception as e:
            logger.warning(f'[Map] Could not open render log {log_file}: {e.__class__.__name__}: {e} — falling back to main log')
            render_log = None
        write_lock = asyncio.Lock()

        async def _render_log(line: str):
            entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [Map] {line}"
            if render_log is None:
                logger.info(entry)
                return
            async with write_lock:
                render_log.write(entry + '\n')
                render_log.flush()

        base_cmd = f"../unmined/unmined-cli web render --world='{world_path}'"

        # Make dynamic area based on nexuscore border sizes
        common_params = ' '.join([
            "--imageformat=png",
            "--zoomin=2",
            "--area='b((2111, 2111), (-2112, -2112))'",
            "--log-level=debug",
            "--shadows=3d",
            "--chunkprocessors=1"
        ])

        # Make dynamic parameterization, based on user configurations
        # allow people to pass in their own blockstyles.txt via docker, for custom block palletes
        render_tasks = {
            'overworld': f"{base_cmd} --output='../unmined/overworld' --dimension=overworld --mapsettings='./map/Everthorn.json' {common_params}",
            'nether': f"{base_cmd} --output='../unmined/nether' --dimension=nether --mapsettings='./map/Nether.json' {common_params}",
            'subway': f"{base_cmd} --output='../unmined/subway' --dimension=overworld --mapsettings='./map/Subway.json' {common_params}",
            'the_end': f"{base_cmd} --output='../unmined/the_end' --dimension=end --mapsettings='./map/End.json' {common_params}"
        }

        processes: dict[str, asyncio.subprocess.Process] = {}
        stream_tasks: list[asyncio.Task] = []
        start_time = datetime.now()
        try:
            timeout_mins = timeout_seconds / 60
            await _render_log(f'===== Render started (world={world_path}, timeout={timeout_mins:.0f}m) =====')
            logger.info(f'Starting {len(render_tasks)} Map Renders (timeout={timeout_mins:.0f}m). Detailed log: {log_file}')
            logger.info(f'All Renders: {", ".join(render_tasks.keys())}')

            for name, cmd in render_tasks.items():
                await _render_log(f'[{name}] starting render: {cmd}')
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    # New process group per render so timeout cleanup can
                    # kill the whole tree (shell + unmined child) via killpg.
                    start_new_session=True,
                )
                processes[name] = proc
                await _render_log(f'[{name}] spawned (pid={proc.pid})')
                stream_tasks.append(
                    asyncio.create_task(
                        BackupHandler._stream_process_output(proc, name, _render_log),
                        name=f'map-render-log-{name}',
                    )
                )

            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*[p.wait() for p in processes.values()]),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                elapsed = datetime.now() - start_time
                timeout_msg = (
                    f'Render timed out after {int(elapsed.total_seconds() // 60)}m '
                    f'{int(elapsed.total_seconds() % 60)}s (limit={timeout_mins:.0f}m) — '
                    f'terminating {len(processes)} unmined process(es) to free save hold'
                )
                await _render_log(timeout_msg)
                logger.error(f'{Colors.RED}[Map] {timeout_msg}{Colors.END}')
                await asyncio.gather(
                    *[BackupHandler._terminate_process(p, n) for n, p in processes.items()],
                    return_exceptions=True,
                )
                raise TimeoutError(f'Map render exceeded {timeout_mins:.0f} minute timeout; processes terminated')

            # Ensure all streamed output is drained before reporting
            if stream_tasks:
                await asyncio.gather(*stream_tasks, return_exceptions=True)

            names = list(render_tasks.keys())
            successful = [names[i] for i, result in enumerate(results) if result == 0]
            failed = [(names[i], results[i]) for i in range(len(names)) if results[i] != 0]
            for layer, code in failed:
                await _render_log(f'[{layer}] exited with code {code}')

            duration = datetime.now() - start_time
            minutes = int(duration.total_seconds() // 60)
            seconds = int(duration.total_seconds() % 60)
            summary = f'Render completed in {minutes}m {seconds}s. Completed: {len(successful)}/{len(results)} ({", ".join(successful) if successful else "none"})'
            await _render_log(f'===== {summary} =====')
            logger.info(f'[Map] {summary}')

            if failed:
                failed_msg = f'Incomplete render: {len(successful)}/{len(results)} succeeded; failed layers will be retried next cycle'
                await _render_log(failed_msg)
                logger.error(f'[Map] {failed_msg}')

        except (asyncio.CancelledError, TimeoutError):
            # Always clear tasks + processes so the coordinator lock/hold frees up.
            for t in stream_tasks:
                if not t.done():
                    t.cancel()
            if stream_tasks:
                await asyncio.gather(*stream_tasks, return_exceptions=True)
            await asyncio.gather(
                *[BackupHandler._terminate_process(p, n) for n, p in processes.items()],
                return_exceptions=True,
            )
            raise
        except Exception as e:
            for t in stream_tasks:
                if not t.done():
                    t.cancel()
            if stream_tasks:
                await asyncio.gather(*stream_tasks, return_exceptions=True)
            await asyncio.gather(
                *[BackupHandler._terminate_process(p, n) for n, p in processes.items() if p.returncode is None],
                return_exceptions=True,
            )
            err_msg = f'Map update failed: {e.__class__.__name__} - {str(e)}'
            try:
                await _render_log(err_msg)
            except Exception:
                pass
            logger.error(err_msg)
            raise
        finally:
            if render_log is not None:
                try:
                    render_log.close()
                except Exception:
                    pass

    @staticmethod
    @asynccontextmanager
    async def _temp_work_dir(base: Path):
        """Temp dir whose cleanup can never fail the caller.

        Removing a multi-GB world copy via shutil.rmtree can transiently
        fail (e.g. ENOTEMPTY if a lingering child still touches the tree,
        or flaky overlayfs behavior in Docker). Without this guard, a
        fully successful backup/render would be reported as FAILED and the
        loop would immediately re-run it.
        """
        tmp = tempfile.TemporaryDirectory(dir=base, ignore_cleanup_errors=True)
        try:
            yield Path(tmp.name)
        except Exception:
            # Body raised: the backup/render genuinely failed — attempt
            # cleanup, then let the original error propagate.
            try:
                tmp.cleanup()
            except Exception as e:
                logger.warning(f'Temp work dir cleanup failed after error: {e.__class__.__name__}: {e} ({tmp.name})')
            raise
        else:
            # Body succeeded: cleanup must never fail the result.
            try:
                tmp.cleanup()
            except Exception as e:
                logger.warning(f'Temp work dir cleanup failed (result preserved): {e.__class__.__name__}: {e} ({tmp.name})')
        finally:
            leftover = Path(tmp.name)
            if leftover.exists():
                try:
                    entries = [str(p.relative_to(leftover)) for p in leftover.rglob('*')]
                    logger.warning(
                        f'Temp work dir not fully removed ({len(entries)} leftover entries, '
                        f'e.g. {entries[:10]}); retrying removal in background: {leftover}'
                    )
                except Exception as e:
                    logger.warning(
                        f'Temp work dir not fully removed; retrying removal in background: '
                        f'{leftover} ({e.__class__.__name__}: {e})'
                    )
                try:
                    await asyncio.to_thread(shutil.rmtree, leftover, ignore_errors=True)
                except Exception as e:
                    logger.warning(f'Background removal of temp work dir failed: {e.__class__.__name__}: {e} ({leftover})')

    async def backup(self):
        async with self._temp_work_dir(self.backup_path) as temp_dir_path:
            await asyncio.to_thread(self.__copy_files_to_dir, temp_dir_path)
            await asyncio.to_thread(self.__copy_extra_files, temp_dir_path)
            zip_file_name = await asyncio.to_thread(self.__zip_files, temp_dir_path)
            await asyncio.to_thread(self.__upload_to_cloud, temp_dir_path, zip_file_name)

    async def map_update(self):
        async with self._temp_work_dir(self.backup_path) as temp_dir_path:
            level_path: Path = await asyncio.to_thread(self.__copy_files_to_dir, temp_dir_path)
            await self.__run_unmined('..' / level_path)