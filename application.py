from flask import Flask, render_template, redirect, request, session, flash
from stellar_sdk import Server, Keypair, TransactionBuilder, Network #connect to horizon and transact on stellar blockchain
from stellar_sdk.exceptions import NotFoundError, BadRequestError #failed transaction handling
from dotenv import load_dotenv #load in environment variables/tokens
import requests #get data from stellar/coingecko servers
import time #get current system time
from datetime import datetime #convert unix timestamps to readable time formats
import os #access environment tokens
import cg #coingecko api for lumen price

#import environment variables/tokens
load_dotenv()
application = Flask(__name__)
application.secret_key = os.getenv("SECRET_KEY")

#connect to stellar horizon server
server = Server(horizon_url="https://horizon.stellar.org")

#get transaction fee from server
base_fee = server.fetch_base_fee()

@application.route("/")
def home():
    """homepage"""
    #get latest XLM price from coingecko
    #also shows time of last update
    usd_price = cg.get_price()
    update_time = datetime.fromtimestamp(time.time())
    update_time = update_time.strftime("%b %d %H:%M:%S EST")

    #clear sending info just in case
    session.pop('recipient_address', None)
    session.pop('amount', None)
    session.pop('memo', None)

    #page for users with a connected wallet
    if "pub_key" in session:
        user_balance = get_bal(session.get('pub_key'))
        return render_template("main_logged_in.html", 
            pub_address = session.get("pub_key"),
            user_balance = float(user_balance),
            price = "$"+str(usd_price),
            usd_equiv = "~$"+str(round(float(user_balance)*usd_price, 4)),
            update_time = update_time)

    #page for no wallet
    else:
        return render_template("main.html",
        price = "$"+str(usd_price),
        update_time = update_time)

@application.route("/create")
def create():
    """page for explaining seed phrase before creating wallet"""
    return render_template("create.html")

@application.route("/create_result")
def create_result():
    """page for displaying seed phrase"""
    
    phrase = Keypair.generate_mnemonic_phrase()
    return render_template("create_success.html",
    phrase = phrase)

@application.route("/import_wallet", methods=['POST', 'GET'])
def import_wallet():
   """page for importing a new wallet using 12 word seed phrase"""
   return render_template("import_wallet.html")

@application.route("/imported", methods=['POST', 'get'])
def imported():
    """page for status after entering seed phrase"""
    phrase = request.form['phrase']
    pl = len(phrase.split(" ")) # get phrase length, split into words
    if pl == 12: #check that there are twelve words
        try: #verify mnenomic is valid
            imported_key = Keypair.from_mnemonic_phrase(phrase)
        except ValueError:
            err_msg = "Invalid mnemonic entered, please double check your input."
            return render_template("import_failed.html", err_msg=err_msg)
        session['priv_key'] = imported_key.secret
        session['pub_key'] = imported_key.public_key
        #accounts do not "exist" on the blockchain if unfunded
        #therefore, we will try to retrieve the balance
        #if we can't, we just set it to 0
        account_url = "https://horizon.stellar.org/accounts/"+str(session.get('pub_key'))
        account_info = requests.get(account_url).json()
        try:
            session['user_balance'] = account_info['balances'][0]['balance']
        except KeyError:
            session['user_balance'] = 0
        return render_template("import_success.html")
    else:
        err_msg = "Seed phrases are 12 words long. Please try again."
        return render_template("import_failed.html", err_msg=err_msg)

@application.route("/check_balance", methods = ['post', 'get'])
def check_balance():
    """page asks user to input an address"""
    return render_template("check_balance.html")

def get_bal(address):
    """function to retrieve wallet ballance from horizon"""
    account_url = "https://horizon.stellar.org/accounts/"+str(address)
    try:
        account_info = requests.get(account_url).json()
        balance = account_info['balances'][0]['balance']
        return balance
    except:
        return 0

@application.route("/balance", methods = ['post', 'get'])
def balance():
    """page displays balance of previously input address"""
    balance = get_bal(request.form['address'])
    if balance == 0:
        return render_template("balance_failed.html")
    else:
        return render_template("balance.html", balance = balance)

################################ todo #########################################
# 1. disable send button after send button is clicked to avoid double spending
# 2. disable send button when address and amount are invalid
###############################################################################
@application.route("/send", methods = ['POST', 'GET'])
def send_money():
    """page for inputting data to send money"""
    return render_template("send.html",
    user_balance = float(get_bal(session.get('pub_key'))),
    fee = base_fee,
    fee_xlm = format(base_fee/10000000, ".7f"))

@application.route("/send_confirm", methods=['POST', 'GET'])
def send_confirm():
    session['recipient_address'] = request.form['recipient_address']
    session['memo'] = request.form['memo']
    session['amount'] = request.form['amount']
    return render_template("send_confirm.html",
    address = session.get('recipient_address'),
    memo = session.get('memo'),
    amount = session.get('amount'))

def send_transaction():
    """function to actually process and confirm transactions"""
    try:
        source_account = server.load_account(session.get("pub_key"))
    except NotFoundError:
        return False
    recipient_address = session.get('recipient_address')
    amount = session.get('amount')
    memo = session.get('memo')
    priv_key = session.get("priv_key")

    transaction = (
    TransactionBuilder(
        source_account = source_account,
        network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE,
        base_fee = base_fee,
        )
    .add_text_memo(memo)
    .append_payment_op(recipient_address, amount)
    .set_timeout(30) #transaction valid for next 30 seconds
    .build()
    )
    transaction.sign(priv_key) #required to verify transaction
    try:
        response = server.submit_transaction(transaction)
        transaction_info_url = "https://steexp.com/tx/"+response['hash']
        session['user_balance'] = get_bal(session.get('pub_key'))
        return transaction_info_url
    except BadRequestError as e:
        return e

################################ todo #########################################
# add verification/confirmation page before transaction goes through
@application.route("/send_result", methods = ['POST', 'GET'])
def send_result():
    """page to output confirmation with recipient address and amount.
    displays link to view transaction info on stellar explorer"""
    result = send_transaction()
    if result != BadRequestError:
        return render_template("send_success.html",
        address = session.get('recipient_address'),
        amount = session.get('amount'),
        transaction_url = result)
    else:
        return render_template("send_failed.html",
        err_msg = result)

@application.route("/remove_wallet")
def remove_wallet():
    if "priv_key" not in session:
        flash("Cannot remove wallet: there is no wallet connected.")
        return redirect("/")
    else:
        return render_template("remove_wallet.html")

@application.route("/remove_conf")
def remove_conf():
    if "priv_key" in session:
        session.pop("priv_key", None)
    if "pub_key" in session:    
        session.pop("pub_key", None)
    if "balance" in session:
        session.pop("balance", None)
    return render_template("remove_conf.html")

@application.route("/view_secret")
def view_secret():
    if "priv_key" not in session:
        flash("Cannot view secret key: there is no wallet connected.")
        return redirect("/")
    else:
        return render_template("view_secret.html",
        priv_key = session.get("priv_key"))

@application.route("/about")
def about():
    """page for info about stellar/the wallet"""
    return render_template("about.html")

@application.route("/where_to_buy")
def where_to_buy():
    """page for info on where to buy XLM"""
    return render_template("where_to_buy.html")

@application.route("/more")
def more():
    """page for extra, less commonly accessed settings"""
    return render_template("more.html")

# run the app
if __name__ == "__main__":
    application.run(debug = False)
