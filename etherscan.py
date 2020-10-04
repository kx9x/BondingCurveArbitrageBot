import json
import requests
import settings

def getAbi(address):
    endpoint = settings.ETHERSCAN_API_URL + '?module=contract&action=getabi&apikey={0}&address={1}'.format(settings.ETHERSCAN_API_KEY, address)
    res = requests.get(endpoint)
    return res.json()['result']
