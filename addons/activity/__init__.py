import json
import logging
import os
import time
from functools import lru_cache

import cv2
import numpy as np
import textdistance

from addons.base import BaseAddOn
from addons.common_cache import load_game_data
from imgreco import common, main
from penguin_stats import arkplanner
from util.richlog import get_logger

detect_cache_file = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'detect_cache.json')
logger = logging
rich_logger = get_logger(__name__)


def get_stage_map(force_update=False):
    stages = load_game_data('stage_table', force_update)['stages']
    return process_stages(stages)


def process_stages(stages):
    stage_code_map = {}
    zone_linear_map = {}
    for stage_id in stages.keys():
        stage = stages[stage_id]
        if stage_code_map.get(stage['code']) is not None:
            continue
        stage_code_map[stage['code']] = stage
        l = zone_linear_map.get(stage['zoneId'], [])
        l.append(stage['code'])
        zone_linear_map[stage['zoneId']] = l
    return stage_code_map, zone_linear_map


def get_activities(force_update=False):
    return load_game_data('activity_table', force_update)['basicInfo']


def get_zones(force_update=False):
    return load_game_data('zone_table', force_update=force_update)['zones']


@lru_cache(1)
def get_ppocr():
    from ppocronnx.predict_system import TextSystem
    return TextSystem(unclip_ratio=2, box_thresh=0.3)


def get_stage(target_stage_code):
    stage_code_map, zone_linear_map = get_stage_map()
    if target_stage_code not in stage_code_map:
        stage_code_map, zone_linear_map = get_stage_map(force_update=True)
        if target_stage_code not in stage_code_map:
            raise RuntimeError(f'无效的关卡: {target_stage_code}')
    target_stage = stage_code_map[target_stage_code]
    # print(target_stage)
    if not check_activity_available(target_stage['zoneId']):
        # 活动复刻关卡的 zone id 会变化, 所以需要更新关卡信息
        stage_code_map, zone_linear_map = get_stage_map(force_update=True)
        if target_stage_code not in stage_code_map:
            raise RuntimeError(f'无效的关卡: {target_stage_code}')
        target_stage = stage_code_map[target_stage_code]
        # print(target_stage)
        if not check_activity_available(target_stage['zoneId']):
            raise RuntimeError('活动未开放')
    stage_linear = zone_linear_map.get(target_stage['zoneId'])
    # print(stage_linear)
    return target_stage, stage_linear


def get_zone_description(zone_id):
    activity_id = zone_id.split('_')[0]
    activities = get_activities()
    act_name = activities[activity_id]['name']
    zones = get_zones()
    zone_name = zones[zone_id]['zoneNameSecond']
    return f'{act_name} - {zone_name}'


def get_zone_name(zone_id):
    zones = get_zones()
    zone_name = zones[zone_id]['zoneNameSecond']
    return zone_name


def check_activity_available(zone_id):
    activity_id = zone_id.split('_')[0]
    activities = get_activities()
    if activity_id not in activities:
        activities = get_activities(force_update=True)
        if activity_id not in activities:
            return False
    cur_time = time.time()
    activity_info = activities[activity_id]
    return activity_info['startTime'] < cur_time < activity_info['endTime']


def update_cache():
    print('更新缓存...')
    get_zones(True)
    get_activities(True)
    get_stage_map(True)


def calc_box_center(box):
    box_y = box[:, 1]
    box_x = box[:, 0]
    return int(np.average(box_x)), int(np.average(box_y))


@lru_cache(1)
def load_detect_cache():
    """
    {
        'zoneId': [x, y]
    }
    if pos == [-1, -1] that means detect result is negative
    """
    if not os.path.exists(detect_cache_file):
        return {}
    with open(detect_cache_file, 'r') as f:
        return json.load(f)


def has_success_detect(zone_id):
    detect_cache = load_detect_cache()
    res = detect_cache.get(zone_id)
    return res != [-1, -1]


def get_detect_result_from_cache(zone_id):
    detect_cache = load_detect_cache()
    return detect_cache.get(zone_id)


def save_detect_result(zone_id, pos):
    detect_cache = load_detect_cache()
    detect_cache[zone_id] = pos
    with open(detect_cache_file, 'w') as f:
        json.dump(detect_cache, f)
        load_detect_cache.cache_clear()


