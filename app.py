from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/students")
def students():
    return render_template("students.html")


@app.route("/add-student")
def add_student():
    return render_template("add_student.html")


@app.route("/qr-codes")
def qr_codes():
    return render_template("qr_codes.html")


@app.route("/active-session")
def active_session():
    return render_template("active_session.html")


if __name__ == "__main__":
    app.run(debug=True)