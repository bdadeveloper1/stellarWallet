from flask import Flask, render_template, redirect, request, session, flash
from stellar_sdk import Server, Keypair, TransactionBuilder, Network #connect to horizon and transact on stellar blockchain
from stellar_sdk.exceptions import NotFoundError, BadRequestError, TypeError, Ed25519SecretSeedInvalidError #failed transaction handling
from dotenv import load_dotenv #load in environment variables/tokens
import requests #get data from stellar/coingecko/exchange rate servers
from datetime import datetime #convert unix timestamps to readable time formats
import time #get current system time
import os #access environment tokens
import cg #coingecko api for lumen price
import pandas as pd #storing dataframe of transaction list
import qrcode #generate qrcode for receiving address

#import environment variables/tokens
load_dotenv()
application = Flask(__name__)
application.secret_key = os.getenv("SECRET_KEY")
er_key = os.getenv("EXCHANGE_RATE_KEY")

#connect to stellar horizon server
server = Server(horizon_url="https://horizon.stellar.org")
#getting account info/balance
account_url = "https://horizon.stellar.org/accounts/"
#getting transaction history
tx_url = "https://horizon.stellar.org/transactions/"

#get exchange rates
er_url = "https://v6.exchangerate-api.com/v6/"+er_key+"/latest/USD"
try:
    rates = requests.get("https://v6.exchangerate-api.com/v6/"+er_key+"/latest/USD").json()
    last_update_unix = rates['time_last_update_unix']
    last_rate_update = datetime.strftime(datetime.fromtimestamp(last_update_unix), "%b %d %Y %H:%M")
    currency_dict = rates['conversion_rates']
    currency_list = list(rates['conversion_rates'].keys())
except:
    currency_list = []
    last_rate_update = "N/A"

#get transaction fee from server
try:
    base_fee = server.fetch_base_fee()
except:
    base_fee = 100

@application.route("/", methods=['GET', 'POST'])
def home():
    """homepage"""
    #print(session.keys())
    #get latest XLM price from coingecko
    #also shows time of last update
    usd_price = cg.get_price()

    #load user currency
    try:
        session['currency'] = request.form['currency']
    except:
        pass

    #clear session variables that may be leftover from filling out "send funds" page
    if 'recipient_address' in session:
        session.pop('recipient_address', None)
    if 'amount' in session:
        session.pop('amount', None)
    if 'memo' in session:
        session.pop('memo', None)

    if 'currency' in session:
        currency = session['currency']
        conversion_rate = currency_dict[currency]
    else:
        session['currency'] = 'USD'
        currency = session['currency']
        conversion_rate = 1


    #check if wallet is currently connected
    if 'pub_key' in session:
        logged_in = True
        session['user_balance'] = get_bal(session.get('pub_key'))
    else:
        logged_in = False
        session['user_balance'] = 0
    return render_template("main.html",
        pub_address = session.get("pub_key"),
        user_balance = float(session['user_balance']),
        fiat_equiv = str(round(float(session['user_balance'])*usd_price*conversion_rate, 2))+" "+currency,
        logged_in = logged_in)

def get_bal(address):
    """function to retrieve wallet ballance"""
    try:
        account_info = requests.get(account_url+address).json()
        balance = account_info['balances'][0]['balance']
        return balance
    except:
        return 0

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

@application.route("/import_result", methods=['POST', 'GET'])
def imported():
    """page for status after entering seed phrase"""
    if request.method == 'POST':
        #importing a seed phrase
        if 'phrase' in request.form:
            import_result = import_phrase(request.form['phrase'])
            if import_result == ValueError:
                return render_template("import_failed.html", err_msg = "Invalid mnemonic entered, please double check your input.")
            elif import_result == False:
                return render_template("import_failed.html", err_msg = "Seed phrases consist of 12 words, please try again.")
            else:
                return render_template("import_success.html")
        #importing a secret key
        elif 'secret_key' in request.form:
            import_result = import_key(request.form['secret_key'])
            if import_result == False:
                return render_template("import_failed.html", err_msg = "Invalid key entered, please double check your input.")
            else:
                return render_template("import_success.html")

