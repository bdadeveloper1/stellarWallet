from flask import Flask, render_template, request
from stellar_sdk import Server, Keypair
import requests

application = Flask(__name__)
server = Server(horizon_url="https://horizon-testnet.stellar.org")
base_fee = server.fetch_base_fee()

# sample address for checking balance, sending XLM
# GBQMBYUUN2I6HLQ3OPDQRYI7AK5WWAXC6TDIG4UNWR7HHRPRJCHB6YBG

@application.route('/')
def home():
    return render_template("main.html")

@application.route('/create')
def create():
    return render_template("create.html")

@application.route('/create_phrase')
def create_phrase():
    new_keypair = new_wallet()
    phrase = new_keypair.generate_mnemonic_phrase()
    return render_template("create_phrase.html", phrase = phrase,
    public_key = new_keypair.public_key)

def new_wallet():
    keypair = Keypair.random()
    return keypair
    
@application.route("/check_balance", methods = ['POST', 'GET'])
def check_balance():
    return render_template("check_balance.html")
    
@application.route("/balance", methods = ['POST', 'GET'])
def balance():
    balance = get_bal(request.form['address'])
    return render_template("balance.html", balance=balance)

def get_bal(address):
    account_url_testnet = "https://horizon-testnet.stellar.org/accounts/"+str(address)
    account_url_mainnet = "https://horizon.stellar.org/accounts/"+str(address)
    try:
        account_info = requests.get(account_url_testnet).json()
    except:
        return "error"

    balance = account_info['balances'][0]['balance']
    return balance
    
@application.route("/send", methods = ['POST', 'GET'])
def send_money():
    return render_template("send.html")

def transact():
    pass

@application.route("/send_conf", methods = ['POST', 'GET'])
def send_conf():
    return render_template("send_conf.html"#, address=address, amount=amount
    )

@application.route("/about")
def about():
    return render_template("about.html")

# run the app
if __name__ == "__main__":
    # Setting debug to True enables debug output. This line should be
    # removed before deploying a production app.
 #   application.debug = True
    application.run(
        #ssl_context='adhoc'
        )