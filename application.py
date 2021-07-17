from flask import Flask, render_template, redirect, request, session, flash
from flask.helpers import url_for
from stellar_sdk import Server, Keypair, TransactionBuilder, Network
from stellar_sdk.exceptions import NotFoundError, BadRequestError
import requests
from dotenv import load_dotenv
import os

load_dotenv()
application = Flask(__name__)
application.secret_key = "cb97eb2a6536f6838dbc7d049088f6cac425afc0" #os.getenv("SECRET_KEY")
server = Server(horizon_url="https://horizon.stellar.org")
base_fee = server.fetch_base_fee()

@application.route("/")
def home():
    """homepage"""
    #page for users with a connected wallet
    lumen_price = get_price()
    print(lumen_price)
    if "pub_key" in session:
        return render_template("main_logged_in.html", 
            pub_address = session.get("pub_key"),
            user_balance = session.get("user_balance"),
            lumen_price = lumen_price)
    #page for no wallet
    else:
        return render_template("main.html",
        lumen_price = lumen_price)

def get_price():
    try:
        lumen_price = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=stellar&vs_currencies=usd").json()
        return lumen_price['stellar']['usd']
    except:
        return "Cannot be retrieved"

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
        account_url = "https://horizon.stellar.org/accounts/"+str(session['pub_key'])
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
# 1.  prevent sending an amount of XLM that would result
# in a balance below the required amount
# 2. disable send button after send button is clicked to avoid double spending
# 3. prevent sending when address and amount are invalid
###############################################################################
@application.route("/send", methods = ['POST', 'GET'])
def send_money():
    """page for inputting data to send money"""
    return render_template("send.html",
    user_balance = session.get("user_balance"),
    fee = base_fee,
    fee_xlm = format(base_fee/10000000, ".7f"))

def send_transaction():
    """function to actually process and confirm transactions"""
    recipient_address = request.form['recipient_address']
    try:
        source_account = server.load_account(session.get("pub_key"))
    except NotFoundError:
        return False
    amount = request.form['amount']
    memo = request.form['memo']
    priv_key = session.get("priv_key")

    transaction = (
    TransactionBuilder(
        source_account = source_account,
        network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE,
        base_fee = base_fee,
        )
    .add_text_memo(memo)
    .append_payment_op(recipient_address, amount)
    .set_timeout(60) #transaction times out if unsuccessful after 1 minute
    .build()
    )
    transaction.sign(priv_key) #required to verify transaction
    try:
        response = server.submit_transaction(transaction)
        transaction_info_url = "https://steexp.com/tx/"+response['hash']
        session['user_balance'] = get_bal(session['pub_key'])
        return transaction_info_url
    except BadRequestError:
        return False

################################ todo #########################################
# add verification/confirmation page before transaction goes through
@application.route("/send_conf", methods = ['POST', 'GET'])
def send_conf():
    """page to output confirmation with recipient address and amount.
    displays link to view transaction info on stellar explorer"""
    transaction_url = send_transaction()
    if transaction_url != False:
        return render_template("send_success.html",
        address = request.form['recipient_address'],
        amount = request.form['amount'],
        transaction_url = transaction_url)
    else:
        err_msg = """The server could not process your transaction.<br />\
            Make sure you entered the recipient's address correctly and that you have enough Lumens.<br><br>\
            Additionally, the Stellar protocol requires users to maintain at least 1 XLM in their wallet."""
        return render_template("send_failed.html",
        err_msg = err_msg)


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

# run the app
if __name__ == "__main__":
#    application.debug = True
    application.run()
