import json
import os
from logging import DEBUG, INFO

import cv2
import numpy as np

import imgreco
from Arknights.helper import logger
from addons.base import BaseAddOn
from imgreco import inventory
from imgreco.common import convert_to_pil
from imgreco.stage_ocr import do_tag_ocr
from util.richlog import get_logger

rich_logger = get_logger(__name__)
item_value_file = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'item_value.json')


def init_value_map():
    with open(item_value_file, 'r', encoding='utf-8') as f:
        return json.load(f)


value_map = init_value_map()


def show_img(img):
    cv2.imshow('test', img)
    cv2.waitKey()


def log_text(text, level=INFO):
    rich_logger.logtext(text)
    logger.log(level, text)


def get_credit_price(cv_screen, item_pos, ratio):
    x, y = item_pos
    x = x - int(50 * ratio)
    y = y + int(77 * ratio)
    price_img = cv_screen[y:y + int(28 * ratio), x:x + int(120 * ratio)]
    price_img = cv2.cvtColor(price_img, cv2.COLOR_RGB2GRAY)
    price_img = cv2.threshold(price_img, 180, 255, cv2.THRESH_BINARY)[1]
    cv2.rectangle(cv_screen, (x, y), (x + int(120 * ratio), y + int(28 * ratio)), (0, 255, 0))
    # show_img(price_img)
    res = do_tag_ocr(price_img)
    return int(res)


def get_total_credit(pil_screen):
    vw, vh = imgreco.util.get_vwvh(pil_screen.size)
    rect = tuple(map(int, (100*vw-20.139*vh, 3.333*vh, 100*vw-2.361*vh, 7.500*vh)))
    credit_img = cv2.cvtColor(np.asarray(pil_screen.crop(rect)), cv2.COLOR_BGR2RGB)
    credit_img = cv2.cvtColor(credit_img, cv2.COLOR_RGB2GRAY)
    credit_img = cv2.threshold(credit_img, 140, 255, cv2.THRESH_BINARY)[1]
    return int(do_tag_ocr(credit_img, 1))


def get_value_old(item_id: str, item_name: str, item_type: str, quantity: int):
    if item_name == '招聘许可':
        return 900
    if item_name.startswith('技巧概要·卷'):
        level = int(item_name[6:]) - 1
        return (3 ** level) * 10 * quantity
    if item_type == 'MATERIAL' and item_id.isdigit() and len(item_id) == 5:
        quantity = quantity if quantity else 2
        if item_name == '异铁':
            return 150 * quantity
        elif item_name == '装置':
            return 120
        elif item_name == '酮凝集':
            return 100 * quantity
        level = int(item_id[4:]) - 1
        return (4 ** level) * 15 * quantity
    if item_name == '龙门币':
        if quantity == 3600:
            return 150
        return 75
    if item_name == '赤金':
        return 150
    if item_type == 'CARD_EXP':
        level = int(item_id[3:]) - 1
        return (2 ** level) * 18 * quantity
    return 1


def get_value(item_id: str, item_name: str, item_type: str, quantity: int):
    low_value_name_contains = ['碳', '加急许可', '家具']
    for en in low_value_name_contains:
        if en in item_name:
            return 1
    quantity = quantity if quantity else 1
    if item_name in value_map:
        sanity = value_map[item_name]
        return int(quantity * sanity * 100)


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


def calc_items(screen):
    rich_logger.logimage(screen)
    total_credit = get_total_credit(screen)
    log_text(f'total_credit: {total_credit}')
    infos = inventory.get_all_item_details_in_screen(screen, exclude_item_ids={'other'},
                                                     only_normal_items=False)
    cv_screen = cv2.cvtColor(np.asarray(screen), cv2.COLOR_BGR2RGB)
    h, w = cv_screen.shape[:2]
    ratio = h / 720
    values, prices = [0], [0]
    log_text(f"[itemId-itemName]: price/item_value", DEBUG)
    for info in infos:
        item_value = get_value(info['itemId'], info['itemName'], info['itemType'], info['quantity'])
        price = get_credit_price(cv_screen, info['itemPos'], ratio)
        cv2.circle(cv_screen, info['itemPos'], 4, (255, 0, 0), -1)
        log_text(f"[{info['itemId']}-{info['itemName']}]: {price}/{item_value}", DEBUG)
        values.append(item_value)
        prices.append(price)
    rich_logger.logimage(convert_to_pil(cv_screen))
    solve_items = solve(total_credit, values, prices)[1:]
    picked_items = []
    for i in range(len(solve_items)):
        if solve_items[i] == 1:
            picked_items.append(infos[i])
    if not picked_items:
        log_text('信用点不足以购买任何商品.')
        return picked_items
    picked_names = [picked_item['itemName'] for picked_item in picked_items]
    log_text(f"picked items: {', '.join(picked_names)}")
    return picked_items


class AutoCreditStoreAddOn(BaseAddOn):
    def run(self, **kwargs):
        self.helper.replay_custom_record('goto_credit_store')
        screen = self.helper.adb.screenshot()
        picked_items = calc_items(screen)
        for picked_item in picked_items:
            log_text(f'buy item: {picked_item}')
            self.click(picked_item['itemPos'])
            self.helper.replay_custom_record('buy_credit_item', quiet=True)


if __name__ == '__main__':
    AutoCreditStoreAddOn().run()
    # print(get_total_credit(AutoCreditStoreAddOn().screenshot()))
    # from PIL import Image
    # print(get_total_credit(Image.open('../../screenshot/test/img.png')))
    # print(get_total_credit(Image.open('../../screenshot/test/img_1.png')))
    # print(get_total_credit(Image.open('../../screenshot/test/img_2.png')))
    # print(calc_items(Image.open('../../screenshot/test/img_2.png')))
