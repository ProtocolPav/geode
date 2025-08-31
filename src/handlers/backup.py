import asyncio
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from sanic.log import logger, Colors

from src.handlers.config import ConfigHandler
from src.cloud_services.base import get_cloud_service

class BackupHandler:
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
                self.server_path / Path('config/default/variables.json')
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
        
        return f'{self.bucket_name}/{backup_type}/{relative_path}'

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
            zip_file_name = await asyncio.to_thread(self.__zip_files, temp_dir_path)
            await asyncio.to_thread(self.__upload_to_cloud, temp_dir_path, zip_file_name)

    async def map_update(self):
        with tempfile.TemporaryDirectory(dir=self.backup_path) as temp_dir:
            temp_dir_path = Path(temp_dir)

            level_path: Path = await asyncio.to_thread(self.__copy_files_to_dir, temp_dir_path)
            await self.__run_unmined('..' / level_path)