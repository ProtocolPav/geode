import asyncio
from collections.abc import Callable

from sanic.log import logger, Colors


class LoopHandler:
    def __init__(self):
        self.__loops = []
        self.__tasks = []
        self.running = False

    def loop(self, name: str, interval: int):
        def decorator(func):
            self.add_loop(func, name, interval)

        return decorator

    def add_loop(self, function: Callable, name: str, interval: int):
        async def task_function(geode):
            logger.info(f"[Loops] Loading {name} ({function.__name__}) to loop every {interval} seconds")

            while True:
                try:
                    await function(geode)
                    await asyncio.sleep(interval)

                except asyncio.CancelledError:
                    logger.info(f"[Loops] {name} has been canceled")

                except Exception as e:
                    logger.exception(f"[Loops] There was an error executing {name}. Trying again in 30 seconds.", exc_info=e)
                    await asyncio.sleep(30)

        self.__loops.append(task_function)

    async def start_looper(self, geode):
        if not self.running:
            logger.info(f"[Loops] Starting loops...")

            for loop in self.__loops:
                self.__tasks.append(asyncio.create_task(coro=loop(geode)))

            await asyncio.gather(*self.__tasks)

            self.running = True