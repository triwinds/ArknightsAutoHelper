import json
import logging
import os
from datetime import datetime, timezone, timedelta

import cv2

import app
from Arknights.addons.contrib.only720.old_base import OldMixin
from imgreco.ocr.ppocr import ocr_for_single_line

task_cache_path = app.cache_path.joinpath('jiaomie_cache.json')
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


class AutoJiaomieAddOn(OldMixin):
    def __init__(self, helper):
        super().__init__(helper)

    def get_current_process(self):
        vh, vw = self.vh, self.vw
        screen = self.screenshot()
        roi = screen.crop((14.028 * vh, 88.472 * vh, 42.083 * vh, 93.889 * vh)).array
        res = ocr_for_single_line(roi)
        logging.info(f'current process: {res}')
        return res

    def check_is_finish(self):
        current_process = self.get_current_process()
        arr = current_process.split('/')
        return len(arr) == 2 and arr[0] == arr[1]

    def start_jiaomie(self, times):
        from Arknights.addons.combat import CombatAddon
        while times != 0:
            oos = self.addon(CombatAddon).create_operation_once_statemachine('quick_jiaomie')
            if self.check_is_finish():
                logging.info('Not necessary to start jiaomie')
                return 0
            try:
                oos.prepare_operation()
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
            except StopIteration:
                logging.info('No more battle')
                return times
        return 0

    def run(self):
        task_cache = load_cache()
        remain = task_cache['remain']
        if remain == 0:
            return False
        from Arknights.addons.record import RecordAddon
        if self.addon(RecordAddon).try_replay_record('goto_jiaomie'):
            remain = self.start_jiaomie(remain)
        else:
            logging.info('No jiaomie item on todo list, skip.')
            remain = 0
        task_cache['remain'] = remain
        save_cache(task_cache)
        return remain != 0


if __name__ == '__main__':
    from Arknights.configure_launcher import helper
    helper.addon(AutoJiaomieAddOn).run()
