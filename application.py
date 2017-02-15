from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir
from time import localtime, strftime

from helpers import *

# Stock Trading website for CS50, pset7
# Erik Golke 14/02/2017


# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    
    # updates portfolio if stock is owned
    stocks = db.execute("SELECT * FROM portfolio WHERE User_ID = :User_ID", User_ID = session["user_id"])
    
    # updates portfolio with current stock prices
    for i in range(len(stocks)):
        quote = lookup(stocks[i]["Symbol"])
        total = stocks[i]["Shares"] * quote["price"]
        result = db.execute("UPDATE portfolio SET Price = :price, Total = :total WHERE Symbol = :symbol AND User_ID = :User_ID",
        price = quote["price"], total = total, symbol = quote["symbol"], User_ID = session["user_id"])
    
    portfolio = db.execute("SELECT * FROM portfolio WHERE User_ID = :User_ID", User_ID = session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = :User_ID", User_ID = session["user_id"])
    holdings = db.execute("SELECT SUM(Total) FROM portfolio WHERE User_ID = :User_ID", User_ID = session["user_id"])
    
    # check if portfolio is empty
    if any(stocks) is True:
        
        # if not empty, render index with appropriate values, else default
        return render_template("index.html", items = portfolio, Cash = usd(cash[0]["cash"]), Total = usd(cash[0]["cash"] + holdings[0]["SUM(Total)"]))
    else:
        return render_template("index.html", Cash = usd(cash[0]["cash"]), Total = usd(cash[0]["cash"]))
    
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # gets stock info, stores in a dictionary
        quote = lookup(request.form.get("stock"))
        
        # get number of shares from user, ensures input is valid int
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("invalid shares")
        
        # ensure number is positive    
        if shares < 1:
            return apology("Invalid shares")    
        
         # checks if quote exists
        if quote is None:
            return apology("invalid stock symbol")
         
        # gets cash from database  
        cash = db.execute("SELECT cash FROM users WHERE id = :User_ID", User_ID = session["user_id"])
        
        # determine total cost of shares
        cost = float(quote["price"]) * shares
        
        # check to see if user has enough cash
        if float(cash[0]["cash"]) < cost:
            return apology("Insufficient funds")
            
        # inserts transaction into database transaction table
        result = db.execute("INSERT INTO transactions (Symbol,Shares,Price,Transacted, User_ID) values(:Symbol, :Shares, :Price, :Transacted, :User_ID)", 
        Symbol = quote["symbol"], Shares = shares, Price = cost, Transacted = strftime("%Y-%m-%d %H:%M:%S", localtime()), User_ID = session["user_id"])
            
        # open portfolio
        portfolio = db.execute("SELECT * FROM portfolio WHERE User_ID = :User_ID", User_ID = session["user_id"])
            
        # checks if stock symbol is already in database
        if not any(i['Symbol'] == quote["symbol"] for i in portfolio):
                
            # inserts transaction into database portfolio if not owned
            result = db.execute("INSERT INTO portfolio (Symbol,Name,Shares,Price,Total, User_ID) values(:Symbol, :Name, :Shares, :Price, :Total, :User_ID)", 
            Symbol = quote["symbol"], Name = quote["name"], Shares = shares, Price = quote["price"], Total = cost, User_ID = session["user_id"])
        else:   
             # updates portfolio if stock is owned    
            resultant = db.execute("UPDATE portfolio SET Shares = Shares + :shares, Price = Price + :price, Total = Total + :total WHERE Symbol = :symbol AND User_ID = :User_ID",
            shares = shares, price = quote["price"], total = cost, symbol = quote["symbol"], User_ID = session["user_id"])
            
        # deducts money spent from users available cash
        update = db.execute("UPDATE users SET cash = cash - :cost WHERE id = :User_ID", cost = cost, User_ID = session["user_id"])
            
            
        return redirect(url_for("index"))
            
    else:
        return render_template("buy.html")    

@app.route("/history")
@login_required
def history():
    
    transactions = db.execute("SELECT * FROM transactions WHERE User_ID = :User_ID", User_ID =session["user_id"])
        
    # directs user to purchase confirmation screen
    return render_template("history.html", items = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username").upper())

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
     # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # gets stock info, stores in a dictionary
        quote = lookup(request.form.get("quote"))
        
        # checks if quote exists, returns stock information
        if quote is not None:
            return render_template("quotedisplay.html", name = quote["name"], price = quote["price"], symbol = quote["symbol"])
        else:
            return apology("Invalid stock symbol")
            
    # redirect user to quote form        
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    
    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        
        if not request.form.get("username"):
            return apology("must enter username")
        
        # ensure password was submitted
        if not request.form.get("password"):
            return apology("must enter password")

        # ensure password confrimation was submitted
        elif not request.form.get("passwordconfirm"):
            return apology("must re-enter password")
        
        # ensure password is entered correctly twice    
        if not request.form.get("password") == request.form.get("passwordconfirm"):
            return apology("password fields must match")
        
        # encrypt password, and insert username and hashed password into table    
        hash = pwd_context.encrypt(request.form.get('password'))
        result = db.execute("INSERT INTO users (username,hash) values(:username, :hash)",
        username = request.form.get("username").upper(), hash = hash)
        
        # check if username already taken
        if not result:
            return apology("username already taken")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username = request.form.get("username").upper())

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]
        
        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # gets stock info, stores in a dictionary
        quote = lookup(request.form.get("stock"))
        
        # get number of shares from user, ensures input is valid int
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("invalid shares")
        
        # ensure number is positive    
        if shares < 1:
            return apology("Invalid shares")    
        
         # checks if quote exists
        if quote is None:
            return apology("invalid stock symbol")
         
        # gets cash from database  
        cash = db.execute("SELECT cash FROM users WHERE id = :User_ID", User_ID = session["user_id"])
        
         # open portfolio
        portfolio = db.execute("SELECT * FROM portfolio WHERE User_ID = :User_ID", User_ID = session["user_id"])
         
        # check if symbol is in portfolio
        if any(i['Symbol'] == quote["symbol"] for i in portfolio):
            totalshares = db.execute("SELECT Shares FROM portfolio WHERE Symbol = :symbol AND User_ID = :User_ID",
            symbol = quote["symbol"], User_ID = session["user_id"])
        else:
            return apology("You don't own that stock.")
        
        # determine total cost of shares
        cost = float(quote["price"]) * shares
        
        # check to see if user has enough shares
        if shares > totalshares[0]["Shares"]:
            return apology("Insufficient shares")
            
        # inserts transaction into database transaction table
        result = db.execute("INSERT INTO transactions (Symbol,Shares,Price,Transacted, User_ID) values(:Symbol, :Shares, :Price, :Transacted, :User_ID)", 
        Symbol = quote["symbol"], Shares = -shares, Price = cost, Transacted = strftime("%Y-%m-%d %H:%M:%S", localtime()), User_ID = session["user_id"])
            
        # checks if stock symbol is already in database
        if any(i['Symbol'] == quote["symbol"] for i in portfolio):
            
            # if selling less shares than you own, update portfolio
            if not shares == totalshares[0]["Shares"]:
                result = db.execute("UPDATE portfolio SET Shares = Shares - :Shares, Total = Total - :cost WHERE Symbol = :Symbol AND User_ID = :User_ID",
                Shares = shares, cost = cost, Symbol = quote["symbol"], User_ID = session["user_id"])
            else:    
            # if selling all shares
                result = db.execute("DELETE FROM portfolio WHERE Symbol = :Symbol AND User_ID = :User_ID",
                Symbol = quote["symbol"], User_ID = session["user_id"])
        else:   
            return apology("Can't sell what you don't own, brodawg")
            
        # deducts money spent from users available cash
        update = db.execute("UPDATE users SET cash = cash + :cost WHERE id = :User_ID", cost = cost, User_ID = session["user_id"])
            
            
        return redirect(url_for("index"))
            
    else:
        return render_template("sell.html")    
        
@app.route("/change", methods=["GET", "POST"])
def change():     
     # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # ensure old password was submitted
        if not request.form.get("current_password"):
            return apology("must enter current password")
        
        # ensure password was submitted
        if not request.form.get("new_password"):
            return apology("must enter new password")

        # ensure password confrimation was submitted
        elif not request.form.get("new_password_confirm"):
            return apology("must re-enter new password")
        
        # ensure password is entered correctly twice    
        if not request.form.get("new_password") == request.form.get("new_password_confirm"):
            return apology("password fields must match")
            
        # query database for password
        password = db.execute("SELECT hash FROM users WHERE id = :id", id = session["user_id"])

        # verify password   
        if not pwd_context.verify(request.form.get("current_password"), password[0]["hash"]):
            return apology("incorrect password")
            
        
        # encrypt password, and update new password   
        hash = pwd_context.encrypt(request.form.get('new_password'))
        result = db.execute("UPDATE users SET hash = :hash WHERE id = :id",
        hash = hash, id = session["user_id"])
        
        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("change.html")
