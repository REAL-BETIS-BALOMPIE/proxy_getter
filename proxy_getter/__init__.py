import concurrent.futures
import datetime
import requests
import threading

from proxy_checker import ProxyChecker

PROXY_URL = 'https://api.proxyscrape.com/?request=getproxies&proxytype=http&country=all&ssl=all&anonymity=all&ssl=yes'

USED_PROXIES = {}
LAST_PROXY_LIST = []
LAST_PROXY_LIST_DT = None

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


def _read_proxies(force=False):
    global LAST_PROXY_LIST_DT, LAST_PROXY_LIST

    if REFRESH_ALLOWED.is_set():
        REFRESH_ALLOWED.clear()
        if force or (
                not LAST_PROXY_LIST_DT or
                (datetime.datetime.now() - LAST_PROXY_LIST_DT).total_seconds() > MIN_PROXY_TIME):
            response = requests.get(PROXY_URL)
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
    proxies = {
        'https': f'http://{proxy}'
    }
    valid = True
    checker = ProxyChecker()
    result_checker = checker.check_proxy(proxy)
    if result_checker == False:
        valid = False
    else:
        print(result_checker)
        try:
            response = requests.get(check_against, headers=HEADERS, proxies=proxies, timeout=(5, 10))
            valid &= response.status_code == 200
        except requests.exceptions.RequestException as e:
            print(e)
            valid = False
    return valid

def get_proxy(discard_proxy=None, check_against=None):
    if discard_proxy:
        _remove_proxy(discard_proxy)
    to_read = _get_used_proxies() + _read_proxies().copy()
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
        _read_proxies(force=True)
        return get_proxy()
    with LIST_LOCK:
        USED_PROXIES[res] = datetime.datetime.now()
    return res
