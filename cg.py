# function for getting stellar price
# mostly just to keep the main application.py file shorter/cleaner.
import requests

def get_price():
    try:
        price = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=stellar&vs_currencies=usd").json()
        return price['stellar']['usd']
    except:
        return "Cannot be retrieved"