import os
import shutil
import tarfile
import tempfile
import httpx
import zipfile
from pathlib import Path
import platform
from sanic.log import logger, Colors


def copy_if_not_exists(src, dst):
    if not os.path.exists(dst):
        shutil.copy2(src, dst)


async def check_for_updates():
    server_dir = Path('../server/')
    server_dir.mkdir(parents=True, exist_ok=True)
    unmined_dir = Path('../unmined/')
    unmined_executable = unmined_dir / 'unmined-cli'

    plat = platform.system().lower()

    if plat not in ['linux']:
        raise OSError('Geode only supports Debian-based Linux distributions, we advise you to run Geode via Docker.')
    logger.info(f'Checking for updates...')
    logger.debug(f'Platform: {plat}')

    client = httpx.AsyncClient()
    latest = await client.get("https://raw.githubusercontent.com/Bedrock-OSS/BDS-Versions/main/versions.json")
    version = latest.json()[plat]['stable']
    should_install = True

    if (server_dir/'version.geode').exists() and (server_dir/'version.geode').read_text() == version:
        should_install = False

    if should_install:
        await install(plat, version, client, server_dir)

    if unmined_executable.exists():
        logger.debug('Unmined CLI already installed')
    else:
        await install_unmined(client, unmined_dir)

    logger.info('Server is up to date!')

async def install(plat: str, version: str, client: httpx.AsyncClient, server_dir: Path):
    data_url = f"https://raw.githubusercontent.com/Bedrock-OSS/BDS-Versions/main/{plat}/{version}.json"
    server_data = (await client.get(data_url)).json()

    with tempfile.TemporaryFile(dir=server_dir) as file:
        logger.debug(f'Found Minecraft Server version {version}')
        logger.debug(f'Found link: {server_data["download_url"]}')

        async with client.stream('GET', server_data['download_url'], headers={'User-Agent': 'Geode/1.0 (Minecraft)'}) as response:
            size_in_MB = f'{Colors.GREY}{round(server_data["size_in_bytes"]/1000/1000, 1)}MB{Colors.END}'
            logger.info(f'{Colors.BOLD}{Colors.BLUE}Downloading Bedrock Server...{Colors.END} | {size_in_MB}')

            async for chunk in response.aiter_bytes(1024):
                file.write(chunk)

            zip_file: zipfile.ZipFile
            with zipfile.ZipFile(file) as zip_file:
                skip_items = ["allowlist.json", "permissions.json", "server.properties", "config/default/permissions.json"]
                zip_size = sum([x.file_size for x in zip_file.infolist()])

                size_in_MB = f'{Colors.GREY}{round(zip_size/1000/1000, 1)}MB{Colors.END}'
                logger.info(f'{Colors.BOLD}{Colors.BLUE}Installing Bedrock Server...{Colors.END} | {size_in_MB}')

                for item in zip_file.infolist():
                    # logger.debug(f'{Colors.GREY}Unzipping {Colors.BOLD}{item.filename}...{Colors.END}')
                    if item.filename in skip_items and (server_dir/item.filename).exists():
                        logger.debug(f'Skipping {Colors.BOLD}{item.filename}{Colors.END}')
                    else:
                        zip_file.extract(item.filename, server_dir)

            for i in server_dir.iterdir():
                os.chmod(i, 0o755)
            logger.info(f'{Colors.BOLD}{Colors.CYAN}Server Version {version} Installed!{Colors.END} | {size_in_MB}')

async def install_unmined(client: httpx.AsyncClient, unmined_dir: Path):
    data_url = "https://unmined.net/download/unmined-cli-linux-x64-dev/"
    extraction_dir = Path('../')

    with tempfile.NamedTemporaryFile(dir=extraction_dir) as file:
        logger.debug(f'Installing Unmined CLI...')

        async with client.stream('GET', data_url, headers={'User-Agent': 'Geode/1.0 (Minecraft)'}) as response:
            size_in_MB = f'{Colors.GREY}{round(int(response.headers.get("x-dlm-filesize", 0))/1000/1000, 1)}MB{Colors.END}'
            logger.info(f'{Colors.BOLD}{Colors.BLUE}Downloading Unmined CLI...{Colors.END} | {size_in_MB}')

            async for chunk in response.aiter_bytes(1024):
                file.write(chunk)

        file.flush()

        with tarfile.open(file.name, 'r:gz') as tar_file:
            root_dir = extraction_dir / Path(tar_file.getnames()[0])
            tar_file.extractall(extraction_dir)

        shutil.copytree(root_dir, unmined_dir, dirs_exist_ok=True, copy_function=copy_if_not_exists)
        shutil.rmtree(root_dir)

        logger.info(f'{Colors.BOLD}{Colors.CYAN}Unmined CLI Installed!{Colors.END} | {size_in_MB}')
