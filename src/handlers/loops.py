import asyncio
from collections.abc import Callable

from sanic.log import logger, Colors

from src import errors


class LoopHandler:
    def __init__(self):
        self.__loops = []
        self.__tasks = []
        self.running = False

    def loop(self, name: str, interval: int, delay: int = 0):
        """
        Decorator function to add a callback function to the loop handler

        :param name: The name of the loop
        :param interval: The interval in seconds between each loop
        :param delay: (Optional) The delay in seconds before starting the loop for the first time
        """
        def decorator(func):
            self.add_loop(func, name, interval, delay)

        return decorator

    def add_loop(self, callback: Callable, name: str, interval: int, delay: int = 0):
        """
        Adds a callback function to the loop handler

        :param callback: The callback function to add to the loop handler
        :param name: The name of the loop
        :param interval: The interval in seconds between each loop
        :param delay: (Optional) The delay in seconds before starting the loop for the first time
        """
        async def task_function(geode):
            bold_name = f'{Colors.BOLD}{name}{Colors.END}'
            logger.info(f"[Loops] Loading {bold_name} ({callback.__name__}) to loop every {interval} seconds")
            if delay:
                logger.info(f"[Loops] {bold_name} ({callback.__name__}) initial delay of {delay} seconds")
                await asyncio.sleep(delay)

            while True:
                try:
                    logger.info(f"[Loops] Running {bold_name}...")
                    await callback(geode)
                    await asyncio.sleep(interval)

                except asyncio.CancelledError as e:
                    logger.exception(f"[Loops] {bold_name} has been canceled", exc_info=e)

                except Exception as e:
                    if e.args:
                        logger.error(f"[Loops] {e}. {Colors.GREY}Trying again in 30 seconds.{Colors.END}")
                    else:
                        logger.error(f"[Loops] There was an error executing {bold_name}. {Colors.GREY}Trying again in 30 seconds.{Colors.END}")
                    await asyncio.sleep(30)

        self.__loops.append(task_function)

    async def start_looper(self, geode):
        if not self.running:
            logger.info(f"[Loops] Starting loops...")

            for loop in self.__loops:
                self.__tasks.append(asyncio.create_task(coro=loop(geode)))

            self.running = True