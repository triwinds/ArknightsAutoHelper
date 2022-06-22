import json
import os
import time

import cv2
import numpy as np

from Arknights.addons.contrib.base import crop_cv_by_rect
from Arknights.addons.contrib.only720.old_base import _find_template2, OldMixin
from imgreco.common import crop_image_only_outside, has_color, test_color
from imgreco.ocr.ppocr import ocr as ppocr
from imgreco.stage_ocr import predict_char_images, crop_char_img


def open_img(name, mode=cv2.IMREAD_GRAYSCALE):
    filepath = os.path.join(os.path.realpath(os.path.dirname(__file__)), name)
    return cv2.imread(filepath, mode)


def show_img(img):
    cv2.imshow('test', img)
    cv2.waitKey()


def load_clue_slot_img():
    res = {}
    for i in range(1, 8):
        slot_img = open_img('c%d.png' % i)
        slot_img = cv2.threshold(slot_img, 254, 255, cv2.THRESH_BINARY)[1]
        # show_img(slot_img)
        res[i] = slot_img
    return res


small_img = open_img('small.png')
large_img = open_img('large.png')
no_clue_img = open_img('no_clue.png')
no_giveable_clue_img = open_img('no_giveable_clue.png')
clock_img = open_img('clock.png')
receive_img = open_img('receive.png')
clue_slot_imgs = load_clue_slot_img()
my_daily_clue_img = open_img('my_daily_clue.png')
friend_clue_img = open_img('friend_clue.png')
give_clue_img = open_img('give_clue.png')
send_clue_img = open_img('send_clue.png')
unlock_clue_img = open_img('unlock_clue.png')

friend_record_file = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'friend_record.json')


