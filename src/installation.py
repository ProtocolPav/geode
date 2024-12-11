import tempfile
import httpx
import zipfile
from pathlib import Path
import platform
from sanic.log import logger, Colors


async def download():
    server_dir = Path('../server/')
    server_dir.mkdir(parents=True, exist_ok=True)
    plat = platform.system().lower()

    if plat not in ['linux']:
        raise OSError('Geode only supports Debian-based Linux distributions, we advise you to run Geode via Docker.')
    logger.debug(f'Platform: {plat} | Distribution: {platform.freedesktop_os_release()}')

    client = httpx.AsyncClient()
    latest = await client.get("https://raw.githubusercontent.com/Bedrock-OSS/BDS-Versions/main/versions.json")
    version = latest.json()[plat]['stable']

    # Check if version should be installed. Separate the functions.

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
                    logger.debug(f'{Colors.GREY}Unzipping {Colors.BOLD}{item.filename}...{Colors.END}')
                    if item.filename in skip_items and (server_dir/item.filename).exists():
                        logger.debug(f'Skipping {Colors.BOLD}{item.filename}{Colors.END}')
                    else:
                        zip_file.extract(item.filename, server_dir)

            logger.info(f'{Colors.BOLD}{Colors.CYAN}Server Version {version} Installed!{Colors.END} | {size_in_MB}')
