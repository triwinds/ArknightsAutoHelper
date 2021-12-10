import time

from pywinauto import Desktop
from pywinauto.controls.hwndwrapper import DialogWrapper
import pywinauto.mouse as mouse
from imgreco.imgops import match_template
from PIL import Image
import os
import logging
from util.richlog import get_logger
from addons.base import BaseAddOn


file_root = os.path.realpath(os.path.dirname(__file__)) + '/'
reboot_img = Image.open(file_root + 'reboot.png').convert('L')
start_img = Image.open(file_root + 'start.png').convert('L')
login_img = Image.open(file_root + 'login.png').convert('L')
logger = get_logger('restart_mumu')


class VoidAddOn(BaseAddOn):
    def run(self, **kwargs):
        pass


def get_mumu_window():
    for i in Desktop().windows():
        wind: DialogWrapper = i
        if 'MuMu模拟器' in wind.window_text():
            wind.set_focus()
            return wind
    return None


def reboot_mumu(mumu_window):
    logging.info('reboot mumu...')
    if mumu_window is None:
        return False
    try:
        mumu_window.close_alt_f4()
        # click_window_pos(mumu_window, (1265, 15))
        time.sleep(0.5)
    except:
        pass
    return click_window_img(mumu_window, reboot_img)


def start_arknights():
    os.system('adb connect 127.0.0.1:7555')
    os.system('adb -s 127.0.0.1:7555 shell am start -n com.hypergryph.arknights/com.u8.sdk.U8UnityContext')


def click_window_img(mumu_window, pil_gray_img):
    window_img = mumu_window.capture_as_image().convert('L')
    (x, y), p = match_template(window_img, pil_gray_img)
    logging.info(f'click_window_img: {(x, y), p}')
    if p > 0.9:
        click_window_pos(mumu_window, (x, y))
        return True
    else:
        addon = VoidAddOn()
        screen = addon.screenshot()
        gray_screen = screen.convert('L')
        (x, y), p = match_template(gray_screen, pil_gray_img)
        logging.info(f'adb click_window_img: {(x, y), p}')
        if p > 0.9:
            # click_window_pos(mumu_window, (x, y))
            addon.click((x, y))
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
            logger.logimage(window.capture_as_image())
            logger.logimage(BaseAddOn().screenshot())
            raise RuntimeError(f'Fail to click [{img_name}].')
        else:
            logging.info(f'retry click [{img_name}]...')


def restart_all():
    mumu_window = get_mumu_window()
    reboot_mumu(mumu_window)
    time.sleep(20)
    mumu_window = get_mumu_window()
    start_arknights()
    time.sleep(10)
    retry_click_img(mumu_window, start_img, 'start')
    time.sleep(5)
    retry_click_img(mumu_window, login_img, 'login')
    time.sleep(10)


if __name__ == '__main__':
    # 需要管理员权限
    restart_all()
