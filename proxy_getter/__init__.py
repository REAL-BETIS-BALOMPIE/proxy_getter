import concurrent.futures
import datetime
import requests
import threading

PROXY_URL = 'https://api.proxyscrape.com/?request=getproxies&proxytype=http&country=all&ssl=all&anonymity=all&ssl=yes'

VERIFY_IP = "https://ipv4bot.whatismyipaddress.com"

USED_PROXIES = {}
LAST_PROXY_LIST = []
LAST_PROXY_LIST_DT = None

MIN_AVAILABILITY = 80
MIN_SPEED = 100
MAX_RESP = 4000
MIN_PROXY_TIME = 15 * 60

READING_LIST = False
LIST_LOCK = threading.Lock()
READING_LIST_LOCK = threading.Lock()
CONDITION_VAR = threading.Condition()


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
    global LAST_PROXY_LIST_DT, LAST_PROXY_LIST, READING_LIST

    _update_used_proxies()
    with CONDITION_VAR:
        READING_LIST_LOCK.acquire()
        is_being_read = READING_LIST
        READING_LIST_LOCK.release()
        if is_being_read is False:
            READING_LIST_LOCK.acquire()
            READING_LIST = True
            READING_LIST_LOCK.release()
            if force or (
                    not LAST_PROXY_LIST_DT or
                    (datetime.datetime.now() - LAST_PROXY_LIST_DT).total_seconds() > MIN_PROXY_TIME):
                response = requests.get(PROXY_URL)
                LIST_LOCK.acquire()
                LAST_PROXY_LIST = sorted(
                    filter(lambda x: ':' in x, response.content.decode('utf-8').split('\r\n')),
                    key=lambda x: 0 if x.split(':')[1] == '8080' else 1)
                LAST_PROXY_LIST_DT = datetime.datetime.now()
                LIST_LOCK.release()
            READING_LIST_LOCK.acquire()
            READING_LIST = False
            READING_LIST_LOCK.release()
            CONDITION_VAR.notifyAll()
        else:
            CONDITION_VAR.wait()
    return [proxy for proxy in LAST_PROXY_LIST if proxy not in USED_PROXIES.keys()]


def _update_used_proxies():
    LIST_LOCK.acquire()
    key_list = list(USED_PROXIES.keys())
    for proxy in key_list:
        if (datetime.datetime.now() - USED_PROXIES[proxy]).total_seconds() > MIN_PROXY_TIME:
            del USED_PROXIES[proxy]
    LIST_LOCK.release()


def _remove_proxy(proxy):
    LIST_LOCK.acquire()
    try:
        LAST_PROXY_LIST.remove(proxy)
    except ValueError:
        pass
    LIST_LOCK.release()


def check_proxy(proxy):
    proxies = {
      'https': f'https://{proxy}'
    }
    try:
        response = requests.get(VERIFY_IP, proxies=proxies, timeout=5)
        return response.content.decode('utf-8') == proxy.split(':')[0]
    except (
            requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout,
            requests.exceptions.SSLError, requests.Timeout, requests.ConnectionError
    ):
        return False


def get_proxy():
    _update_used_proxies()
    to_read = _read_proxies().copy()
    res = None
    for chunk in _chunks(to_read, 5):
        if res is not None:
            break
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            for proxy, status in executor.map(lambda e: (e, check_proxy(e)), chunk):
                if status:
                    if res is None:
                        res = proxy
                else:
                    _remove_proxy(proxy)
    if res is not None:
        USED_PROXIES[proxy] = datetime.datetime.now()
        return res
    _read_proxies(force=True)
    return get_proxy()
