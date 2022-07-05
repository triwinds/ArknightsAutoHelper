import json
import logging
import os
from datetime import datetime, timezone, timedelta

import cv2

import app
from Arknights.addons.contrib.only720.old_base import OldMixin
from imgreco.ocr.ppocr import ocr_for_single_line
from imgreco.common import crop_image_only_outside

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
        roi = crop_image_only_outside(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), roi)
        res = ocr_for_single_line(roi).replace('O', '0')
        logging.info(f'current process: {res}')
        return res

    def check_is_finish(self):
        current_process = self.get_current_process()
        arr = current_process.split('/')
        return len(arr) == 2 and arr[0] == arr[1]

    def tap_start_operation(self):
        vh, vw = self.vh, self.vw
        self.tap_rect((100*vw-26.111*vh, 90.694*vh, 100*vw-8.333*vh, 94.861*vh), 2)

    def tap_confirm(self):
        res = self.match_roi('contrib/auto_jiaomie/confirm_quick_start')
        if res:
            self.logger.info('Confirm quick start')
            self.tap_rect(res.bbox, post_delay=12)
        # vh, vw = self.vh, self.vw
        # self.tap_rect((100*vw-26.111*vh, 90.694*vh, 100*vw-8.333*vh, 94.861*vh), 3)

    def start_jiaomie(self, times):
        from Arknights.addons.combat import CombatAddon
        addon = self.addon(CombatAddon)
        use_penguin_report = addon.use_penguin_report
        addon.use_penguin_report = False
        while times != 0:
            oos = addon.create_operation_once_statemachine(None)
            if self.check_is_finish():
                logging.info('No necessary to start jiaomie')
                addon.use_penguin_report = use_penguin_report
                return 0
            try:
                res = self.match_roi('contrib/auto_jiaomie/quick_start_available')
                if res:
                    self.logger.info('Quick start is available, use it.')
                    self.tap_rect(res.bbox, post_delay=2)
                smobj = oos.create_combat_session()
                recoresult, _ = oos.prepare_operation()
                smobj.prepare_reco = recoresult
                res = self.match_roi('contrib/auto_jiaomie/quick_start_ready')
                if res:
                    self.tap_start_operation()
                    self.tap_confirm()
                    self.wait_for_still_image()
                    oos.on_end_operation(smobj)
                    self.delay(5)
                    times -= 1
                    continue
                c_id, remain = addon.combat_on_current_stage(1)
                if remain == 0:
                    times -= 1
                else:
                    addon.use_penguin_report = use_penguin_report
                    return times
            except StopIteration:
                logging.info('No more battle')
                addon.use_penguin_report = use_penguin_report
                return times
        addon.use_penguin_report = use_penguin_report
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
    # helper.addon(AutoJiaomieAddOn).start_jiaomie(1)
