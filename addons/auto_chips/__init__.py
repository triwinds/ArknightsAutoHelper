from addons.base import BaseAddOn
from addons.common_cache import load_game_data
from penguin_stats import arkplanner
import requests
from datetime import datetime
import json
import os
import config
from Arknights.helper import logger

# cache_key = '%Y-%m-%d'  # cache by day
cache_key = '%Y--%V'  # cache by week

inventory_cache_file = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'inventory_items_cache.json')


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


class AutoChips(BaseAddOn):
    def __init__(self, helper=None, minimum_storage=8):
        super().__init__(helper)
        self.minimum_storage = minimum_storage

    def run(self, **kwargs):
        my_chips = self.load_chips()
        if my_chips[0]['count'] < self.minimum_storage:
            my_chips = self.load_chips(True)
        if my_chips[0]['count'] >= self.minimum_storage:
            logger.info('All chips are exceed minimum storage, exit.')
            return
        chip = my_chips[0]
        item_stage_map = get_item_stage_map()
        stage_code = item_stage_map[chip['itemId']][0]
        logger.info(f"{chip['name']}, count: {chip['count']}, stage: {stage_code}")
        c_id, remain = self.helper.module_battle(stage_code, 1000)
        if remain != 1000:
            logger.info('recheck inventory...')
            self.load_chips(True)

    def load_inventory(self, force_update=False):
        if os.path.exists(inventory_cache_file) and not force_update:
            with open(inventory_cache_file, 'r') as f:
                data = json.load(f)
                if data['cacheTime'] == datetime.now().strftime(cache_key):
                    return data
        return self.update_inventory()

    def update_inventory(self):
        data = self.helper.get_inventory_items(True, False)
        data['cacheTime'] = datetime.now().strftime(cache_key)
        with open(inventory_cache_file, 'w') as f:
            json.dump(data, f)
        return data

    def load_chips(self, force_update=False):
        logger.info('加载库存信息...')
        my_items = self.load_inventory(force_update)
        my_chips = []
        all_items = arkplanner.get_all_items()
        for item in all_items:
            if item['itemType'] == 'CHIP':
                item['count'] = my_items.get(item['itemId'], 0)
                my_chips.append(item)
        return sorted(my_chips, key=lambda x: x['count'])


__all__ = ['AutoChips']

if __name__ == '__main__':
    addon = AutoChips()
    addon.run()
