import subprocess
import time

from pywinauto import Desktop
from pywinauto.controls.hwndwrapper import DialogWrapper
import pywinauto.mouse as mouse
from imgreco.imgops import match_template
from PIL import Image
import os
import logging

from util import cvimage
from util.richlog import get_logger


file_root = os.path.realpath(os.path.dirname(__file__)) + '/'
close_img = Image.open(file_root + 'close.png').convert('L')
start_img = Image.open(file_root + 'start.png').convert('L')
login_img = Image.open(file_root + 'login.png').convert('L')
logger = get_logger('restart_bluestacks')


def get_bluestacks_window():
    for i in Desktop().windows():
        wind: DialogWrapper = i
        if 'BlueStacks App Player' == wind.window_text():
            wind.set_focus()
            return wind
    return None


def close_bluestacks(bluestacks_window):
    logging.info('close bluestacks...')
    if bluestacks_window is None:
        return False
    try:
        bluestacks_window.close_alt_f4()
        time.sleep(0.5)
    except:
        pass
    return click_window_img(bluestacks_window, close_img)


def start_arknights():
    from Arknights.configure_launcher import reconnect_helper, get_helper
    reconnect_helper()
    helper = get_helper()
    helper.control.adb.shell('am start -n com.hypergryph.arknights/com.u8.sdk.U8UnityContext')
    time.sleep(10)


def click_window_img(bluestacks_window, pil_gray_img):
    window_img = bluestacks_window.capture_as_image().convert('L')
    (x, y), p = match_template(window_img, pil_gray_img)
    logging.info(f'click_window_img: {(x, y), p}')
    if p > 0.9:
        click_window_pos(bluestacks_window, (x, y))
        return True
    else:
        from Arknights.configure_launcher import get_helper
        helper = get_helper()
        from Arknights.addons.common import CommonAddon
        addon = helper.addon(CommonAddon)
        screen = addon.screenshot()
        gray_screen = screen.convert('L')
        (x, y), p = match_template(gray_screen, pil_gray_img)
        logging.info(f'adb click_window_img: {(x, y), p}')
        if p > 0.9:
            # click_window_pos(bluestacks_window, (x, y))
            addon.tap_point((x, y))
            return True
    return False


def click_window_pos(window, pos):
    x, y = pos
    x, y = int(x), int(y)
    x, y = window.client_to_screen((x, y))
    mouse.click(coords=(x, y))


def retry_click_img(window, img, img_name):
    c = 0
    max_retry = 6
    logging.info(f'try to click [{img_name}].')
    while not click_window_img(window, img):
        time.sleep(20)
        c += 1
        if c > max_retry:
            logger.logtext('fail img_name: ' + img_name)
            logger.logimage(cvimage.from_pil(window.capture_as_image()))
            # logger.logimage(BaseAddOn().screenshot())
            raise RuntimeError(f'Fail to click [{img_name}].')
        else:
            logging.info(f'retry click [{img_name}]...')


def start_bluestacks():
    subprocess.Popen(r'"C:\Program Files\BlueStacks_nxt\HD-Player.exe" --instance Nougat64')
    time.sleep(20)


def restart_all():
    bluestacks_window = get_bluestacks_window()
    close_bluestacks(bluestacks_window)
    start_bluestacks()
    bluestacks_window = get_bluestacks_window()
    start_arknights()
    retry_click_img(bluestacks_window, start_img, 'start')
    time.sleep(5)
    retry_click_img(bluestacks_window, login_img, 'login')
    time.sleep(10)


if __name__ == '__main__':
    restart_all()