def import_phrase(phrase):
    """helper function for 12 word seed phrase wallet recovery"""
    phrase = request.form['phrase']
    #verify the phrase is 12 words
    if len(phrase.split(" ")) == 12:
        try: #verify mnenomic is valid
            imported_key = Keypair.from_mnemonic_phrase(phrase)
        except ValueError as e:
            return e
        #set session variables once wallet is successfully imported
        session['priv_key'] = imported_key.secret
        session['pub_key'] = imported_key.public_key
        #try to retrieve the balance
        #if we can't (account has no transactions), we just set it to 0
        account_info = requests.get(account_url+session['pub_key']).json()
        try:
            session['user_balance'] = account_info['balances'][0]['balance']
        except KeyError:
            session['user_balance'] = 0
        return True
    else:
        return False

def import_key(secret_key):
    """helper function for importing wallets from a secret key"""
    secret_key = request.form['secret_key']
    try:
        imported_key = Keypair.from_secret(secret_key)
    except Ed25519SecretSeedInvalidError:
        return False
    session['priv_key'] = imported_key.secret
    session['pub_key'] = imported_key.public_key
    account_info = requests.get(account_url+session['pub_key']).json()
    try:
        session['user_balance'] = account_info['balances'][0]['balance']
    except KeyError:
        session['user_balance'] = 0
    return True

@application.route("/qr_code")
def qr_code():
    generate_qr_code()
    return render_template("qr_code.html",
    address = session['pub_key'])

def generate_qr_code():
    qr = qrcode.QRCode(version=1,
    box_size = 8,
    border = 1)
    qr.add_data(session['pub_key'])
    qr.make(fit = True)
    img = qr.make_image(fill_color = "black",
                        back_color = "white")
    img.save("static/qr_code.png")

