import time

from Arknights.helper import ArknightsHelper, logger
import json
import os

from datetime import datetime, timezone, timedelta
from addons.auto_recruit import AutoRecruitAddOn, get_op_name
from addons.auto_credit_store import AutoCreditStoreAddOn

task_cache_path = './common_task_cache.json'


def load_cache():
    task_cache = {
        'time': datetime.now().astimezone(tz=timezone(timedelta(hours=4))).strftime('%Y-%m-%d'),
        'get_credit': False,
        'auto_recruit': False
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
    task_cache = load_cache()
    helper = ArknightsHelper()

    logger.info('===基建收菜')
    helper.try_replay_record('get_building')
    logger.info('===清空无人机')
    helper.try_replay_record('clear_drones')
    AutoRecruitAddOn(helper).hire_all()
    logger.info('===清空无人机')

    helper.clear_task()

    if not task_cache['get_credit']:
        logger.info('===收取并使用信用点')
        helper.replay_custom_record('get_credit')
        AutoCreditStoreAddOn(helper).run()
        task_cache['get_credit'] = True
    if not task_cache['auto_recruit']:
        logger.info('===自动公招')
        AutoRecruitAddOn(helper).auto_recruit(3)
        task_cache['auto_recruit'] = True
    else:
        logger.info('===清空公招刷新次数')
        AutoRecruitAddOn(helper).clear_refresh()
    save_cache(task_cache)


if __name__ == '__main__':
    main()
    # hire_all(ArknightsHelper())
