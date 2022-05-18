import json
import os
import time
from datetime import datetime, timezone, timedelta

from Arknights.helper import ArknightsHelper, logger
from addons.auto_clues import AutoClueAddOn
from addons.auto_credit_store import AutoCreditStoreAddOn
from addons.auto_recruit import AutoRecruitAddOn
from addons.auto_shift import AutoShiftAddOn
from imgreco.item import update_net

task_cache_path = './common_task_cache.json'


def load_cache():
    task_cache = {
        'time': datetime.now().astimezone(tz=timezone(timedelta(hours=4))).strftime('%Y-%m-%d'),
        'get_credit': False,
        'auto_recruit': False,
        'auto_clue_time': 0
    }
    if os.path.exists(task_cache_path):
        with open(task_cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if data['time'] == task_cache['time']:
                task_cache = data
    return task_cache


def save_cache(task_cache):
    with open(task_cache_path, 'w', encoding='utf-8') as f:
        json.dump(task_cache, f, ensure_ascii=False)


def main():
    print('do common task.')
    update_net()
    task_cache = load_cache()
    helper = ArknightsHelper()

    logger.info('===基建收菜')
    helper.try_replay_record('get_building')
    logger.info('===清空无人机')
    AutoShiftAddOn(helper).clear_drones('b302')
    AutoRecruitAddOn(helper).hire_all()

    helper.clear_task()

    logger.info('===基建换班')
    AutoShiftAddOn(helper).run()

    auto_clue_time = task_cache.get('auto_clue_time', 0)
    if auto_clue_time + 6 * 3600 < time.time():
        logger.info('===收取并应用线索')
        AutoClueAddOn().run()
        task_cache['auto_clue_time'] = int(time.time())

    if not task_cache['get_credit']:
        logger.info('===收取并使用信用点')
        helper.replay_custom_record('get_credit')
        helper.replay_custom_record('get_store_credit')
        AutoCreditStoreAddOn(helper).run()
        task_cache['get_credit'] = True
    if not task_cache['auto_recruit']:
        logger.info('===自动公招')
        AutoRecruitAddOn(helper).auto_recruit(4)
        task_cache['auto_recruit'] = True
    else:
        logger.info('===清空公招刷新次数')
        AutoRecruitAddOn(helper).clear_refresh()
    save_cache(task_cache)


if __name__ == '__main__':
    main()
