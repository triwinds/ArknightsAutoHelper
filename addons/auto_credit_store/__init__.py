import time
from Arknights.helper import ArknightsHelper, logger
from imgreco import inventory
import cv2
import numpy as np
import imgreco
from imgreco.ocr.ppocr import do_ocr, ocr_for_single_line
from util.richlog import get_logger
from logging import DEBUG, INFO, WARN, ERROR
from addons.base import BaseAddOn


rich_logger = get_logger(__name__)


def show_img(img):
    cv2.imshow('test', img)
    cv2.waitKey()


def log_text(text, level=INFO):
    rich_logger.logtext(text)
    logger.log(level, text)


def get_credit_price(cv_screen, item_pos, ratio):
    x, y = item_pos
    x = x - int(50 * ratio)
    y = y + int(76 * ratio)
    price_img = cv_screen[y:y + int(30 * ratio), x:x + int(120 * ratio)]
    price_img = cv2.cvtColor(price_img, cv2.COLOR_RGB2GRAY)
    price_img[price_img < 180] = 0
    price_img = cv2.cvtColor(price_img, cv2.COLOR_GRAY2RGB)
    res = int(ocr_for_single_line(price_img, '0123456789'))
    return res


def get_total_credit(pil_screen):
    vw, vh = imgreco.util.get_vwvh(pil_screen.size)
    rect = tuple(map(int, (100*vw-20.139*vh, 3.333*vh, 100*vw-2.361*vh, 7.500*vh)))
    credit_img = cv2.cvtColor(np.asarray(pil_screen.crop(rect)), cv2.COLOR_BGR2RGB)
    raw_credit_img = credit_img.copy()
    credit_img = cv2.cvtColor(credit_img, cv2.COLOR_RGB2GRAY)
    credit_img[credit_img < 140] = 0
    # credit_img = cv2.resize(credit_img, (0, 0), fx=1.5, fy=1.5)
    credit_img = crop_image_only_outside(credit_img, raw_credit_img, padding=6)
    # credit_img = cv2.cvtColor(credit_img, cv2.COLOR_GRAY2RGB)
    # show_img(credit_img)
    s = ocr_for_single_line(credit_img).upper().replace('S', '5').replace('O', '0')
    return int(s)


def get_value(item_id: str, item_name: str, item_type: str, quantity: int):
    if item_name == '招聘许可':
        return 350
    if item_name.startswith('技巧概要·卷'):
        level = int(item_name[6:])
        return level * 100
    if item_type == 'MATERIAL' and item_id.isdigit() and len(item_id) == 5:
        if item_name in {'装置', '异铁', '酮凝集'}:
            return 300
        level = int(item_id[4:])
        return level * 100 - 50
    if item_name == '龙门币':
        if quantity == 3600:
            return 200
        return 150
    if item_name == '赤金':
        return 200
    if item_type == 'CARD_EXP':
        level = int(item_id[3:])
        return level * 100
    return 1


def solve(total_credit, values, prices):
    total_items = len(values) - 1
    dp = np.zeros((total_items + 1, total_credit + 1), dtype=np.int32)
    for i in range(1, total_items + 1):
        for j in range(1, total_credit + 1):
            if prices[i] <= j:
                dp[i, j] = max(dp[i - 1, j - prices[i]] + values[i], dp[i - 1, j])
            else:
                dp[i, j] = dp[i - 1, j]
    item = [0]*len(values)
    find_what(dp, total_items, total_credit, values, prices, item)
    return item


def find_what(dp, i, j, values, prices, item):  # 最优解情况
    if i >= 0:
        if dp[i][j] == dp[i - 1][j]:
            item[i] = 0
            find_what(dp, i - 1, j, values, prices, item)
        elif j - prices[i] >= 0 and dp[i][j] == dp[i - 1][j - prices[i]] + values[i]:
            item[i] = 1
            find_what(dp, i - 1, j - prices[i], values, prices, item)


def crop_image_only_outside(gray_img, raw_img, threshold=128, padding=3):
    mask = gray_img > threshold
    m, n = gray_img.shape[:2]
    mask0, mask1 = mask.any(0), mask.any(1)
    col_start, col_end = mask0.argmax(), n - mask0[::-1].argmax()
    row_start, row_end = mask1.argmax(), m - mask1[::-1].argmax()
    return raw_img[row_start - padding:row_end + padding, col_start - padding:col_end + padding]


class AutoCreditStoreAddOn(BaseAddOn):
    def run(self, **kwargs):
        self.helper.replay_custom_record('goto_credit_store')
        screen = self.helper.adb.screenshot()
        rich_logger.logimage(screen)
        total_credit = get_total_credit(screen)
        log_text(f'total_credit: {total_credit}')
        infos = inventory.get_all_item_details_in_screen(screen, exclude_item_ids={'other'},
                                                         only_normal_items=False)
        cv_screen = cv2.cvtColor(np.asarray(screen), cv2.COLOR_BGR2RGB)
        h, w = cv_screen.shape[:2]
        ratio = h / 720
        values, prices = [0], [0]
        for info in infos:
            item_value = get_value(info['itemId'], info['itemName'], info['itemType'], info['quantity'])
            price = get_credit_price(cv_screen, info['itemPos'], ratio)
            log_text(f"{info['itemId']} - {info['itemName']}: {item_value} - {price}", DEBUG)
            values.append(item_value)
            prices.append(price)
        solve_items = solve(total_credit, values, prices)[1:]
        picked_items = []
        for i in range(len(solve_items)):
            if solve_items[i] == 1:
                picked_items.append(infos[i])
        if not picked_items:
            log_text('信用点不足以购买任何商品.')
            return
        picked_names = [picked_item['itemName'] for picked_item in picked_items]
        log_text(f"picked items: {', '.join(picked_names)}")
        for picked_item in picked_items:
            log_text(f'buy item: {picked_item}')
            self.click(picked_item['itemPos'])
            self.helper.replay_custom_record('buy_credit_item', quiet=True)


if __name__ == '__main__':
    AutoCreditStoreAddOn().run()
    # print(get_total_credit(AutoCreditStoreAddOn().screenshot()))
    # from PIL import Image
    # print(get_total_credit(Image.open('../../screenshots/test58.png')))