def load_friend_record():
    if not os.path.exists(friend_record_file):
        open(friend_record_file, 'w', encoding='utf-8').close()
        return {}
    with open(friend_record_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_friend_record(friend_record):
    with open(friend_record_file, 'w', encoding='utf-8') as f:
        json.dump(friend_record, f, ensure_ascii=False, indent=4)


def add_receive_record(friend_name):
    records = load_friend_record()
    record = records.get(friend_name, {'receive': 0, 'send': 0})
    record['receive'] += 1
    records[friend_name] = record
    save_friend_record(records)


def _has_new_clue(pos, cv_screen, scale):
    red = (34, 0, 125)
    fix_pos = int(30 * scale)
    sx, sy = pos[0] + fix_pos, pos[1] - fix_pos + 10
    test_img = cv_screen[sy:sy + fix_pos, sx:sx + fix_pos]
    # cv2.imshow('test', test_img)
    # cv2.waitKey()
    return has_color(test_img, red)


def crop_friend_name_tag(cv_screen, scale, send_button_pos):
    l = int((send_button_pos[0] - 585) * scale)
    r = int((send_button_pos[0] - 333) * scale)
    t = int((send_button_pos[1] + 18) * scale)
    b = int((send_button_pos[1] + 46) * scale)
    return cv_screen[t:b, l:r]


def reco_friend_name(cv_screen, scale, send_button_pos):
    name_tag = crop_friend_name_tag(cv_screen, scale, send_button_pos)
    # show_img(name_tag)
    ocr_res = ppocr.ocr_single_line(name_tag)
    if ocr_res:
        return ocr_res[0].strip()


def crop_friend_clue_tag(cv_screen, scale, send_button_pos):
    l = int((send_button_pos[0] - 324) * scale)
    r = int((send_button_pos[0] - 24) * scale)
    t = int((send_button_pos[1] + 26) * scale)
    b = int((send_button_pos[1] + 66) * scale)
    return cv_screen[t:b, l:r]


def scan_friend_empty_clues(cv_screen, scale, send_button_pos):
    clue_tag = crop_friend_clue_tag(cv_screen, scale, send_button_pos)
    clue_tag = cv2.cvtColor(clue_tag, cv2.COLOR_RGB2GRAY)
    clue_tag = cv2.threshold(clue_tag, 150, 255, cv2.THRESH_BINARY)[1]
    # show_img(clue_tag)
    h, w = clue_tag.shape[:2]
    char_imgs = crop_char_img(clue_tag)
    final_char_imgs = []
    for img in char_imgs:
        ch, cw = img.shape[:2]
        if ch < h:
            # show_img(img)
            final_char_imgs.append(img)
    owned_clues = predict_char_images(final_char_imgs)
    res = []
    for i in range(1, 8):
        if str(i) not in owned_clues:
            res.append(i)
    return res


def scan_send_button(gray_screen, scale):
    result = cv2.matchTemplate(gray_screen, send_clue_img, cv2.TM_CCOEFF_NORMED)
    loc = np.where(result >= 0.9)
    tag_set = set()
    tag_set2 = set()
    res = []
    for pt in zip(*loc[::-1]):
        pos_key = (pt[0] // 100, pt[1] // 100)
        pos_key2 = (int(pt[0] / 100 + 0.5), int(pt[1] / 100 + 0.5))
        if pos_key in tag_set or pos_key2 in tag_set2:
            continue
        tag_set.add(pos_key)
        tag_set2.add(pos_key2)
        res.append((int(pt[0]*scale), int(pt[1]*scale)))
    return res


def is_friend_latest_login_in_today(cv_screen, scale, send_button_pos):
    blue = (169, 117, 0)
    x = int((send_button_pos[0] - 355) * scale)
    y = int((send_button_pos[1] + 100) * scale)
    return test_color(cv_screen[y][x], blue)


class AutoClueAddOn(OldMixin):
    def __init__(self, helper=None):
        super().__init__(helper)

    def run(self, **kwargs):
        self.goto_meeting_room()
        self.open_clue_view()
        self.get_my_clues()
        self.get_friend_clues()
        self.apply_all_clues()
        self.richlogger.logimage(self.screenshot())
        if self.try_unlock_clue():
            self.richlogger.logimage(self.screenshot())
            self.open_clue_view()
            self.apply_all_clues()

    def get_my_clues(self):
        gray_screen, cv_screen, scale = self.screenshot2()
        max_val, max_loc = _find_template2(my_daily_clue_img, gray_screen, scale)
        if max_val > 0.7:
            if _has_new_clue(max_loc, cv_screen, scale):
                max_loc = (max_loc[0] + 15, max_loc[1] + 20)
                self.tap_point(max_loc)
                max_val, max_loc = self._find_template(receive_img, center_pos=True)
                if max_val > 0.9:
                    self.logger.info('receive my daily clue.')
                    self.tap_point(max_loc, post_delay=2)

    def get_friend_clues(self):
        gray_screen, cv_screen, scale = self.screenshot2()
        max_val, max_loc = _find_template2(friend_clue_img, gray_screen, scale)
        if max_val < 0.7 or not _has_new_clue(max_loc, cv_screen, scale):
            return
        self.logger.info('receive friend clues.')
        max_loc = (max_loc[0] + 15, max_loc[1] + 20)
        self.tap_point(max_loc, post_delay=2)
        vh, vw = self.vh, self.vw
        self.tap_rect((100 * vw - 51.111 * vh, 91.806 * vh, 100 * vw - 10.139 * vh, 98.611 * vh))
        self.delay(1)
        self.tap_bottom()

    def try_unlock_clue(self):
        max_val, max_loc = self._find_template(unlock_clue_img, True)
        if max_val < 0.98:
            return False
        self.logger.info('all clues are ready, unlock clue.')
        self.tap_point(max_loc, post_delay=3)
        return True

    def goto_meeting_room(self):
        from Arknights.addons.record import RecordAddon
        self.addon(RecordAddon).replay_custom_record('goto_meeting_room')
        max_val, max_loc = self._find_template(small_img)
        if max_val < 0.7:
            self.tap_back()

    def apply_all_clues(self):
        empty_slots = self.scan_empty_slot()
        first_scan = True
        for k in empty_slots:
            self.logger.info(f'try to apply clue [{k}].')
            pos = empty_slots[k]
            self.tap_point(pos)
            self.apply_clue()
            if first_scan:
                first_scan = False
                empty_slots = self.scan_empty_slot()
            else:
                self.delay(1)

    def open_clue_view(self):
        max_val, max_loc = self._find_template(small_img)
        if max_val > 0.7:
            self.tap_point(max_loc, 2)
        else:
            raise RuntimeError('Fail to open clue view')

    def apply_clue(self):
        vh, vw = self.vh, self.vw
        gray_screen, scale = self.gray_screenshot()
        clues_area_img = crop_cv_by_rect(gray_screen, (100 * vw - 60.000 * vh, 0, self.width, self.height))
        max_val, max_loc = _find_template2(no_clue_img, clues_area_img, scale)
        if max_val > 0.7:
            self.logger.info('No available clue found!')
            # self.tap_bottom()
            return
        max_val, max_loc = _find_template2(clock_img, clues_area_img, scale)
        if max_val > 0.7:
            pos = (int(max_loc[0] + 100 * vw - 60.000 * vh + 30), int(max_loc[1] - 60))
            self.logger.info(f'use time limit clue {pos}.')
            self.tap_point(pos)
            name_tag = ~clues_area_img[max_loc[1] - 80: max_loc[1] - 55, max_loc[0] + 174: max_loc[0] + 374]
            # cv2.rectangle(clues_area_img, (max_loc[0] + 174, max_loc[1] - 80), (max_loc[0] + 374, max_loc[1] - 55), 0, 2)
            name_tag = crop_image_only_outside(name_tag, name_tag)
            clue_send_from = ppocr.ocr_single_line(cv2.cvtColor(name_tag, cv2.COLOR_GRAY2RGB))[0]
            self.logger.info(f'use clue send from {clue_send_from}.')
            add_receive_record(clue_send_from)
        else:
            self.logger.info('use first clue.')
            vh, vw = self.vh, self.vw
            self.tap_rect((100 * vw - 57.083 * vh, 26.389 * vh, 100 * vw - 24.722 * vh, 41.667 * vh))
        # self.tap_bottom()
        self.delay(2)

    def scan_empty_slot(self, only_available_slot=True):
        gray_screen, cv_screen, scale = self.screenshot2()
        thresh_screen = cv2.threshold(gray_screen, 254, 255, cv2.THRESH_BINARY)[1]
        # show_img(thresh_screen)
        res = {}
        for k in clue_slot_imgs:
            img = clue_slot_imgs[k]
            max_val, max_loc = _find_template2(img, thresh_screen, scale)
            # print(k, max_val)
            if max_val > 0.9:
                res[k] = max_loc
        if not only_available_slot or not res:
            self.logger.info(f"empty clues: {res}")
            return res
        fin_res = {}
        for k in res:
            if self._has_available_clue(res[k], cv_screen):
                fin_res[k] = res[k]
        self.logger.info(f"available empty clues: {fin_res}")
        return fin_res

    def _has_available_clue(self, pos, cv_screen):
        scale = self.height / 720
        fix_pos = int(61 * scale)
        sx, sy = pos[0] + fix_pos, pos[1] - fix_pos
        test_img = cv_screen[sy:sy+fix_pos-20, sx:sx+fix_pos-20]
        orange = (1, 104, 255)
        # cv2.imshow('test', test_img)
        # cv2.waitKey()
        return has_color(test_img, orange)

    def tap_back(self):
        vh, vw = self.vh, self.vw
        self.tap_rect((3.889 * vh, 2.500 * vh, 18.889 * vh, 8.333 * vh))

    def tap_bottom(self):
        vh, vw = self.vh, self.vw
        self.tap_rect((16.389 * vh, 85.833 * vh, 104.861 * vh, 96.667 * vh))

    def screenshot2(self):
        screen = self.screenshot()
        gray_screen = screen.convert('L').array
        cv_screen = screen.array
        scale = self.height / 720
        if self.height != 720:
            gray_screen = cv2.resize(gray_screen, (int(self.width / scale), 720))
        return gray_screen, cv_screen, scale

    def send_clue(self):
        gray_screen, cv_screen, scale = self.screenshot2()
        send_button_pos = scan_send_button(gray_screen, scale)
        for pos in send_button_pos:
            friend_name = reco_friend_name(cv_screen, scale, pos)
            empty_clues = scan_friend_empty_clues(cv_screen, scale, pos)
            today_login = is_friend_latest_login_in_today(cv_screen, scale, pos)
            self.logger.info(f'{friend_name}({today_login}): {empty_clues}')


if __name__ == '__main__':
    from Arknights.configure_launcher import helper
    helper.addon(AutoClueAddOn).run()
