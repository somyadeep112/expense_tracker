import csv
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# 🔐 LOGIN REQUIRED DECORATOR
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper

app = Flask(__name__)
app.secret_key = "secret123"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)

# USER TABLE
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    password = db.Column(db.String(200))
    budget = db.Column(db.Integer, default=0)   # 💰 NEW FIELD

# EXPENSE TABLE
class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer)
    category = db.Column(db.String(50))
    date = db.Column(db.String(20))
    user_id = db.Column(db.Integer)

with app.app_context():
    db.create_all()

# HOME
@app.route("/")
def home():
    return render_template("index.html")

# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = User(
            username=request.form["username"],
            password=generate_password_hash(request.form["password"])
        )
        db.session.add(user)
        db.session.commit()
        return redirect("/login")
    return render_template("register.html")

# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            return redirect("/dashboard")
        else:
            return "Invalid username or password"

    return render_template("login.html")

# DASHBOARD
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():

    user = User.query.get(session["user_id"])   # 🔥 GET CURRENT USER

    if request.method == "POST":

        # 💰 HANDLE BUDGET UPDATE
        if request.form.get("budget"):
            user.budget = int(request.form["budget"])
            db.session.commit()
            return redirect("/dashboard")

        # ➕ HANDLE EXPENSE ADD
        date = request.form.get("date")

        if not date:
            date = datetime.today().strftime('%Y-%m-%d')

        expense = Expense(
            amount=int(request.form["amount"]),
            category=request.form["category"].lower(),
            date=date,
            user_id=session["user_id"]
        )
        db.session.add(expense)
        db.session.commit()

    expenses = Expense.query.filter_by(user_id=session["user_id"]).all()
    total = sum(e.amount for e in expenses)

    # 📊 CATEGORY CALCULATION
    categories = {}
    for e in expenses:
        categories[e.category] = categories.get(e.category, 0) + e.amount

    # 💰 BUDGET CALCULATION
    remaining = user.budget - total

    return render_template(
        "dashboard.html",
        expenses=expenses,
        total=total,
        categories=categories,
        budget=user.budget,          # 🔥 NEW
        remaining=remaining,         # 🔥 NEW
        active_page="dashboard"
    )

# EXPENSES PAGE
@app.route("/expenses")
@login_required
def expenses_page():

    search = request.args.get("search")

    if search:
        expenses = Expense.query.filter(
            Expense.user_id == session["user_id"],
            Expense.category.ilike(f"%{search}%")
        ).all()
    else:
        expenses = Expense.query.filter_by(user_id=session["user_id"]).all()

    return render_template(
        "expenses.html",
        expenses=expenses,
        active_page="expenses"
    )

# REPORTS PAGE
@app.route("/reports")
@login_required
def reports():

    expenses = Expense.query.filter_by(user_id=session["user_id"]).all()

    total = sum(e.amount for e in expenses)

    categories = {}
    for e in expenses:
        categories[e.category] = categories.get(e.category, 0) + e.amount

    months = {}
    for e in expenses:
        month = e.date[:7]
        months[month] = months.get(month, 0) + e.amount

    return render_template(
        "reports.html",
        total=total,
        categories=categories,
        months=months,
        active_page="reports"
    )

# DELETE
@app.route("/delete/<int:id>")
@login_required
def delete(id):
    expense = Expense.query.filter_by(id=id, user_id=session["user_id"]).first()

    if not expense:
        return "Unauthorized"

    db.session.delete(expense)
    db.session.commit()
    return redirect("/dashboard")

# EDIT
@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit(id):
    expense = Expense.query.filter_by(id=id, user_id=session["user_id"]).first()

    if not expense:
        return "Unauthorized"

    if request.method == "POST":
        expense.amount = int(request.form["amount"])
        expense.category = request.form["category"].lower()
        expense.date = request.form["date"]

        db.session.commit()
        return redirect("/dashboard")

    return render_template("edit.html", expense=expense)

# EXPORT CSV
@app.route("/export")
@login_required
def export():

    expenses = Expense.query.filter_by(user_id=session["user_id"]).all()

    def generate():
        data = [["Amount", "Category", "Date"]]
        for e in expenses:
            data.append([e.amount, e.category, e.date])

        for row in data:
            yield ",".join(map(str, row)) + "\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=expenses.csv"}
    )

# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)