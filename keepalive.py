from flask import Flask
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot đang chạy 24/7!"

def _run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = threading.Thread(target=_run, daemon=True)
    t.start()
