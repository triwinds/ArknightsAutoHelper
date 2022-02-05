import os
import re
import string
import time
from functools import lru_cache

import cv2
import numpy as np
from cnocr import NUMBERS

import config
import imgreco
from Arknights.helper import logger
from addons.base import BaseAddOn
from addons.common_cache import load_game_data
from imgreco.ocr.ppocr import ocr_for_single_line, ocr_and_correct
from ppocronnx.predict_system import TextSystem


character_cache_file = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'character_cache.json')
screenshot_root = config.SCREEN_SHOOT_SAVE_PATH
ppocr = TextSystem()


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


def get_ticket(screenshot):
    item = ''.join(ocr_for_single_line(254-screenshot[661:684, 513:586],
                                       cand_alphabet=string.digits + string.punctuation))
    item = re.sub(r'[^0-9]', '', item)[:-1]
    return item


def show_img(img):
    cv2.imshow('test', img)
    cv2.waitKey()


def get_name(pil_screen):
    vw, vh = imgreco.util.get_vwvh(pil_screen.size)
    rect = tuple(map(int, (100*vw-24.722*vh, 71.111*vh, 100*vw-1.806*vh, 73.889*vh)))
    tag_img = cv2.cvtColor(np.asarray(pil_screen.crop(rect)), cv2.COLOR_BGR2RGB)
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


def get_op_name(pil_screen):
    cv_screen = cv2.cvtColor(np.asarray(pil_screen), cv2.COLOR_BGR2RGB)
    res = get_name(pil_screen)
    if res:
        return res
    return get_name2(cv_screen)


def crop_to_white(tag_img):
    gray_tag = cv2.cvtColor(tag_img, cv2.COLOR_RGB2GRAY)
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
    vw, vh = imgreco.util.get_vwvh(pil_screen.size)
    rect = tuple(map(int, (100 * vw - 24.722 * vh, 71.111 * vh, 100 * vw - 1.806 * vh, 73.889 * vh)))
    tag_img = cv2.cvtColor(np.asarray(pil_screen.crop(rect)), cv2.COLOR_BGR2RGB)
    # show_img(tag_img)
    tag_img = crop_to_white(tag_img)
    # tag_img = cv2.resize(tag_img, (0, 0), fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    # show_img(tag_img)
    res = ppocr.ocr_lines([tag_img])[0]
    print(res)
    res = res[0]
    logger.debug('get_name3: %s' % res)
    if '的信物' in res:
        return res[0:res.index('的信物')]
    return None


def test():
    from PIL import Image
    correct = 0
    correct2 = 0
    file_list = os.listdir('../../screenshot/recruit')
    diff_list = []
    for filename in file_list:
        screen = Image.open(f'../../screenshot/recruit/{filename}')
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


class AutoRecruitAddOn(BaseAddOn):
    def __init__(self, helper=None):
        super().__init__(helper)
        self.min_rarity = 0.1

    def run(self, times=0):
        self.auto_recruit(times)

    def clear_refresh(self):
        self.helper.replay_custom_record('goto_hr_page')
        used_slot = []
        for _ in range(4):
            current_slot = self.choose_slot(used_slot)
            if current_slot == -1:
                return
            op_res, rect_map = self.helper.recruit_with_rect()
            while not op_res[0][2] > self.min_rarity:
                if self.refresh_hr_tags():
                    op_res, rect_map = self.helper.recruit_with_rect()
                else:
                    return
            if op_res[0][2] > self.min_rarity:
                self.helper.replay_custom_record('tap_back')
                logger.info(f'存在高级标签组合 {op_res[0][0]}, 跳过.')
                if current_slot == 4:
                    return

    def hire_all(self):
        logger.info('===公招收菜')
        if not os.path.exists(f'{screenshot_root}/recruit'):
            os.mkdir(f'{screenshot_root}/recruit')
        if self.helper.try_replay_record('goto_hr_page'):
            for _ in range(4):
                if not self.helper.try_replay_record('hire_ops'):
                    return
                screen = self.helper.adb.screenshot()
                op_name = get_op_name(screen)
                img_filename = f'{screenshot_root}/recruit/{int(time.time())}-{op_name}.png'
                screen.save(img_filename)
                logger.info(f'获得干员: {op_name}, 截图保存至: {img_filename}')
                self.click((1223, 45), 2)

    def choose_slot(self, used_slot):
        for tag_slot in range(4):
            current_slot = tag_slot + 1
            if current_slot in used_slot:
                continue
            try:
                self.helper.replay_custom_record('tap_hire%d' % current_slot, quiet=True)
                used_slot.append(current_slot)
                logger.info(f'使用 {current_slot} 号招募位')
                return current_slot
            except RuntimeError:
                used_slot.append(current_slot)
        return -1

    def refresh_hr_tags(self):
        try:
            self.helper.replay_custom_record('refresh_hr_tags', quiet=True)
            logger.info('刷新成功')
            return True
        except RuntimeError:
            logger.info('刷新失败')
            return False

    def auto_recruit(self, hire_num):
        self.helper.replay_custom_record('goto_hr_page')

        used_slot = []

        for k in range(hire_num):
            current_slot = self.choose_slot(used_slot)
            if current_slot == -1:
                logger.error('无空闲招募位, 结束招募.')
                return
            cv_screen = pil2cv(self.helper.adb.screenshot())
            # 检测公招券道具数量
            ticket = get_ticket(cv_screen)
            logger.info('剩余公招许可：%s' % ticket)
            if ticket == '0':
                logger.info('无可用公招许可, 停止招募')
                return
            op_res, rect_map = self.helper.recruit_with_rect()

            while not op_res[0][2] > self.min_rarity:
                if self.refresh_hr_tags():
                    op_res, rect_map = self.helper.recruit_with_rect()
                else:
                    break
            rarity = op_res[0][2]
            tags_choose = op_res[0][0] if rarity > self.min_rarity else []
            logger.info(f"选择标签: {tags_choose}")
            # 增加时长
            if 0 < rarity < 1:
                self.helper.replay_custom_record('set_3h50m')
            else:
                self.click((466, 286), 0)
            if rarity > 1:
                logger.info(f"{current_slot} 号位置出现 4 星以上干员, 选择标签: {tags_choose}, 跳过此位置.")
                continue
            for tag in tags_choose:
                self.helper.tap_rect(rect_map[tag])
            # 招募
            self.click((977, 581), 2)


if __name__ == '__main__':
    # AutoRecruitAddOn().hire_all()
    # AutoRecruitAddOn().auto_recruit(4)
    AutoRecruitAddOn().clear_refresh()
    # test()