def get_transactions(address):
    """function to get list of historical transactions for user address"""
    tx_df = pd.DataFrame()
    try:
        transactions = server.transactions().for_account(account_id = address).call()
    except BadRequestError:
        return tx_df
    tx_count = len(transactions['_embedded']['records'])
    tx_list = []
    tx_fee = [None for i in range(tx_count)]
    #append url of transaction operations to tx_list
    #this will let us get the info needed for every transaction
    for i in range(tx_count):
        hash = transactions['_embedded']['records'][i]['hash']
        tx_fee[i] = format(int(transactions['_embedded']['records'][i]['fee_charged'])/10000000, ".7f")
        tx_list.append(tx_url+hash+"/operations")
    tx_count = len(transactions['_embedded']['records'])

    tx_type = [None for i in range(tx_count)]
    tx_sender = [None for i in range(tx_count)]
    tx_recipient = [None for i in range(tx_count)]
    tx_amount = [None for i in range(tx_count)]
    tx_date = [None for i in range(tx_count)]

    for i, value in enumerate(tx_list):
        tx_info = requests.get(value).json()
        tx_data = tx_info['_embedded']['records'][0]
        #special rule for the first inbound transaction which is when the wallet is created
        if tx_data['type'] == "create_account":
            tx_type[i] = "Account Creation"
            tx_amount[i] = tx_data['starting_balance']
            tx_sender[i] = tx_data['funder']
            tx_recipient[i] = "You"
        #all other transactions
        else:
            tx_amount[i] = tx_data['amount']
            if tx_data['from'] == session['pub_key']:
                tx_sender[i] = "You"
                tx_type[i] = "Sent"
            else:
                tx_sender[i] = tx_data['from']
            if tx_data['to'] == session['pub_key']:
                tx_recipient[i] = "You"
                tx_type[i] = "Received"
            else:
                tx_recipient[i] = tx_data['to']
        tx_date[i] = tx_data['created_at']
    
    tx_date_reformat = [datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ") for date in tx_date]
    tx_date_reformat = [date.strftime("%b %d %Y, %H:%M:%S") for date in tx_date_reformat]
    tx_df = pd.DataFrame({"Date (UTC)": tx_date_reformat,
    "Type":tx_type, "Amount (XLM)": tx_amount, "Fee (XLM)":tx_fee,
    "Sender":tx_sender, "Recipient":tx_recipient})
    return tx_df

@application.route("/transactions")
def transactions():
    if 'pub_key' in session:
        tx_df = get_transactions(session['pub_key'])
        table = tx_df.to_html(index = False)
        if tx_df.empty:
            return render_template("transactions_list.html",
            address = session['pub_key'],
            err_msg = "Error: transaction history could not be retrieved.")
        return render_template("transactions_list.html",
        address = session['pub_key'],
        table = table)
    else:
        flash("Cannot retrieve transactions: there is no wallet connected.")
        return redirect("/")


@application.route("/send", methods = ['POST', 'GET'])
def send_money():
    """page for inputting data to send money"""
    return render_template("send.html",
    user_balance = float(get_bal(session.get('pub_key'))),
    fee = base_fee,
    fee_xlm = format(base_fee/10000000, ".7f"))

################################ todo #########################################
# disable send button after send button is clicked to avoid double spending
@application.route("/send_confirm", methods=['POST', 'GET'])
def send_confirm():
    """page for user to confirm that recipient address and amount
    are correct"""
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
    except NotFoundError as e:
        return e
    recipient_address = session.get('recipient_address')
    amount = session.get('amount')
    memo = session.get('memo')
    priv_key = session.get("priv_key")
    try:
        transaction = (
        TransactionBuilder(
            source_account = source_account,
            network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE,
            base_fee = base_fee,
            )
        .add_memo(memo)
        .append_payment_op(recipient_address, amount)
        .set_timeout(30) #transaction valid for next 30 seconds
        .build()
        )
        transaction.sign(priv_key) #required to verify transaction
    except (BadRequestError, NotFoundError, TypeError) as e:
        return e

    try:
        response = server.submit_transaction(transaction)
        transaction_info_url = "https://steexp.com/tx/"+response['hash']
        session['user_balance'] = get_bal(session.get('pub_key'))
        return transaction_info_url
    except (BadRequestError, NotFoundError, TypeError) as e:
        return e

@application.route("/send_result", methods = ['POST', 'GET'])
def send_result():
    """page to output confirmation with recipient address and amount.
    displays link to view transaction info on stellar explorer"""
    result = send_transaction()
    if result not in [BadRequestError, NotFoundError, TypeError]:
        return render_template("send_success.html",
        address = session.get('recipient_address'),
        amount = session.get('amount'),
        transaction_url = result)
    else:
        return render_template("send_failed.html",
        err_msg = result)

@application.route("/remove_wallet")
def remove_wallet():
    if "priv_key" in session:
        return render_template("remove_wallet.html")
    else:
        flash("Cannot remove wallet: there is no wallet connected.")
        return redirect("/")

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
    if "priv_key" in session:
        return render_template("view_secret.html",
        priv_key = session['priv_key'])
    else:
        flash("Cannot view secret key: there is no wallet connected.")
        return redirect("/")

def set_currency_session():
    session['currency'] = request.form['currency']

@application.route("/about")
def about():
    """page for info about stellar/the wallet"""
    return render_template("about.html")

@application.route("/where_to_buy")
def where_to_buy():
    """page for info on where to buy XLM"""
    return render_template("where_to_buy.html")

@application.route("/more", methods=['GET', 'POST'])
def more():
    """page for extra, less commonly accessed settings"""
    return render_template("more.html",
    currency_list = currency_list,
    last_er_update = last_rate_update)

# run the app
if __name__ == "__main__":
#    application.debug = True
    application.run()
