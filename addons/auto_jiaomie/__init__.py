import json
import logging
import os
from datetime import datetime, timezone, timedelta

import cv2

from addons.base import BaseAddOn
from imgreco.common import convert_to_cv
from imgreco.ocr.ppocr import ocr_for_single_line

task_cache_path = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'jiaomie_cache.json')
ticket_img_path = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'ticket.png')
ticket_img = cv2.imread(ticket_img_path, cv2.IMREAD_GRAYSCALE)


def load_cache():
    task_cache = {
        'week': datetime.now().astimezone(tz=timezone(timedelta(hours=4))).strftime('%Y-%W'),
        'remain': 5
    }
    if os.path.exists(task_cache_path):
        with open(task_cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if data['week'] == task_cache['week']:
                task_cache = data
    return task_cache


def save_cache(task_cache):
    with open(task_cache_path, 'w', encoding='utf-8') as f:
        json.dump(task_cache, f, ensure_ascii=False)


class AutoJiaomieAddOn(BaseAddOn):
    def __init__(self, helper=None):
        super().__init__(helper)

    def get_current_process(self):
        vh, vw = self.vh, self.vw
        screen = self.screenshot()
        roi = convert_to_cv(screen.crop((14.028 * vh, 88.472 * vh, 42.083 * vh, 93.889 * vh)))
        res = ocr_for_single_line(roi)
        logging.info(f'current process: {res}')
        return res

    def check_is_finish(self):
        current_process = self.get_current_process()
        arr = current_process.split('/')
        return len(arr) == 2 and arr[0] == arr[1]

    def start_jiaomie(self, times):
        while times != 0:
            if self.check_is_finish():
                logging.info('Not necessary to start jiaomie')
                return 0
            max_val, max_loc = self._find_template(ticket_img)
            if max_val > 0.9:
                if self.helper.try_replay_record('quick_jiaomie'):
                    times -= 1
                    continue
            c_id, remain = self.helper.module_battle_slim(None, 1)
            if remain == 0:
                times -= 1
            else:
                return times
        return 0

    def run(self):
        task_cache = load_cache()
        remain = task_cache['remain']
        if remain == 0:
            return False
        self.helper.replay_custom_record('goto_jiaomie')
        remain = self.start_jiaomie(remain)
        task_cache['remain'] = remain
        save_cache(task_cache)
        return remain != 0


if __name__ == '__main__':
    AutoJiaomieAddOn().run()
