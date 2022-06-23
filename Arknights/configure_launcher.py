from automator import launcher, BaseAutomator
from .helper import ArknightsHelper


def init_helper(reset_device=False) -> BaseAutomator:
    launcher._configure('akhelper', ArknightsHelper, reset_device)
    return launcher.helper


helper = init_helper()


def reconnect_helper():
    global helper
    helper = init_helper(True)


def get_helper():
    global helper
    return helper