class ActivityAddOn(BaseAddOn):
    def run(self, target_stage_code, repeat_times=1000, allow_extra_stage_icons=False):
        target_stage_code = target_stage_code.upper()
        target_stage, stage_linear = get_stage(target_stage_code)
        all_items_map = arkplanner.get_all_items_map()
        rewards = target_stage['stageDropInfo']['displayDetailRewards']
        # print(rewards)
        stage_drops = [all_items_map[reward["id"]]["name"] for reward in rewards
                       if reward["type"] == "MATERIAL" and reward["dropType"] == 2]
        logger.info(f"{target_stage['code']}: {target_stage['name']}, 重复次数: {repeat_times}, 关卡掉落: {stage_drops}")
        record_name = f'goto_{target_stage["stageType"]}_{target_stage["zoneId"]}'
        if has_success_detect(target_stage["zoneId"]) or not self.helper.try_replay_record(record_name):
            pos = self.try_detect_and_enter_zone(target_stage)
            if pos != [-1, -1]:
                self.try_find_and_tap_stage_by_ocr(target_stage['zoneId'], target_stage_code, stage_linear, pos)
            elif self.try_create_custom_record(target_stage, record_name):
                self.helper.replay_custom_record(record_name)
        return self.helper.module_battle_slim(target_stage_code, repeat_times)

    def try_create_custom_record(self, target_stage, record_name):
        wait_seconds_after_touch = 5
        c = input('是否录制相应操作记录(需要使用 MuMu 模拟器)[y/N]:').strip().lower()
        if c != 'y':
            return False
        update_cache()
        print('录制到进入活动关卡选择界面即可, 无需点击具体的某个关卡.')
        print(f'如果需要重新录制, 删除 custom_record 下的 {record_name} 文件夹即可.')
        print(f'请在点击后等待 {wait_seconds_after_touch} s , 待控制台出现 "继续..." 字样, 再进行下一次点击.')
        print(f'请在点击后等待 {wait_seconds_after_touch} s , 待控制台出现 "继续..." 字样, 再进行下一次点击.')
        print(f'请在点击后等待 {wait_seconds_after_touch} s , 待控制台出现 "继续..." 字样, 再进行下一次点击.')
        print(f'准备开始录制 {record_name}...')
        self.helper.create_custom_record(record_name, roi_size=32,
                                         description=get_zone_description(target_stage["zoneId"]),
                                         wait_seconds_after_touch=wait_seconds_after_touch)
        return True

    def try_find_and_tap_stage_by_ocr(self, zone_id, target_stage_code, stage_linear, pos):
        try:
            self.helper.find_and_tap_stage_by_ocr(None, target_stage_code, stage_linear)
            save_detect_result(zone_id, pos)
        except Exception as e:
            save_detect_result(zone_id, [-1, -1])
            raise e

    def open_current_activity(self):
        self.open_terminal()
        vh, vw = self.vh, self.vw
        activity_rect = (14.583 * vh, 71.944 * vh, 57.639 * vh, 83.333 * vh)
        logger.info('open current activity')
        self.helper.tap_rect(activity_rect)
        time.sleep(2)

    def open_terminal(self):
        self.helper.back_to_main()
        logger.info('open terminal')
        self.helper.tap_quadrilateral(main.get_ballte_corners(self.screenshot()))
        time.sleep(1)

    def try_detect_and_enter_zone(self, target_stage):
        detect_result = get_detect_result_from_cache(target_stage['zoneId'])
        if detect_result is None:
            update_cache()
            logger.info('No detect cache found, try to detect zone with ppocr.')
            self.open_current_activity()
            return self.detect_and_enter_zone(target_stage)
        elif detect_result != [-1, -1]:
            self.open_current_activity()
            logger.info(f'get detect result from cache: {detect_result}')
            self.click(detect_result, sleep_time=2, randomness=(2, 2))
        return detect_result

    def detect_and_enter_zone(self, target_stage):
        zone_name = get_zone_name(target_stage['zoneId'])
        logger.info(f"target zone name: {zone_name}")
        screen = common.convert_to_cv(self.helper.adb.screenshot())
        dbg_screen = screen.copy()
        ppocr = get_ppocr()
        boxed_results = ppocr.detect_and_ocr(screen)
        max_score = 0
        max_res = None
        for res in boxed_results:
            cv2.drawContours(dbg_screen, [np.asarray(res.box, dtype=np.int32)], 0, (0, 255, 0), 2)
            score = textdistance.sorensen(zone_name, res.ocr_text)
            if score > max_score:
                max_score = score
                max_res = res
        box_center = calc_box_center(max_res.box)
        cv2.drawContours(dbg_screen, [np.asarray(max_res.box, dtype=np.int32)], 0, (255, 0, 0), 2)
        cv2.circle(dbg_screen, box_center, 4, (0, 0, 255), -1)
        rich_logger.logimage(common.convert_to_pil(dbg_screen))
        rich_logger.logtext(f"result {max_res}, box_center: {box_center}")
        logger.info(f"result {max_res}, box_center: {box_center}")
        self.click(box_center, sleep_time=2, randomness=(2, 2))
        return box_center


if __name__ == '__main__':
    addon = ActivityAddOn()
    addon.run('tb-8', 0)
