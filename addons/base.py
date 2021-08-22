import random

from Arknights.helper import ArknightsHelper
from abc import ABC, abstractmethod
import time


class BaseAddOn(ABC):
    def __init__(self, helper=None):
        if helper is None:
            helper = ArknightsHelper()
        self.helper = helper

    @abstractmethod
    def run(self, **kwargs):
        pass

    def click(self, pos, sleep_time=0.5, randomness=(5, 5)):
        x, y = pos
        rx, ry = randomness
        x += random.randint(-rx, rx)
        y += random.randint(-ry, ry)
        self.helper.adb.touch_tap((x, y))
        time.sleep(sleep_time)

    def screenshot(self):
        return self.helper.adb.screenshot()
