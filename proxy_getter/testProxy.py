from proxy_getter import get_proxy, check_proxy

TM_DOMAIN = 'https://www.transfermarkt.es'

proxy = None
proxy = get_proxy(discard_proxy=proxy, check_against=TM_DOMAIN)
print("Proxy Encontrado: " + proxy)