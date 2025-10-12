from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "AutoFit Flask Server is Running! ✅"

if __name__ == "__main__":
    # Render 환경에서는 반드시 0.0.0.0 + PORT 환경변수를 사용해야 함
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

