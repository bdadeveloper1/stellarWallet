from flask import Flask, render_template, request, session
#from flask_session import Session
from stellar_sdk import Server, Keypair, TransactionBuilder, Network
import stellar_sdk
import requests

application = Flask(__name__)
application.secret_key = "wasdfghjkl"
server = Server(horizon_url="https://horizon-testnet.stellar.org")
friendbot_url = "https://friendbot.stellar.org"
base_fee = server.fetch_base_fee()
# sample address for checking balance and sending XLM
# GBQMBYUUN2I6HLQ3OPDQRYI7AK5WWAXC6TDIG4UNWR7HHRPRJCHB6YBG

@application.route('/')
def home():
    """homepage"""
 #   try:
  #      session['priv_key']
   # except:
    #    session['priv_key'] = None

    if session.get('priv_key') != None:
         return render_template("main_logged_in.html",
         pub_address = session.get("pub_key"))
    else:
        return render_template("main.html")
        
  #  else:
   #     return render_template("main_logged_in.html",
    #    pub_address = session['pub_key'])

# to do: save wallet once created
@application.route('/create')
def create():
    """page for explaining seed phrase before creating wallet"""
    return render_template("create.html")

# to do: save wallet once created
@application.route('/create_phrase')
def create_phrase():
    """page for displaying seed phrase"""
    new_keypair = new_wallet()
    response = requests.get(friendbot_url, params={"addr": new_keypair.public_key})
    if response.status_code == 200:
        bot_response = "Your wallet has been successfully created and funded with 10,000 XLM by friendbot."
    else:
        status = response.status_code
        bot_response = "Error "+str(status)+" received from the server. Please try again."
        return render_template("create_failed.html")
    phrase = new_keypair.generate_mnemonic_phrase()
    session['priv_key'] = new_keypair.secret
    session['pub_key'] = new_keypair.public_key
    return render_template("create_success.html",
    bot_response = bot_response, phrase = phrase,
    public_key = new_keypair.public_key,
    secret_key = new_keypair.secret)

def new_wallet():
    """"Function to create a new wallet"""
    keypair = Keypair.random()
    return keypair

# to do: save user's wallet once it is imported
@application.route("/import_wallet", methods=['POST', 'GET'])
def import_wallet():
    """page for importing a new wallet using 12 word seed phrase"""
    return render_template("import_wallet.html")

# def phrase_to_key():
#     """function to convert seed phrase into private key"""
#     if len(request.form['phrase'].split(" ")) == 12:
#         return 
#     else:
    
#     s_key = Keypair.from_mnemonic_phrase(request.form['phrase'])
#     return s_key

@application.route('/imported', methods=['POST', 'GET'])
def imported():
    """page for status after entering seed phrase"""
    pl = len(request.form['phrase'].split(" ")) # get phrase length, split into words
    if pl == 12: #check that there are twelve words
        try:
            key = Keypair.from_mnemonic_phrase(request.form['phrase'])
        except stellar_sdk.exceptions.ValueError:
            err_msg = "Invalid mnemonic, please check if the mnemonic is correct."
            return render_template("import_failed.html", err_msg=err_msg)
        # this should save the user's private key for as long as they keep the site open
        session['priv_key'] = key.secret
        session['pub_key'] = key.public_key
        return render_template("import_success.html")
    else:
        err_msg = "Seed phrases are 12 words; {} words were entered.".format(pl)
        return render_template("import_failed.html", err_msg=err_msg)

@application.route("/check_balance", methods = ['POST', 'GET'])
def check_balance():
    """page asks user to input an address"""
    return render_template("check_balance.html")

def get_bal(address):
    """function to retrieve wallet ballance from horizon"""
    account_url_testnet = "https://horizon-testnet.stellar.org/accounts/"+str(address)
    account_url_mainnet = "https://horizon.stellar.org/accounts/"+str(address)
    try:
        account_info = requests.get(account_url_testnet).json()
    except:
        return "error"

    balance = account_info['balances'][0]['balance']
    return balance

@application.route("/balance", methods = ['POST', 'GET'])
def balance():
    """page displays balance of previously input address"""
    balance = get_bal(request.form['address'])
    return render_template("balance.html", balance=balance)

@application.route("/send", methods = ['POST', 'GET'])
def send():
    """page for inputting data to send money"""
    return render_template("send.html")

def transact():
    """function to actually process and confirm transactions"""
    recipient_address = request.form['recipient_address']
    amount = request.form['amount']
    #ideally the user should not have to enter their private key
    #but there is currently not an implented way to store it (cookies? etc.)
    #at least i don't know the proper way to store a private key
    priv_key = session.get('priv_key')
    memo = request.form['memo']
    transaction = (
    TransactionBuilder(
        source_account = server.load_account(session.get('pub_key')),
        network_passphrase = Network.TESTNET_NETWORK_PASSPHRASE,
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
        transaction_info_url = "https://testnet.steexp.com/tx/"+response['hash']
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

@application.route("/remove")
def remove():
    pass
#    return render_template("remove.html")

@application.route("/about")
def about():
    """page for info about stellar/the wallet"""
    return render_template("about.html")

# run the app
if __name__ == "__main__":
    application.debug = True
    application.run()