import json
import random
import time

from Arknights.helper import logger
from addons.base import BaseAddOn
from addons.common_cache import load_common_cache
from imgreco.ocr.cnocr import ocr_for_single_line
from imgreco import util

import cv2
import os
import numpy as np


def open_img(name, mode=cv2.IMREAD_GRAYSCALE):
    filepath = os.path.join(os.path.realpath(os.path.dirname(__file__)), name)
    return cv2.imread(filepath, mode)


overview_test_img = open_img('overview_test.png')
zoom_test_img = open_img('zoom_test.png')
open_shift_img = open_img('open_shift.png')

current_shift_file = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'current_shift_cache.json')

character_table = load_common_cache('character_table', force_update=False)
cn_op_names = set()
for cid, character_info in character_table.items():
    cn_op_names.add(character_info['name'])

room_rect_map = {
    'control_room': (649, 69, 1057, 247),
    '1F02': (1133, 162, 1267, 231),

    'b101': (1, 256, 158, 354),
    'b102': (165, 256, 372, 354),
    'b103': (382, 256, 579, 354),
    'b104': (642, 256, 950, 354),
    'b105': (1224, 256, 1277, 354),

    'b201': (2, 359, 52, 462),
    'b202': (71, 359, 252, 462),
    'b203': (278, 359, 476, 462),
    'b204': (748, 359, 1058, 462),
    'b205': (1231, 359, 1278, 462),

    'b301': (7, 469, 155, 570),
    'b302': (171, 469, 374, 570),
    'b303': (381, 469, 582, 570),
    'b304': (648, 469, 955, 570),
    'b305': (1231, 469, 1277, 570),

    'b401': (751, 579, 1055, 667)
}


# 疲劳值 icon 半径 10
def get_circles(gray_img, min_radius=8, max_radius=11):
    circles = cv2.HoughCircles(gray_img, cv2.HOUGH_GRADIENT, 1, 30, param1=128,
                               param2=30, minRadius=min_radius, maxRadius=max_radius)
    return circles[0]


def show_img(img):
    cv2.imshow('test', img)
    cv2.waitKey()


def crop_screen_by_rect(cv_screen, rect):
    return cv_screen[int(rect[1]):int(rect[3]), int(rect[0]):int(rect[2])]


def ocr_tag(tag, white_threshold=150):
    # show_img(tag)
    tag = cv2.cvtColor(tag, cv2.COLOR_RGB2GRAY)
    tag[tag < white_threshold] = 0
    tag = cv2.cvtColor(tag, cv2.COLOR_GRAY2RGB)
    # show_img(tag)
    return ocr_for_single_line(tag)


def cvt2cv(pil_img, color=cv2.COLOR_BGR2RGB):
    return cv2.cvtColor(np.asarray(pil_img), color)


def test_color(c1, c2, channel=3, diff=10):
    for i in range(channel):
        if abs(c1[i] - c2[i]) > diff:
            return False
    return True


def is_on_shift(cv_screen, icon_pos):
    h, w = cv_screen.shape[:2]
    x, y = icon_pos
    standard_color = [220, 152, 0]
    colors = []
    if x - 30 > 0:
        colors.append(cv_screen[y][x - 30])
    if x + 112 < w:
        colors.append(cv_screen[y][x + 112])
    for color in colors:
        if not test_color(standard_color, color):
            return False
    return True


def process_circle(cv_screen, dbg_screen, res, x, y, r):
    h, w = cv_screen.shape[:2]
    x, y, r = int(x), int(y), int(r)
    if x + 105 > w:
        return
    # print(x, y, r)
    name_tag = cv_screen[y + 6:y + 35, x + 10:x + 105]
    op_name = ocr_tag(name_tag, 130)
    tag_color = (0, 0, 255)
    if op_name in cn_op_names:
        tag_color = (255, 255, 0)
        res.append({'op_name': op_name, 'pos': (x, y), 'on_shift': is_on_shift(cv_screen, (x, y))})
    cv2.circle(dbg_screen, (x, y), r, (0, 255, 255), 2)
    cv2.rectangle(dbg_screen, (x + 10, y + 6), (x + 105, y + 35), tag_color, 2)
    # show_img(name_tag)


