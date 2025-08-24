import asyncio
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from sanic.log import logger, Colors

from src.handlers.config import ConfigHandler

class BackupHandler:
    def __init__(self, file_list: tuple, level_name: str):
        self.file_list = file_list
        self.level_name = level_name
        self.server_path = Path('../server/')
        self.world_path = Path('../server/worlds/')
        self.backup_path = Path('../server/backups/')
        self.backup_path.mkdir(parents=True, exist_ok=True)

        self.config = ConfigHandler()
        self.backup_location = self.config['backup']['location']
        self.bucket_name = self.config['backup']['bucket_name']

    def __copy_files_to_dir(self, dst: Path):
        """
        Copies files to the specified destination directory.
        The copied files will also be truncated to the specified length by the Bedrock Server.

        :param dst: The destination directory path.
        """
        for file_name, file_length in self.file_list:
            file_path = self.world_path / Path(file_name)

            target = dst / file_path.relative_to(self.server_path)
            target.parent.mkdir(parents=True, exist_ok=True)

            if file_path.exists():
                shutil.copyfile(file_path, target)

                with open(target, 'a') as f:
                    f.truncate(int(file_length))

        level_path = [x for x in (dst / 'worlds').iterdir()]
        return dst / 'worlds' / level_path[0]

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
                self.server_path / Path('config/default/variables.json')
            ]

            extra_files = extra_files + server_files

        for extra_file in extra_files:
            target = dst / extra_file.relative_to(self.server_path)

            if extra_file.is_dir():
                shutil.copytree(extra_file, target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(extra_file, target)

    def __zip_files(self, src: Path):
        file_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        destination = self.backup_path / Path(f'{self.level_name}_{file_date}.zip')

        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in src.glob('**/*'):
                zip_file.write(file_path, file_path.relative_to(src))

    @staticmethod
    async def __run_unmined(world_path: Path):
        base_cmd = f"../unmined/unmined-cli web render --world='{world_path}'"

        common_params = ' '.join([
            "--imageformat=png",
            "--zoomin=2",
            "--area='b((2111, 2111), (-2112, -2112))'",
            "--log-level=error",
            "--shadows=3d",
            "--chunkprocessors=1"
        ])

        # Make dynamic parameterization, based on user configurations
        # allow people to pass in their own blockstyles.txt via docker, for custom block palletes
        render_tasks = {
            'overworld': f"{base_cmd} --output='../unmined/overworld' --dimension=overworld --mapsettings='./Everthorn.json' {common_params}",
            'nether': f"{base_cmd} --output='../unmined/nether' --dimension=nether --mapsettings='./Nether.json' {common_params}",
            'subway': f"{base_cmd} --output='../unmined/subway' --dimension=overworld --mapsettings='./Subway.json' {common_params}"
        }

        try:
            processes = [await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT) for cmd in render_tasks.values()]

            logger.info(f'Starting {len(render_tasks)} Map Renders...')
            start_time = datetime.now()

            results = await asyncio.gather(*[p.wait() for p in processes], return_exceptions=True)

            successful = [list(render_tasks.keys())[i] for i, result in enumerate(results) if result == 0]

            duration = datetime.now() - start_time
            minutes = duration.seconds // 60
            seconds = duration.seconds % 60

            logger.info(f'Map Render completed in {minutes}m {seconds}s. Completed: {len(successful)}/{len(results)}')
            logger.info(f'All Renders: {", ".join(render_tasks.keys())}')
            logger.info(f'Completed Renders: {", ".join(successful)}')

        except Exception as e:
            logger.error(f'Map update failed: {e.__class__.__name__} - {str(e)}')

    async def backup(self):
        with tempfile.TemporaryDirectory(dir=self.backup_path) as temp_dir:
            temp_dir_path = Path(temp_dir)

            await asyncio.to_thread(self.__copy_files_to_dir, temp_dir_path)
            await asyncio.to_thread(self.__copy_extra_files, temp_dir_path)
            await asyncio.to_thread(self.__zip_files, temp_dir_path)

    async def map_update(self):
        with tempfile.TemporaryDirectory(dir=self.backup_path) as temp_dir:
            temp_dir_path = Path(temp_dir)

            level_path: Path = await asyncio.to_thread(self.__copy_files_to_dir, temp_dir_path)
            await self.__run_unmined('..' / level_path)
