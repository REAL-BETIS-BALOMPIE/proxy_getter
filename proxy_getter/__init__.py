import concurrent.futures
import datetime
import requests
import threading

PROXY_URL = 'https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies'

USED_PROXIES = {}
LAST_PROXY_LIST = []
LAST_PROXY_LIST_DT = None
LAST_PROXY_URL = PROXY_URL

MIN_PROXY_TIME = 15 * 60

LIST_LOCK = threading.Lock()
REFRESH_ALLOWED = threading.Event()

REFRESH_ALLOWED.set()

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:65.0) Gecko/20100101 Firefox/65.0'}


def _chunks(lst, n):
    chunk = []
    for i in lst:
        chunk.append(i)

        if len(chunk) == n:
            y_chunk = chunk
            chunk = []
            yield y_chunk
    yield chunk


def _read_proxies(force=False, api_url=PROXY_URL):
    global LAST_PROXY_LIST_DT, LAST_PROXY_LIST, LAST_PROXY_URL, USED_PROXIES

    if LAST_PROXY_URL != api_url:
        with LIST_LOCK:
            LAST_PROXY_LIST_DT = None
            LAST_PROXY_LIST = []
            USED_PROXIES = {}
            LAST_PROXY_URL = api_url
            force = True

    if REFRESH_ALLOWED.is_set():
        REFRESH_ALLOWED.clear()
        if force or (
                not LAST_PROXY_LIST_DT or
                (datetime.datetime.now() - LAST_PROXY_LIST_DT).total_seconds() > MIN_PROXY_TIME):
            response = requests.get(api_url)
            with LIST_LOCK:
                LAST_PROXY_LIST = sorted(
                    filter(lambda x: ':' in x, response.content.decode('utf-8').split('\r\n')),
                    key=lambda x: 0 if x.split(':')[1] == '8080' else 1)
                LAST_PROXY_LIST_DT = datetime.datetime.now()
        REFRESH_ALLOWED.set()
    else:
        REFRESH_ALLOWED.wait()
    with LIST_LOCK:
        res = [proxy for proxy in LAST_PROXY_LIST if proxy not in USED_PROXIES.keys()]
    return res


def _remove_proxy(proxy):
    with LIST_LOCK:
        if proxy in USED_PROXIES.keys():
            del USED_PROXIES[proxy]

        try:
            LAST_PROXY_LIST.remove(proxy)
        except ValueError:
            pass


def _get_used_proxies():
    with LIST_LOCK:
        res = sorted(USED_PROXIES.keys(), key=lambda x: USED_PROXIES[x], reverse=True)
    return res


def check_proxy(proxy, check_against=None):
    splits = proxy.split('://')
    if len(splits) > 1:
        protocol = splits[0]
        url = splits[1]
    else:
        protocol = 'https'
        url = proxy

    proxies = {
        protocol: url,
    }

    try:
        response = requests.get(check_against, headers=HEADERS, proxies=proxies, timeout=(5, 10))
        valid = response.status_code == 200
    except requests.exceptions.RequestException as e:
        valid = False
    return valid


def get_proxy(discard_proxy=None, check_against=None, api_url=PROXY_URL):
    if discard_proxy:
        _remove_proxy(discard_proxy)
    to_read = _get_used_proxies() + _read_proxies(api_url=api_url).copy()
    res = None
    for chunk in _chunks(to_read, 5):
        if res is not None:
            break
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            for proxy, status in executor.map(lambda e: (e, check_proxy(e, check_against=check_against)), chunk):
                if status:
                    if res is None:
                        res = proxy
                else:
                    _remove_proxy(proxy)
    if res is None:
        _read_proxies(force=True, api_url=api_url)
        return get_proxy()
    with LIST_LOCK:
        USED_PROXIES[res] = datetime.datetime.now()
    return res
