from flask import Flask
import time
import random

app = Flask(__name__)

@app.route("/test")
def test():
    # simulate processing time
    delay = random.uniform(0.05, 0.2)
    time.sleep(delay)
    return {"status": "ok", "delay": delay}

if __name__ == "__main__":
    app.run(debug=True)
