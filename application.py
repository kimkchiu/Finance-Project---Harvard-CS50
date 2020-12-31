import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    #query into stocks for listing data
    rows = db.execute("SELECT * FROM stocks WHERE user_id = :user_id AND shares > 0", user_id = session["user_id"])

    #for cash left
    user = db.execute("SELECT * FROM users WHERE users.id = :user_id", user_id = session["user_id"])
    cash = user[0]['cash']
    cash = float(cash)

    #final total
    finalTotal = float(cash)
    for row in rows:
        finalTotal += float(row['total'])

    return render_template("index.html", rows = rows, cash = usd(cash), finalTotal =usd(finalTotal))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    #Go to buy.html is using GET
    if request.method == "GET":
        return render_template("buy.html")

    else:
        #quantity of shares variables to be defined
        shares = request.form.get("shares")
        symbol = request.form.get("symbol").upper()

        #See if symbol exists or that there is a symbol
        if not request.form.get("shares"):
            return apology("Error, Need input symbol or share")

        if not request.form.get("symbol"):
            return apology("Error, Need input symbol or share")

        #call lookup function with symbol
        price = lookup(symbol)["price"]
        name = lookup(symbol)["name"]


        #lookup cash in sql
        rows = db.execute("SELECT * FROM users WHERE id = :user_id", user_id = session["user_id"])
        cash = float(rows[0]["cash"])


        #total price
        total = float(price) * int(shares)


        #if not positive number for shares
        if int(shares) <= 0:
            return apology("Needs to be a positive number to purchase")

        if lookup(symbol) == None:
            return apology("Error, invalid symbol")

        #Check if there is enough cash
        if cash < total:
            return apology("Sorry, not enough cash to purchase")
        else:
            balance = float(cash - total)

            dateTimeObj = datetime.now()
            timestampStr = dateTimeObj.strftime("%d-%b-%Y (%H:%M)")

            price = round(price)
            cash = round(cash)
            total = round(total)
            balance = round(balance)

            #insert into stock listing table if new
            stocks = db.execute("SELECT * FROM history JOIN users ON history.user_id = users.id WHERE users.id = :user_id AND history.symbol = :symbol",
                user_id = session['user_id'], symbol = symbol)

            #if stock is new
            if len(stocks) != 0:
                db.execute("UPDATE stocks SET shares = shares + :shares, price = :price, total = (shares + :shares) * price WHERE user_id = :user_id AND symbol = :symbol",
                    shares = shares, price = price, user_id = session["user_id"], symbol = symbol)
            else:
                db.execute("INSERT INTO stocks (symbol, name, shares, price, total, user_id) VALUES (:symbol, :name, :shares, :price, :total, :user_id)",
                    symbol = symbol, name = name, shares = shares, price = price, total = total, user_id = session["user_id"])

            #insert into new table for stocks bought
            db.execute("INSERT INTO history (symbol, name, shares, price, total, user_id, time, trans) VALUES (:symbol, :name, :shares, :price, :total, :user_id, :time, :trans)",
                symbol = symbol, name = name, shares = shares, price = price, total = total, user_id = session["user_id"], time = timestampStr, trans = "Bought")


            #update users table for the cash remaining after buying
            db.execute("UPDATE users SET cash = :balance WHERE id = :user_id", balance = balance, user_id = session["user_id"])

            #flash message saying success
            flash('Bought!')

            return redirect("/")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

     #query into stocks for listing data
    rows = db.execute("SELECT * FROM history JOIN users ON history.user_id = users.id WHERE users.id = :user_id", user_id = session['user_id'])

    return render_template("history.html", rows = rows)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    """Get stock quote."""

    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")

        lookedup = lookup(symbol)

        if lookedup == None:
            return apology("Error, symbol doesn't exist")


        return render_template("quoted.html", name = lookedup['name'], symbol = lookedup['symbol'], price = lookedup['price'])



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirm")
        newhash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)

        #Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",username=request.form.get("username"))

        #return error apology if no name
        if not username:
            return apology("must provide username", 403)
        if len(rows)!= 0:
            return apology("username already exists", 403)


        #return error apology if no password
        if not password:
            return apology("must provide password or passwords don't match", 403)
        if confirm != password:
            return apology("passwords don't match", 403)

        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username = username, hash = newhash)

        #flash message saying success
        flash('Succesfully Registered!')

        return redirect("/")




