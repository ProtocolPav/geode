import asyncio
from collections.abc import Callable

from sanic.log import logger, Colors

from src.models import Loop


class LoopHandler:
    def __init__(self):
        self.__loops: dict[str, Loop] = {}
        self.running = False
        self._geode = None

    def loop(self, name: str, interval: int, delay: int = 0, send_logs: bool = True):
        """
        Decorator function to add a callback function to the loop handler

        :param name: The name of the loop
        :param interval: The interval in seconds between each loop
        :param delay: (Optional) The delay in seconds before starting the loop for the first time
        :param send_logs: (Optional) Whether the loop handler should send a log each time the loop runs
        """
        def decorator(func):
            self.add_loop(func, name, interval, delay, send_logs=send_logs)

        return decorator

    def add_loop(self, callback: Callable, name: str, interval: int, delay: int = 0, repetitions: int = 0, send_logs: bool = True):
        """
        Adds a callback function to the loop handler

        :param callback: The callback function to add to the loop handler
        :param name: The name of the loop
        :param interval: The interval in seconds between each loop
        :param delay: (Optional) The delay in seconds before starting the loop for the first time
        :param repetitions: (Optional) How many times should the loop be repeated. Set to 0 for infinite
        :param send_logs: (Optional) Whether the loop handler should send a log each time the loop runs
        """
        async def task_function(geode):
            bold_name = f'{Colors.BOLD}{name}{Colors.END}'

            logger.info(f"[Loops] Loading {bold_name} ({callback.__name__}) to loop every {interval} seconds. "
                        f"Repetitions: {repetitions if repetitions > 0 else 'Infinite'}. Send Logs: {send_logs}")

            if delay:
                logger.info(f"[Loops] {bold_name} ({callback.__name__}) initial delay of {delay} seconds")
                await asyncio.sleep(delay)

            loop_i = 0

            while repetitions == 0 or loop_i < repetitions:
                try:
                    if send_logs: logger.info(f"[Loops] Running {bold_name} ({loop_i})...")
                    await callback(geode)
                    loop_i += 1
                    await asyncio.sleep(interval)

                except asyncio.CancelledError as e:
                    logger.exception(f"[Loops] {bold_name} has been canceled", exc_info=e)

                except Exception as e:
                    if e.args:
                        logger.error(f"[Loops] {e}. {Colors.GREY}Trying again in 30 seconds.{Colors.END}")
                    else:
                        logger.error(f"[Loops] There was an error executing {bold_name}. {Colors.GREY}Trying again in 30 seconds.{Colors.END}")
                    await asyncio.sleep(30)

            logger.info(f"[Loops] Finished Running {bold_name}. Maximum Repetitions: {repetitions}, Current Repetitions: {loop_i}")
            self.__loops[name].task.cancel()
            del self.__loops[name]

        self.__loops[name] = Loop(name, task_function)

        if self.running:
            self.__loops[name].task = asyncio.create_task(task_function(self._geode), name=name)

    async def start_looper(self, geode):
        if not self.running:
            self._geode = geode
            logger.info(f"[Loops] Starting loops...")

            for loop in self.__loops.values():
                loop.task = asyncio.create_task(loop.callback(geode), name=loop.name)

            self.running = True