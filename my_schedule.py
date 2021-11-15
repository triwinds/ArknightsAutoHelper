import requests
import bs4
from datetime import datetime, timezone, timedelta
import time
import common_task
from Arknights.helper import ArknightsHelper, logger
import os
import json
from apscheduler.schedulers.blocking import BlockingScheduler
import config
from imgreco.item import update_net
from addons.restart_mumu import restart_all
import traceback


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
        import jiaomie
        if not jiaomie.main():
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
    # helper.module_battle('9-18')


def send_by_tg_bot(chat_id, title, content):
    # @shadowfox_MsgCat_bot
    result = requests.post('https://msgcat.shadowfox.workers.dev/sendMsg',
                           json={'chatId': chat_id, 'title': title, 'content': content})
    return result


def do_works():
    # 重启 adb server, 以免产生奇怪的 bug
    try:
        os.system('adb kill-server')
        os.system('adb connect 127.0.0.1:7555')
        update_net()
        logger.info(f'run schedule at {datetime.now()}')
        clear_sanity()
        common_task.main()
        logger.info(f'finish at: {datetime.now()}')
        time.sleep(60)
    except Exception as e:
        send_by_tg_bot(config.get('notify/chat_id'), 'arh-fail', traceback.format_exc())
        raise e


def recruit():
    from addons.auto_recruit import AutoRecruitAddOn
    addon = AutoRecruitAddOn()
    addon.hire_all()
    addon.auto_recruit(4)


def main():
    do_works()
    scheduler = BlockingScheduler()
    scheduler.add_job(recruit, 'cron', day_of_week='0,1', hour='19', minute=0)
    scheduler.add_job(restart_all, 'cron', day='*/2', hour=4, minute=5)
    scheduler.add_job(do_works, 'cron', hour='*/4', minute=15)
    scheduler.start()


if __name__ == '__main__':
    main()
    # print(is_in_event())
