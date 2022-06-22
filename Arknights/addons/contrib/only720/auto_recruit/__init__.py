import logging
import os
import string
import time
from functools import lru_cache

import cv2
import numpy as np

import app
import imgreco
from Arknights.addons.contrib.common_cache import load_game_data
from Arknights.addons.contrib.only720.old_base import OldMixin
from Arknights.addons.record import RecordAddon
from Arknights.addons.recruit import RecruitAddon
from imgreco.ocr.ppocr import ocr_for_single_line, ocr_and_correct
from imgreco.ppocr_utils import get_ppocr
from imgreco.stage_ocr import do_tag_ocr
from util import cvimage

screenshot_root = app.screenshot_path.joinpath('recruit')
logger = logging.getLogger(__file__)


@lru_cache(1)
def get_character_name_map():
    en2cn = {}
    cn2en = {}
    character_table = load_game_data('character_table')
    for cid, info in character_table.items():
        en2cn[info['appellation'].upper()] = info['name']
        cn2en[info['name']] = info['appellation'].upper()
    return en2cn, cn2en


def pil2cv(pil_img):
    cv_img = np.asarray(pil_img)
    return cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)


def show_img(img):
    cv2.imshow('test', img)
    cv2.waitKey()


def get_name(screen):
    vw, vh = imgreco.common.get_vwvh(screen.size)
    rect = tuple(map(int, (100*vw-24.722*vh, 71.111*vh, 100*vw-1.806*vh, 73.889*vh)))
    tag_img = screen.crop(rect).array
    # show_img(tag_img)
    tag_img = crop_to_white(tag_img)
    # show_img(tag_img)
    res = ocr_for_single_line(tag_img)
    res = ''.join(res).strip()
    logger.debug('get_name: %s' % res)
    if res.endswith('的信物'):
        return res[:-3]
    return None


def get_name2(cv_screen):
    # ocr english name on middle screen
    en2cn, cn2en = get_character_name_map()
    name_tag = cv_screen[567:601, 367:975]
    # name_tag = cv2.cvtColor(name_tag, cv2.COLOR_RGB2GRAY)
    # name_tag[name_tag < 140] = 0
    # name_tag = cv2.cvtColor(name_tag, cv2.COLOR_GRAY2RGB)
    # show_img(name_tag)
    cand_alphabet = string.digits + string.ascii_uppercase + '-'
    en_name = ocr_and_correct(name_tag, en2cn, cand_alphabet=cand_alphabet, log_level=20)
    logger.debug('get_name2: %s' % en_name)
    return en2cn.get(en_name)


def get_op_name(screen):
    cv_screen = screen.array
    res = get_name(screen)
    if res:
        return res
    return get_name2(cv_screen)


def crop_to_white(tag_img):
    gray_tag = cv2.cvtColor(tag_img, cv2.COLOR_BGR2GRAY)
    gray_tag[gray_tag < 170] = 0
    # show_img(gray_tag)
    h, w = gray_tag.shape
    for x in range(w):
        has_black = False
        for y in range(h):
            if gray_tag[y][x] == 0:
                has_black = True
                break
        if not has_black:
            return tag_img[0:h, x:w]
    return tag_img


def get_name3(pil_screen):
    vw, vh = imgreco.common.get_vwvh(pil_screen.size)
    rect = tuple(map(int, (100 * vw - 24.722 * vh, 71.111 * vh, 100 * vw - 1.806 * vh, 73.889 * vh)))
    tag_img = cv2.cvtColor(np.asarray(pil_screen.crop(rect)), cv2.COLOR_BGR2RGB)
    # show_img(tag_img)
    tag_img = crop_to_white(tag_img)
    # tag_img = cv2.resize(tag_img, (0, 0), fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    # show_img(tag_img)
    from imgreco.ppocr_utils import get_ppocr
    res = get_ppocr().ocr_lines([tag_img])[0]
    print(res)
    res = res[0]
    logger.debug('get_name3: %s' % res)
    if '的信物' in res:
        return res[0:res.index('的信物')]
    return None


def test():
    correct = 0
    correct2 = 0
    file_list = os.listdir(screenshot_root)
    diff_list = []
    for filename in file_list:
        from util import cvimage
        screen = cvimage.open(screenshot_root.joinpath(filename))
        cv_screen = cv2.cvtColor(np.asarray(screen), cv2.COLOR_BGR2RGB)
        print(filename)
        real_name = get_name(screen)
        test_name = get_name2(cv_screen)
        ppocr_name = get_name3(screen)
        print(real_name, test_name, ppocr_name)
        if real_name == test_name:
            correct += 1
            print('==============')
        else:
            print('--------------')
        correct2 += 1 if real_name == ppocr_name else 0
        if real_name != ppocr_name:
            diff_list.append(f'{filename}---{ppocr_name}')
    print(f'{correct}/{len(file_list)}, {correct/len(file_list)}')
    print(f'{correct2}/{len(file_list)}, {correct2 / len(file_list)}')
    print(diff_list)


def ocr_rect(screen, rect, thresh=None):
    tag = screen.crop(rect)
    if thresh is not None:
        tag_array = cv2.threshold(tag.convert('L').array, thresh, 255, cv2.THRESH_BINARY)[1]
        tag = cvimage.fromarray(tag_array, 'L').convert('BGR')
    return get_ppocr().ocr_single_line(tag.array)


