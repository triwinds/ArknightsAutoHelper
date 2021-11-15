from Arknights.helper import ArknightsHelper
from datetime import datetime, timezone, timedelta
import json
import os


task_cache_path = './jiaomie_cache.json'


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


def main():
    # 刷完就返回 false
    task_cache = load_cache()
    remain = task_cache['remain']
    if remain == 0:
        return False
    helper = ArknightsHelper()
    helper.replay_custom_record('goto_jiaomie')
    c_id, remain = helper.module_battle_slim(None, remain)
    task_cache['remain'] = remain
    save_cache(task_cache)
    return remain != 0


if __name__ == '__main__':
    main()