def group_pos(values):
    tmp = {}
    for value in values:
        flag = True
        for k, v in tmp.items():
            if abs(value - k) < 20:
                v.append(value)
                flag = False
                break
        if flag:
            tmp[value] = [value]
    res = [sum(v) // len(v) for v in tmp.values()]
    res.sort()
    return res


class AutoShiftAddOn(BaseAddOn):
    def __init__(self, helper=None):
        super().__init__(helper)
        self.vw, self.vh = util.get_vwvh(self.helper.viewport)

    def run(self, **kwargs):
        current_shift_info = {'current_shift': 1, 'time': 0}
        if os.path.exists(current_shift_file):
            with open(current_shift_file, 'r') as f:
                current_shift_info = json.load(f)
            if time.time() < current_shift_info.get('time', 0) + 3600 * 6:
                logger.info(f'距离上次基建换班不到 6 小时, 跳过此次换班')
                return
        pending_shift = current_shift_info['current_shift'] % 2 + 1
        logger.info(f'执行基建换班, 使用的排班方案为: {pending_shift}')
        self.goto_building()
        self.apply_shift(f'shift{pending_shift}_cache.json')
        current_shift_info['current_shift'] = pending_shift
        current_shift_info['time'] = int(time.time())
        with open(current_shift_file, 'w') as f:
            json.dump(current_shift_info, f)

    def get_all_op_on_screen(self, process_with_fixed_y=True):
        screen = self.screenshot()
        cv_screen = cv2.cvtColor(np.asarray(screen), cv2.COLOR_BGR2RGB)

        dbg_screen = cv_screen.copy()
        gray_screen = cv2.cvtColor(cv_screen, cv2.COLOR_RGB2GRAY)
        blur_screen = cv2.GaussianBlur(gray_screen, (5, 5), 2.5)
        # show_img(blur_screen)
        circles = get_circles(blur_screen)
        res = []

        if process_with_fixed_y:
            center_ys = [314, 595]
            center_xs = group_pos(circles[:, 0])
            for x in center_xs:
                for y in center_ys:
                    process_circle(cv_screen, dbg_screen, res, x, y, 10)
        else:
            for x, y, r in circles:
                process_circle(cv_screen, dbg_screen, res, x, y, r)
        # show_img(dbg_screen)
        return res

    def tap_clear(self):
        vw, vh = self.vw, self.vh
        self.helper.tap_rect((100 * vw - 18.333 * vh, 0.833 * vh, 100 * vw - 4.722 * vh, 7.639 * vh))
        screen = self.screenshot()
        cv_screen = cvt2cv(screen)
        if test_color([15, 15, 112], cv_screen[int(68.472 * vh)][-1]):
            self.helper.tap_rect((50 * vw + 4.861 * vh, 63.611 * vh, 50 * vw + 79.306 * vh, 73.333 * vh))
        time.sleep(1)

    def tap_confirm(self):
        vw, vh = self.vw, self.vh
        confirm_rect = (100 * vw - 24.861 * vh, 90.417 * vh, 100 * vw - 3.056 * vh, 96.944 * vh)
        self.helper.tap_rect(confirm_rect)
        screen = self.screenshot()
        cv_screen = cvt2cv(screen)
        if test_color([113, 86, 6], cv_screen[-1][-1]):
            self.helper.tap_rect((50 * vw + 14.444 * vh, 90.278 * vh, 50 * vw + 84.861 * vh, 99.167 * vh))
        time.sleep(1)

    def tap_back(self):
        vw, vh = self.vw, self.vh
        self.helper.tap_rect((2.222 * vh, 1.944 * vh, 22.361 * vh, 8.333 * vh))
        time.sleep(0.5)

    def tap_first_slot(self):
        vw, vh = self.vw, self.vh
        self.helper.tap_rect((100 * vw - 57.500 * vh, 12.361 * vh, 100 * vw - 14.583 * vh, 30.000 * vh))

    def get_op_sanity(self, cv_screen):
        vw, vh = self.vw, self.vh
        sanity_tag = crop_screen_by_rect(cv_screen, (42.639 * vh, 13.194 * vh, 52.083 * vh, 17.361 * vh))
        return ocr_tag(sanity_tag, 150)

    def _test_img(self, template, threshold=0.9):
        screenshot = self.screenshot()
        gray_screen = cvt2cv(screenshot, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray_screen, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        return max_val > threshold

    def open_room_shift_view(self):
        screenshot = self.screenshot()
        gray_screen = cvt2cv(screenshot, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray_screen, open_shift_img, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        # print(max_loc)
        if max_val > 0.9:
            self.click(max_loc)

    def is_in_overview(self):
        return self._test_img(overview_test_img)

    def is_in_original_zoom(self):
        return self._test_img(zoom_test_img)

    def open_room(self, room):
        room_rect = room_rect_map.get(room)
        if not room_rect:
            raise RuntimeError(f'Can not find room: {room}')
        if not self.is_in_original_zoom():
            raise RuntimeError('Not in original zoom state.')
        for _ in range(2):
            self.helper.tap_rect(room_rect)
            time.sleep(0.5)
            if not self.is_in_original_zoom():
                return
        raise RuntimeError(f'Fail to open room {room}')

    def get_on_shift_op_on_screen(self):
        infos = self.get_all_op_on_screen()
        return [op_info for op_info in infos if op_info['on_shift']]

    def __swipe_screen(self, move, rand=100, origin_x=None, origin_y=None, swipe_time=random.randint(900, 1200)):
        origin_x = (origin_x or self.helper.viewport[0] // 2) + random.randint(-rand, rand)
        origin_y = (origin_y or self.helper.viewport[1] // 2) + random.randint(-rand, rand)
        self.helper.adb.touch_swipe2((origin_x, origin_y), (move, max(250, move // 2)), swipe_time)

    def dump_current_shift(self, save_file='shift_cache.json', choose_room: set = None, exclude_room={'b105', 'b305'}):
        res = {}
        if choose_room and exclude_room:
            exclude_room -= choose_room
        for room in room_rect_map.keys():
            if choose_room and room not in choose_room:
                continue
            if room in exclude_room:
                continue
            self.open_room(room)
            self.open_room_shift_view()
            self.tap_first_slot()
            op_infos = self.get_on_shift_op_on_screen()
            res[room] = [op_info['op_name'] for op_info in op_infos]
            logger.info(f'{room}: {res[room]}')
            self.tap_back()
            self.tap_back()
        if save_file:
            with open(os.path.join(os.path.realpath(os.path.dirname(__file__)), save_file), 'w', encoding='utf-8') as f:
                json.dump(res, f, ensure_ascii=False, indent=4)
        return res

    def apply_shift(self, shift_file='shift_cache.json'):
        with open(os.path.join(os.path.realpath(os.path.dirname(__file__)), shift_file), 'r', encoding='utf-8') as f:
            shift_schedule = json.load(f)
        for room, ops in shift_schedule.items():
            logger.info(f'applying room {room}: {ops}')
            self.open_room(room)
            self.open_room_shift_view()
            self.tap_clear()
            self.tap_first_slot()

            last_ops = set()
            cur_ops = set()
            scroll_flag = False
            while True:
                op_infos = self.get_all_op_on_screen()
                for op_info in op_infos:
                    cur_ops.add(op_info['op_name'])
                    if op_info['op_name'] in ops:
                        x, y = op_info['pos']
                        self.click((x + 50, y - 100), 0.1)
                        ops.remove(op_info['op_name'])
                if not ops:
                    break
                else:
                    scroll_flag = True
                    move = -random.randint(self.helper.viewport[0] // 6, self.helper.viewport[0] // 5)
                    self.__swipe_screen(move, 50, self.helper.viewport[0] // 3 * 2)
                    self.helper.adb.touch_swipe2((self.helper.viewport[0] // 2,
                                                  self.helper.viewport[1] - 50), (1, 1), 10)
                if last_ops == cur_ops:
                    logger.error(f'apply room {room} fail, rest ops: {ops}')
                    break
                else:
                    last_ops = cur_ops
                    cur_ops = set()
            if scroll_flag:
                logger.info(f'scroll back to the begin...')
                last_ops = set()
                while True:
                    op_infos = self.get_all_op_on_screen()
                    cur_ops = set([i['op_name'] for i in op_infos])
                    move = random.randint(self.helper.viewport[0] // 4, self.helper.viewport[0] // 3)
                    self.__swipe_screen(move, 50, self.helper.viewport[0] // 3 * 2, swipe_time=random.randint(100, 300))
                    time.sleep(0.5)
                    if last_ops == cur_ops:
                        break
                    # print(last_ops, cur_ops)
                    last_ops = cur_ops
            self.tap_confirm()
            self.tap_back()
            if not ops:
                logger.info(f'apply room {room} success!')

    def goto_building(self):
        vw, vh = self.vw, self.vh
        self.helper.back_to_main()
        self.helper.tap_rect((100 * vw - 47.083 * vh, 80.278 * vh, 100 * vw - 21.806 * vh, 93.750 * vh))
        time.sleep(5)


if __name__ == '__main__':
    # AutoShiftAddOn().dump_current_shift(save_file='shift_test_cache.json', choose_room={'b105'})
    # AutoShiftAddOn().apply_shift('shift_test_cache.json')
    # AutoShiftAddOn().dump_current_shift('shift2_cache.json', exclude_room={'control_room', 'b105', 'b305', 'b401'})
    AutoShiftAddOn().apply_shift('shift2_cache.json')
    # AutoShiftAddOn().get_all_op_on_screen()
    # AutoShiftAddOn().tap_clear()
