from flask import Flask, render_template, request, redirect, send_from_directory
import os
from stellar_sdk import Server
import requests

app = Flask(__name__)
server = Server(horizon_url="https://horizon-testnet.stellar.org")
base_fee = server.fetch_base_fee()

# sample address for checking balance, sending XLM
# GBQMBYUUN2I6HLQ3OPDQRYI7AK5WWAXC6TDIG4UNWR7HHRPRJCHB6YBG

@app.route('/')
def home():
    return render_template("main.html")

@app.route('/create')
def create():
    return render_template("create.html")
    
@app.route("/check_balance", methods = ['POST', 'GET'])
def check_balance():
    return render_template("check_balance.html")
    
@app.route("/balance", methods = ['POST', 'GET'])
def balance():
    balance = get_bal(request.form['address'])
    return render_template("balance.html", balance=balance)

def get_bal(address):
    account_url_testnet = "https://horizon-testnet.stellar.org/accounts/"+str(address)
    account_url_mainnet = "https://horizon.stellar.org/accounts/"+str(address)
    try:
        account_info = requests.get(account_url_testnet).json()
    except requests.exceptions.SSLError as e:
        return e

    balance = account_info['balances'][0]['balance']
    return balance
    #print("account has {} XLM".format(balance))
    
@app.route("/send", methods = ['POST', 'GET'])
def send_money():
    return render_template("send.html")

def transact():
    pass

@app.route("/confirmation", methods = ['POST', 'GET'])
def confirmation():
    return render_template("confirmation.html"#, address=address, amount=amount
    )

@app.route("/about")
def about():
    return render_template("about.html")

# run the app
if __name__ == "__main__":
    # Setting debug to True enables debug output. This line should be
    # removed before deploying a production app.
    app.debug = True
    app.run(ssl_context='adhoc')