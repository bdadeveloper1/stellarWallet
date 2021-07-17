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
        if session.get('balance') in [None, 0]:
            return render_template("main_logged_in.html",
            pub_address = session.get('pub_key'),
            pub_balance = session.get('user_balance'))
        else:
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
    phrase = Keypair.generate_mnemonic_phrase()
    return render_template("create_success.html",
    phrase = phrase)

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
            session['balance'] = account_info['balances'][0]['balance']
            # session['balance'] = balance
        except KeyError:
            session['balance'] = 0
        return render_template("import_success.html")
    else:
        err_msg = "Seed phrases are 12 words long. Please try again."
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
    if balance == 0:
        return render_template("balance_failed.html")
    else:
        return render_template("balance.html", balance=balance)

@application.route("/send", methods = ['POST', 'GET'])
def send():
    """page for inputting data to send money"""
    if session.get('balance') == 0:
        flash("You have no XLM to send!")
        return redirect("/")
    return render_template("send.html")

def transact():
    """function to actually process and confirm transactions"""
    recipient_address = request.form['recipient_address']
    try:
        source_account = server.load_account(session.get('pub_key'))
    except NotFoundError:
        return False
    amount = request.form['amount']
    memo = request.form['memo']
    priv_key = session.get('priv_key')

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
    application.debug = False
    application.run()
