import json
import re
import string
import time
import os
import requests
from functools import lru_cache

import cv2
import numpy as np
from cnocr import NUMBERS

import imgreco
from Arknights.helper import logger
from imgreco.ocr.cnocr import cn_ocr
from addons.base import BaseAddOn
import config

ocr = cn_ocr


character_cache_file = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'character_cache.json')
screenshot_root = config.SCREEN_SHOOT_SAVE_PATH


@lru_cache(1)
def get_character_name_map():
    en2cn = {}
    cn2en = {}
    character_table = get_character_table()
    for cid, info in character_table.items():
        en2cn[info['appellation'].upper()] = info['name']
        cn2en[info['name']] = info['appellation'].upper()
    return en2cn, cn2en


def get_character_table():
    if os.path.exists(character_cache_file):
        with open(character_cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return download_character_table()


def download_character_table():
    print('下载角色信息...')
    resp = requests.get('https://raw.fastgit.org/Kengxxiao/ArknightsGameData/master/zh_CN'
                        '/gamedata/excel/character_table.json')
    data = resp.json()
    with open(character_cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def pil2cv(pil_img):
    cv_img = np.asarray(pil_img)
    return cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)


# https://github.com/shuangluoxss/ArkAutoHR/blob/ce9c15bf7353a7a143787c93ec7c351ae6bd6fd9/auto_hr.py
def str_similiar(s1, s2):
    """
    返回字符串s1与字符串s2的相似程度
    """
    score = 0
    max_len = min(len(s1), len(s2))
    if s1[:max_len] == s2[:max_len]:
        score += 100 ** max_len
    for sub_str_len in range(1, 6):  # 字串长度1至5
        s1_set = set([s1[i:i + sub_str_len] for i in range(len(s1) + 1 - sub_str_len)])
        s2_set = set([s2[i:i + sub_str_len] for i in range(len(s2) + 1 - sub_str_len)])
        score += len(s1_set & s2_set) * 10 ** sub_str_len
    return score


def search_in_list(s_list, x, min_score=500):
    """
    寻找字符串数组s_list中与字符串x最接近的字符串并返回。若相似度不高或有两个字符串相似度相同，返回None
    """
    tmp_list = [(s, str_similiar(s, x)) for s in s_list]
    tmp_list.sort(key=lambda x: x[1], reverse=True)
    if tmp_list[0][1] > max(min_score, tmp_list[1][1]):
        return tmp_list[0]
    else:
        return None, 0


def get_ticket(screenshot):
    ocr.set_cand_alphabet(cand_alphabet=NUMBERS)
    item = ''.join(ocr.ocr_for_single_line(254-screenshot[661:684, 513:586]))
    ocr.set_cand_alphabet(cand_alphabet=None)
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
    res = ocr.ocr_for_single_line(tag_img)
    res = ''.join(res).strip()
    logger.debug('get_name: %s' % res)
    if res.endswith('的信物'):
        return res[:-3]
    return None


def get_name2(cv_screen):
    en2cn, cn2en = get_character_name_map()
    name_tag = cv_screen[567:601, 367:975]
    name_tag = cv2.cvtColor(name_tag, cv2.COLOR_RGB2GRAY)
    name_tag[name_tag < 140] = 0
    ocr.set_cand_alphabet(string.digits + string.ascii_uppercase + '-')
    res = ocr.ocr_for_single_line(name_tag)
    ocr.set_cand_alphabet(None)
    res = ''.join(res)
    logger.debug('get_name2: %s' % res)
    en_name, score = search_in_list(en2cn, res)
    logger.debug(f'en_name, score: {en_name, score}')
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


def test():
    from PIL import Image
    screen = Image.open('../../screenshot/recruit/1629463955-暗索.png')
    cv_screen = cv2.cvtColor(np.asarray(screen), cv2.COLOR_BGR2RGB)
    print(get_name(screen))
    print(get_name2(cv_screen))


class AutoRecruitAddOn(BaseAddOn):
    def run(self, times=0):
        self.auto_recruit(times)

    def click(self, pos, sleep=0.5):
        self.helper.adb.touch_tap(pos)
        time.sleep(sleep)

    def clear_refresh(self):
        self.helper.replay_custom_record('goto_hr_page')
        used_slot = []
        for _ in range(4):
            current_slot = self.choose_slot(used_slot)
            op_res, rect_map = self.helper.recruit_with_rect()
            while not op_res[0][2] > 0:
                if self.refresh_hr_tags():
                    op_res, rect_map = self.helper.recruit_with_rect()
                else:
                    return
            if op_res[0][2] > 0:
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
                self.helper.adb.touch_tap((1223, 45))

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

            while not op_res[0][2] > 0:
                if self.refresh_hr_tags():
                    op_res, rect_map = self.helper.recruit_with_rect()
                else:
                    break
            # 增加时长
            self.click((466, 286), 0)
            rarity = op_res[0][2]
            tags_choose = op_res[0][0] if rarity > 0 else []
            logger.info(f"选择标签: {tags_choose}")
            if rarity > 1:
                logger.info(f"{current_slot} 号位置出现 4 星以上干员, 选择标签: {tags_choose}, 跳过此位置.")
                continue
            for tag in tags_choose:
                self.helper.tap_rect(rect_map[tag])
            # 招募
            self.click((977, 581), 2)


if __name__ == '__main__':
    # AutoRecruitAddOn().hire_all()

    test()