class AutoRecruitAddOn(OldMixin):
    def __init__(self, helper):
        super().__init__(helper)
        self.min_rarity = 0.1

    def run(self, times=0):
        self.auto_recruit(times)

    def clear_refresh(self):
        logger.info('===清空公招刷新次数')
        self.goto_hr_page()
        used_slot = []
        for _ in range(4):
            current_slot = self.choose_slot(used_slot)
            if current_slot == -1:
                return
            op_res, rect_map = self.addon(RecruitAddon).recruit_with_rect()
            while not op_res[0][2] > self.min_rarity:
                if self.refresh_hr_tags():
                    op_res, rect_map = self.addon(RecruitAddon).recruit_with_rect()
                else:
                    return
            if op_res[0][2] > self.min_rarity:
                self.tap_back()
                logger.info(f'存在高级标签组合 {op_res[0][0]}, 跳过.')
                if current_slot == 4:
                    return

    def hire_all(self):
        logger.info('===公招收菜')
        if not os.path.exists(screenshot_root):
            os.mkdir(screenshot_root)
        if self.goto_hr_page():
            for _ in range(4):
                if not self.addon(RecordAddon).try_replay_record('hire_ops', quiet=True):
                    return
                screen = self.screenshot()
                op_name = get_op_name(screen)
                img_filename = screenshot_root.joinpath(f'{int(time.time())}-{op_name}.png')
                screen.save(img_filename)
                logger.info(f'获得干员: {op_name}, 截图保存至: {img_filename}')
                self.tap_point((1223, 45), 2)

    def choose_slot(self, used_slot):
        for tag_slot in range(4):
            current_slot = tag_slot + 1
            if current_slot in used_slot:
                continue
            try:
                self.addon(RecordAddon).replay_custom_record('tap_hire%d' % current_slot, quiet=True)
                used_slot.append(current_slot)
                logger.info(f'使用 {current_slot} 号招募位')
                return current_slot
            except RuntimeError:
                used_slot.append(current_slot)
        return -1

    def refresh_hr_tags(self):
        try:
            self.addon(RecordAddon).replay_custom_record('refresh_hr_tags', quiet=True)
            logger.info('刷新成功')
            return True
        except RuntimeError:
            logger.info('刷新失败')
            return False

    def tap_back(self):
        self.tap_rect(imgreco.common.get_nav_button_back_rect(self.viewport), post_delay=2)

    def get_ticket(self):
        gray_screen, scale = self.gray_screenshot()
        ticket_tag = gray_screen[26:51, 832:874]
        ticket_tag = cv2.threshold(ticket_tag, 143, 255, cv2.THRESH_BINARY)[1]
        # show_img(ticket_tag)
        return do_tag_ocr(ticket_tag, noise_size=1)

    def goto_hr_page(self):
        if not self.check_is_in_position():
            return self.addon(RecordAddon).try_replay_record('goto_hr_page')
        return True

    def auto_recruit(self, hire_num):
        logger.info('===自动公招')
        self.goto_hr_page()
        used_slot = []

        for k in range(hire_num):
            current_slot = self.choose_slot(used_slot)
            if current_slot == -1:
                logger.error('无空闲招募位, 结束招募.')
                return
            # 检测公招券道具数量
            ticket = self.get_ticket()
            logger.info('剩余公招许可：%s' % ticket)
            if ticket == '0':
                logger.info('无可用公招许可, 停止招募')
                return
            op_res, rect_map = self.addon(RecruitAddon).recruit_with_rect()

            while not op_res[0][2] > self.min_rarity:
                if self.refresh_hr_tags():
                    op_res, rect_map = self.addon(RecruitAddon).recruit_with_rect()
                else:
                    break
            rarity = op_res[0][2]
            tags_choose = op_res[0][0] if rarity > self.min_rarity else []
            logger.info(f"选择标签: {tags_choose}")
            # 增加时长
            if 0 < rarity < 1:
                self.addon(RecordAddon).replay_custom_record('set_3h50m')
            else:
                self.tap_point((466, 286), 0)
            if rarity > 1:
                self.tap_back()
                logger.info(f"{current_slot} 号位置出现 4 星以上干员, 选择标签: {tags_choose}, 跳过此位置.")
                continue
            for tag in tags_choose:
                self.tap_rect(rect_map[tag])
            # 招募
            self.tap_point((977, 581), 2)

    def check_is_in_position(self):
        vh, vw = self.vh, self.vw
        screen = self.screenshot()
        res = ocr_rect(screen, (16.667 * vh, 16.389 * vh, 34.028 * vh, 22.083 * vh), 200)
        if res and '公开招募' in res[0]:
            return True
        res = ocr_rect(screen, (16.953*vw, 28.472*vh, 26.719*vw, 34.167*vh))
        if res and '招募时限' in res[0]:
            self.tap_back()
            return True
        return False


if __name__ == '__main__':
    from Arknights.configure_launcher import helper

    print(helper.addon(AutoRecruitAddOn).goto_hr_page())
    print(helper.addon(AutoRecruitAddOn).get_ticket())

    helper.addon(AutoRecruitAddOn).clear_refresh()
    helper.addon(AutoRecruitAddOn).auto_recruit(1)
    # helper.addon(AutoRecruitAddOn).hire_all()
