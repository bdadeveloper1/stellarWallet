from json import dump
from flask import Flask, render_template, redirect, request, session, flash
from stellar_sdk import Server, Keypair, TransactionBuilder, Network
from stellar_sdk.exceptions import NotFoundError
import requests

application = Flask(__name__)
application.secret_key = "wasdfghjkl"
server = Server(horizon_url="https://horizon.stellar.org")
base_fee = server.fetch_base_fee()

@application.route('/')
def home():
    """homepage"""
    #render logged in page if wallet is active
    if session.get('pub_key') != None:
        return render_template("main_logged_in.html",
        pub_address = session.get('pub_key'),
        pub_balance = session.get('user_balance'))
    #page for non logged in users
    else:
        return render_template("main.html")
        
  #  else:
   #     return render_template("main_logged_in.html",
    #    pub_address = session['pub_key'])

@application.route('/create')
def create():
    """page for explaining seed phrase before creating wallet"""
    return render_template("create.html")

@application.route('/create_result')
def create_result():
    """page for displaying seed phrase"""
    new_keypair = new_wallet()
    phrase = new_keypair.generate_mnemonic_phrase()
    #i assume this is the way to store the keys for the session
    session['priv_key'] = new_keypair.secret
    session['pub_key'] = new_keypair.public_key
    session['user_balance'] = get_bal(session['pub_key'])
    return render_template("create_success.html",
    phrase = phrase,
    pub_address = session.get('pub_key'),
    priv_address = session.get('priv_key'))

def new_wallet():
    """"function to create a new wallet"""
    return Keypair.random()

# to do: save user's wallet once it is imported
@application.route("/import_wallet", methods=['POST', 'GET'])
def import_wallet():
   """page for importing a new wallet using 12 word seed phrase"""
   return render_template("import_wallet.html")

@application.route('/imported', methods=['POST', 'GET'])
def imported():
    """page for status after entering seed phrase"""
    phrase = request.form['phrase']
    pl = len(phrase.split(" ")) # get phrase length, split into words
    if pl == 12: #check that there are twelve words
        try: #verify mnenomic is valid
            imported_key = Keypair.from_mnemonic_phrase(phrase)
        except ValueError:
            err_msg = "Invalid mnemonic, please check if the mnemonic is correct."
            return render_template("import_failed.html", err_msg=err_msg)
        session['priv_key'] = imported_key.secret
        session['pub_key'] = imported_key.public_key
        #fund public address if not funded
        #accounts do not "exist" on the blockchain if unfunded
        #try to get account info. if fails, fund with friendbot
        # account_url = "https://horizon-testnet.stellar.org/accounts/"+str(session['pub_key'])
        # try:
        #     account_info = requests.get(account_url).json()
        # except:
        #     print("exception #1 reached")
        #     requests.get(friendbot_url, params={"addr": session['pub_key']})
        #     account_info = requests.get(account_url).json()
        try:
            account_url = "https://horizon.stellar.org/accounts/"+str(session['pub_key'])
            account_info = requests.get(account_url).json()
            balance = account_info['balances'][0]['balance']
            session['balance'] = balance
        except KeyError:
            print("exception reached")
            return render_template("import_failed.html",
            err_msg = "Balance could not be retrived.")
        
        print("inside imported function\n"+session['pub_key']+"\n"+session['priv_key'])
        return render_template("import_success.html",
        balance=balance)
    else:
        err_msg = "Seed phrases are 12 words; {} words were entered.".format(pl)
        return render_template("import_failed.html", err_msg=err_msg)

@application.route("/check_balance", methods = ['POST', 'GET'])
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


@application.route("/balance", methods = ['POST', 'GET'])
def balance():
    """page displays balance of previously input address"""
    balance = get_bal(request.form['address'])
    if not balance:
        return render_template("balance_failed.html")
    else:
        return render_template("balance.html", balance=balance)

@application.route("/send", methods = ['POST', 'GET'])
def send():
    """page for inputting data to send money"""
    return render_template("send.html")

def transact():
    """function to actually process and confirm transactions"""
    recipient_address = request.form['recipient_address']
    try:
        source_account = server.load_account(session.get('pub_key'))
    except NotFoundError:
        return False
    amount = request.form['amount']
    priv_key = session.get('priv_key')
    memo = request.form['memo']
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
    response = server.submit_transaction(transaction)
    if response['successful']:
        transaction_info_url = "https://steexp.com/tx/"+response['hash']
        session['user_balance'] = get_bal(session['pub_key'])
        return transaction_info_url
    else:
        return False

@application.route("/send_conf", methods = ['POST', 'GET'])
def send_conf():
    """page to output confirmation with recipient address and amount.
    displays link to view transaction info on stellar explorer"""
    conf_url = transact()
    if conf_url != False:
        return render_template("send_success.html",
        address = request.form['recipient_address'],
        amount = request.form['amount'],
        conf_url = conf_url)
    else:
        return render_template("send_failed.html")

@application.route("/about")
def about():
    """page for info about stellar/the wallet"""
    return render_template("about.html")

@application.route("/remove_wallet")
def remove_wallet():
    if session['priv_key'] == None:
        flash("There is no wallet connected!")
        return redirect("/")
    else:
        return render_template("remove_wallet.html")

@application.route("/remove_conf")
def remove_conf():
    if session['priv_key'] != None:
        session['priv_key'] = None
    if session['pub_key'] != None:    
        session['pub_key'] = None
    if session['balance'] != None:
        session['balance'] = None
    return render_template("remove_conf.html")

@application.route("/view_secret")
def view_secret():
    if session['priv_key'] == None:
        return redirect("/")
    else:
        return render_template("view_secret.html",
        priv_key = session.get('priv_key'))

# run the app
if __name__ == "__main__":
    application.debug = True
    application.run()