import requests
import bs4
from datetime import datetime, timezone, timedelta
import time
import common_task
from Arknights.helper import ArknightsHelper, logger
import os
import json


def is_in_event():
    resp = requests.get('http://prts.wiki/w/%E6%B4%BB%E5%8A%A8%E4%B8%80%E8%A7%88')
    soup = bs4.BeautifulSoup(resp.text, features='html.parser')
    event_tags = soup.find_all(text=' 进行中')
    return len(event_tags) > 0


def do_jiaomie():
    if os.path.exists('common_task_cache.json'):
        with open('common_task_cache.json', 'r') as f:
            task_info = json.load(f)
            task_info.get('time')


def clear_sanity():
    now = datetime.now().astimezone(tz=timezone(timedelta(hours=4)))
    wd = now.weekday()
    logger.info(f'clear_sanity, weekday: {wd}, time: {now}')
    items_day = {1, 2, 3, 4, 5, 6}

    if wd in items_day:
        clear_sanity_by_item()
    elif wd == 0:
        import start_jiaomie
        if not start_jiaomie.main():
            # 剿灭刷完就刷材料
            clear_sanity_by_item()


def clear_sanity_by_item():
    import config
    from addons.activity import ActivityAddOn
    try:
        stage = config.get('addons/activity/stage')
        repeat_times = config.get('addons/activity/repeat_times', 1000)
        addon = ActivityAddOn()
        addon.run(stage, repeat_times)
        return
    except Exception as e:
        print(e)

    from addons.grass_on_aog import GrassAddOn
    GrassAddOn().run()
    # helper = ArknightsHelper()
    # helper.module_battle('1-7')


def main():
    while True:
        # 重启 adb server, 以免产生奇怪的 bug
        os.system('adb kill-server')
        os.system('adb connect 127.0.0.1:7555')
        time.sleep(1)
        logger.info(f'run schedule at {datetime.now()}')
        clear_sanity()
        common_task.main()
        sleep_time = 3600 * 4
        # sleep_time = 1
        logger.info(f'Done, next round will run at {datetime.fromtimestamp(time.time() + sleep_time)}')
        time.sleep(sleep_time)


if __name__ == '__main__':
    main()
    # print(is_in_event())
