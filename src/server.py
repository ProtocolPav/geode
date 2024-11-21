import asyncio.subprocess
import platform
import tempfile
from urllib.parse import to_bytes

import httpx
import rich.progress
from os import PathLike
import zipfile
from pathlib import Path


class BedrockServer:
    process: asyncio.subprocess.Process
    tasks: asyncio.TaskGroup

    def __init__(self):

        if platform.system().lower() == 'windows':
            self.executable = '../server/bedrock_server.exe'
        elif platform.system().lower() == 'linux':
            self.executable = '../server/bedrock_server'
        else:
            raise OSError('Platform not supported! Must be ran on Windows or Linux')



    async def start(self):
        self.process = await asyncio.subprocess.create_subprocess_shell(
            cmd=self.executable,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit= 1024 * 512)

        async with asyncio.TaskGroup() as self.tasks:
            self.tasks.create_task(self.__server_output())
            # self.tasks.create_task(self.__server_input())



    async def __server_output(self):
        while True:
            line = (await self.process.stdout.readline()).decode().rstrip()
            if not line:
                pass
            elif "Quit correctly" in line:
                print(line)
                break
            else:

                print(line)

    async def __server_input(self):
        while True:
            # Get user input asynchronously
            command = await asyncio.to_thread(input)
            if command.strip().lower() == "exit":
                print("Terminating server...")
                self.process.terminate()
                await self.process.wait()
                break

            # Send the command to the subprocess
            self.process.stdin.write((command + "\n").encode())
            await self.process.stdin.drain()  # Ensure the command is sent

server = BedrockServer()
asyncio.new_event_loop().run_until_complete(server.start())