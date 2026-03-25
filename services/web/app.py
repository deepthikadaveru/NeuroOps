from flask import Flask, send_file

app = Flask(__name__)

@app.route("/")
def home():
    return "Web Service Running"

@app.route("/payment")
def payment():
    return send_file("payment.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)