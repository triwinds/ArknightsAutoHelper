import requests
import os
import json
from util.requests import retry_get

common_cache_config = {
    'character_table': {
        'type': 'net_json',
        'filename': 'character_table_cache.json',
        'url': 'https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/master/zh_CN/gamedata/excel/character_table.json',
        'encoding': 'utf-8'
    },
}
proxies = {
    "http": "http://localhost:7890",
    "https": "http://localhost:7890",
}
aog_cache_file = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'aog_cache.json')
aog_cache_key = '%Y--%V'


def get_cache_path(cache_file_name):
    return os.path.join(os.path.realpath(os.path.dirname(__file__)), cache_file_name)


def update_net_cache(cache_file_name, url):
    filepath = get_cache_path(cache_file_name)
    resp = requests.get(url, proxies=proxies)
    with open(filepath, 'wb') as f:
        f.write(resp.content)


def load_bytes_cache(cache_file_name, url, force_update=False):
    filepath = get_cache_path(cache_file_name)
    if not os.path.exists(filepath) or force_update:
        update_net_cache(cache_file_name, url)
    with open(filepath, 'rb') as f:
        return f.read()


def load_net_json_cache(cache_file_name, url, encoding='utf-8', force_update=False):
    filepath = get_cache_path(cache_file_name)
    if not os.path.exists(filepath) or force_update:
        update_net_cache(cache_file_name, url)
    with open(filepath, 'r', encoding=encoding) as f:
        return json.load(f)


def load_common_cache(cache_name, force_update=False):
    info = common_cache_config.get(cache_name)
    if not info:
        raise RuntimeError(f'[{cache_name}] is not exists.')
    if info['type'] == 'net_json':
        return load_net_json_cache(info['filename'], info['url'], info.get('encoding', 'utf-8'), force_update)
    raise RuntimeError(f"Unknown type {info['type']}.")


def load_game_data(table_name, force_update=False):
    url = f'https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/master/zh_CN/gamedata/excel/{table_name}.json'
    return load_net_json_cache(f'{table_name}_cache.json', url, 'utf-8', force_update)


def _update_aog_cache():
    from datetime import datetime
    resp = retry_get('https://arkonegraph.herokuapp.com/total/CN')
    data = {'aog': resp.json(), 'cacheTime': datetime.now().strftime(aog_cache_key)}
    with open(aog_cache_file, 'w') as f:
        json.dump(data, f)
    return data


def load_aog_cache(force_update=False):
    from datetime import datetime
    if os.path.exists(aog_cache_file) and not force_update:
        with open(aog_cache_file, 'r') as f:
            data = json.load(f)
            if data['cacheTime'] == datetime.now().strftime(aog_cache_key):
                return data
    return _update_aog_cache()
