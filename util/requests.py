import requests


proxies = {
  "http": "http://localhost:7890",
  "https": "http://localhost:7890",
}


def retry_get(url, max_retry=5, timeout=30):
    c = 0
    ex = None
    while c < max_retry:
        try:
            return requests.get(url, timeout=timeout, proxies=proxies)
        except Exception as e:
            c += 1
            ex = e
    raise ex
