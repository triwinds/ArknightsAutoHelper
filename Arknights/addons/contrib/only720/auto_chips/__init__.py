from datetime import datetime, timezone, timedelta

import app
from Arknights.addons.contrib.common_cache import load_game_data, load_inventory
from automator import AddonBase
from penguin_stats import arkplanner

# cache_key = '%Y-%m-%d'  # cache by day
cache_key = '%Y--%V'  # cache by week

inventory_cache_file = app.cache_path.joinpath('inventory_items_cache.json')

chip_weekday = {
    '医疗': [0, 3, 4, 6],
    '重装': [0, 3, 4, 6],
    '术师': [0, 1, 4, 5],
    '狙击': [0, 1, 4, 5],
    '先锋': [2, 3, 5, 6],
    '辅助': [2, 3, 5, 6],
    '近卫': [1, 2, 5, 6],
    '特种': [1, 2, 5, 6]
}


def filter_today_chips(my_chips):
    res = []
    now = datetime.now().astimezone(tz=timezone(timedelta(hours=4)))
    wd = now.weekday()
    for chip in my_chips:
        chip_category = chip['name'][0:2]
        if wd in chip_weekday[chip_category]:
            res.append(chip)
    return res


def get_item_stage_map():
    res = {}
    stage_table = load_game_data('stage_table')['stages']
    for stage_id in stage_table:
        stage_info = stage_table[stage_id]
        drops = stage_info['stageDropInfo'].get('displayRewards')
        if drops:
            for drop in drops:
                if drop['type'] in {'MATERIAL', 'CHIP'}:
                    stages = res.get(drop['id']) or []
                    stages.append(stage_info['code'])
                    res[drop['id']] = stages
    return res


class AutoChips(AddonBase):
    def __init__(self, helper):
        super().__init__(helper)

    def run(self, minimum_storage=8):
        my_chips = self.load_chips()
        my_chips = filter_today_chips(my_chips)
        if my_chips[0]['count'] >= minimum_storage:
            self.logger.info('All chips are exceed minimum storage, exit.')
            return
        else:
            my_chips = self.load_chips(True)
            my_chips = filter_today_chips(my_chips)
        chip = my_chips[0]
        item_stage_map = get_item_stage_map()
        stage_code = item_stage_map[chip['itemId']][0]
        self.logger.info(f"{chip['name']}, count: {chip['count']}, stage: {stage_code}")
        from Arknights.addons.stage_navigator import StageNavigator
        c_id, remain = self.addon(StageNavigator).navigate_and_combat(stage_code, 1000)
        if remain != 1000:
            self.logger.info('recheck inventory...')
            self.load_chips(True)

    def load_chips(self, force_update=False):
        my_items = load_inventory(self.helper, force_update, cache_key=cache_key)
        my_chips = []
        all_items = arkplanner.get_all_items()
        for item in all_items:
            if item['itemType'] == 'CHIP':
                item['count'] = my_items.get(item['itemId'], 0)
                my_chips.append(item)
        my_chips = sorted(my_chips, key=lambda x: x['count'])
        self.logger.info(f"my chips: {[(x['name'], x['count']) for x in my_chips]}")
        return my_chips


__all__ = ['AutoChips']

if __name__ == '__main__':
    from Arknights.configure_launcher import helper
    helper.addon(AutoChips).run()
