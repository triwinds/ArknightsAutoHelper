import subprocess
import time
from imgreco.imgops import match_template
from PIL import Image
import os
import logging
from util.richlog import get_logger


file_root = os.path.realpath(os.path.dirname(__file__)) + '/'
start_img = Image.open(file_root + 'start.png').convert('L')
login_img = Image.open(file_root + 'login.png').convert('L')
rich_logger = get_logger('restart_bluestacks')
logger = logging.getLogger(__name__)


def start_and_login_arknights():
    from Arknights.configure_launcher import reconnect_helper, get_helper
    reconnect_helper()
    helper = get_helper()
    helper.control.adb.shell('am start -n com.hypergryph.arknights/com.u8.sdk.U8UnityContext')
    time.sleep(20)
    retry_click_img(start_img, 'start')
    time.sleep(5)
    retry_click_img(login_img, 'login')
    time.sleep(30)


def click_window_img(pil_gray_img):
    from Arknights.configure_launcher import get_helper
    helper = get_helper()
    from Arknights.addons.common import CommonAddon
    addon = helper.addon(CommonAddon)
    screen = addon.screenshot()
    gray_screen = screen.convert('L')
    (x, y), p = match_template(gray_screen, pil_gray_img)
    logger.info(f'adb click_window_img: {(x, y), p}')
    if p > 0.9:
        # click_window_pos(bluestacks_window, (x, y))
        addon.tap_point((x, y))
        return True


def retry_click_img(img, img_name):
    c = 0
    max_retry = 6
    logger.info(f'try to click [{img_name}].')
    while not click_window_img(img):
        time.sleep(20)
        c += 1
        if c > max_retry:
            rich_logger.logtext('fail img_name: ' + img_name)
            # logger.logimage(cvimage.from_pil(window.capture_as_image()))
            # logger.logimage(BaseAddOn().screenshot())
            raise RuntimeError(f'Fail to click [{img_name}].')
        else:
            logger.info(f'retry click [{img_name}]...')


def start_bluestacks():
    subprocess.Popen(r'"C:\Program Files\BlueStacks_nxt\HD-Player.exe" --instance Nougat64')
    time.sleep(60)


def check_bluestacks_is_alive():
    output = subprocess.run(['tasklist'], capture_output=True)
    # print(output.stdout.decode('gbk'))
    return 'HD-Player' in output.stdout.decode('gbk')


def close_bluestacks():
    if not check_bluestacks_is_alive():
        logger.info('bluestacks is not running.')
        return
    logger.info('stopping bluestacks...')
    ret = subprocess.run(['powershell', '$a = Get-Process HD-Player;', '$a.kill();'], capture_output=True)
    if ret.returncode != 0:
        logger.error('stdout:', ret.stdout.decode('gbk'))
        logger.error('stderr:', ret.stderr.decode('gbk'))
    else:
        logger.info('bluestacks stopped.')


def restart_all():
    close_bluestacks()
    start_bluestacks()
    start_and_login_arknights()


if __name__ == '__main__':
    restart_all()