@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    #Go to sell.html is using GET
    if request.method == "GET":

        #get query for symbols to be in dropdown for sell.html
        rows = db.execute("SELECT * FROM stocks WHERE user_id = :user_id AND shares > 0", user_id = session["user_id"])
        return render_template("sell.html", rows = rows)

    else:
        #quantity of shares variables to be defined
        sharesToSell = request.form.get("shares")
        symbol = request.form.get("symbol")

        #See if symbol exists or that there is a symbol
        if not sharesToSell:
            return apology("Error, Need input symbol or share")


        #check for positive number
        if int(sharesToSell) <= 0:
            return apology("Needs to be a positive number to sell")

        if lookup(symbol) ==  None:
            return apology("Error, no symbol found")

        #  if there is not enough shares to be sold, return apology
        stocks = db.execute("SELECT * FROM history WHERE user_id = :user_id AND symbol = :symbol", user_id = session['user_id'], symbol = symbol)

        sharesBought = 0
        for stock in stocks:
            #Need to keep track if something has already been bought or sold -  if bought: add, if sold: subtract
            if stock['trans'] == "Bought":
                sharesBought += int(stock['shares'])
            else:
                sharesBought -= int(stock['shares'])


        # sharesBought = db.execute("SELECT SUM (shares) FROM history WHERE trans = :trans AND symbol = :symbol AND user_id = :user_id", trans = "Bought", symbol = symbol, user_id = session['user_id'])
        # sharesSold = db.execute("SELECT SUM (shares) FROM history WHERE trans = :trans AND symbol = :symbol AND user_id = :user_id", trans = "Sold", symbol = symbol, user_id = session['user_id'])
        # sharesBought = int(sharesBought) - int(sharesSold)

        if int(sharesBought) < int(sharesToSell):
            return apology("Needs to be lower than amount bought")
        else:

            #call lookup function with symbol
            price = lookup(symbol)["price"]
            name = lookup(symbol)["name"]

            #lookup cash in sql
            rows = db.execute("SELECT * FROM users WHERE id = :user_id", user_id = session["user_id"])
            cash = float(rows[0]["cash"])

            #total price
            amountSold = float(price) * int(sharesToSell)
            amountSold = float(amountSold)

            #total balance with amount sold
            balance = float(cash + amountSold)
            sharesLeft = int(sharesBought) - int(sharesToSell)

            #total of the shares left with current price
            totalLeft = int(sharesLeft)* float(price)
            totalLeft = float(totalLeft)

            #time stamp for transaction
            dateTimeObj = datetime.now()
            timestampStr = dateTimeObj.strftime("%d-%b-%Y (%H:%M)")

            #insert into new table for stocks history SOLD
            db.execute("INSERT INTO history (symbol, name, shares, price, total, user_id, time, trans) VALUES (:symbol, :name, :shares, :price, :total, :user_id, :time, :trans)",symbol = symbol, name = name, shares = sharesToSell, price = price, total = amountSold, user_id = session["user_id"], time = timestampStr, trans = "Sold")

            #update sold stocks list where symbol and user id matches
            db.execute("UPDATE stocks SET shares = :shares, price = :price, total = :total WHERE user_id = :user_id AND symbol = :symbol",
                shares = sharesLeft, price = price, total = totalLeft, user_id = session["user_id"], symbol = symbol)


            #update users table for the cash remaining after buying
            db.execute("UPDATE users SET feedback = :feedback WHERE id = :user_id", feedback = feedback, user_id = session["user_id"])

            #flash message saying success
            flash('Thanks for the feedback!')

            return redirect("/")


#NEW DEFINITION TO ADD CASH
@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    """Add cash to pile"""

    #If get method, go to add.html
    if request.method == "GET":
        return render_template("add.html")

    else:

        #get amount of cash to be added
        add = request.form.get("addAmount")

        #See if symbol exists or that there is a symbol
        if not add:
            return apology("Error, Need input")

        if float(add) <= 0:
            return apology("Error, Needs to be a positive amount")

        #lookup cash in sql
        rows = db.execute("SELECT * FROM users WHERE id = :user_id", user_id = session["user_id"])
        cash = float(rows[0]["cash"])

        #Add to cash value
        newCash = cash + float(add)

        #Insert back into SQL
        db.execute("UPDATE users SET cash = :cash WHERE users.id = :user_id", cash = newCash, user_id = session['user_id'])

       #flash message saying success
        flash('Added Cash!')

        return redirect("/")



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
