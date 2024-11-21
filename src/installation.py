import asyncio
import tempfile
import httpx
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn, SpinnerColumn
from os import PathLike
import zipfile
from pathlib import Path
import platform


async def download():
    server_dir = Path('../server/')
    server_dir.mkdir(parents=True, exist_ok=True)
    plat = platform.system().lower()

    if plat not in ['windows', 'linux']: raise OSError('Platform not supported! Must be ran on Windows or Linux')

    client = httpx.AsyncClient()
    latest = await client.get("https://raw.githubusercontent.com/Bedrock-OSS/BDS-Versions/main/versions.json")
    version = latest.json()[plat]['stable']

    data_url = f"https://raw.githubusercontent.com/Bedrock-OSS/BDS-Versions/main/{plat}/{version}.json"
    server_data = (await client.get(data_url)).json()

    with tempfile.TemporaryFile(dir=server_dir) as file:
        async with client.stream('GET', server_data['download_url'], headers={'User-Agent': 'Geode/1.0 (Minecraft 1.12.1)'}) as response:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TimeRemainingColumn()
            ) as progress:
                download_task = progress.add_task("[bold cyan]Downloading Bedrock Server...",
                                                  total=server_data['size_in_bytes'])

                async for chunk in response.aiter_bytes(1024):
                    progress.update(download_task, advance=len(chunk))
                    file.write(chunk)

                progress.update(download_task, description="[bold blue]Downloaded!")

                zip_file: zipfile.ZipFile
                with zipfile.ZipFile(file) as zip_file:
                    skip_items = ["allowlist.json", "permissions.json", "server.properties"]
                    zip_size = sum([x.file_size for x in zip_file.infolist()])

                    install_task = progress.add_task("[bold cyan]Installing Bedrock Server...",
                                                     total=zip_size)

                    for item in zip_file.infolist():
                        progress.update(install_task, advance=item.file_size)
                        if item.filename in skip_items and (server_dir/item.filename).exists():
                            pass

                        zip_file.extract(item.filename, server_dir)

                progress.update(install_task, description="[bold blue]Server Installed!")

asyncio.run(download())