from flask import Flask, send_from_directory, jsonify
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates")
)

def send_html(folder, filename="index.html"):
    path = os.path.join(folder, filename)
    if os.path.exists(path):
        return send_from_directory(folder, filename)

    return f"""
    <html><head><meta charset="utf-8"></head>
    <body style="font-family:Arial;padding:40px;">
        <h2>파일 없음</h2>
        <p>{path}</p>
    </body></html>
    """

def load_json(path, default=None):
    if default is None:
        default = []
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.route("/")
def home():
    return """
    <html>
    <head>
        <meta charset="utf-8">
        <title>AutoFit Platform</title>
        <style>
            body{font-family:Arial;background:#f5f7fb;margin:0;padding:40px;}
            .box{max-width:900px;margin:auto;background:white;padding:30px;border-radius:18px;box-shadow:0 10px 30px rgba(0,0,0,.08);}
            a{display:block;margin:12px 0;padding:14px 18px;background:#0f172a;color:white;text-decoration:none;border-radius:10px;}
        </style>
    </head>
    <body>
        <div class="box">
            <h1>AutoFit Platform</h1>
            <a href="/health">서버 상태 확인</a>
            <a href="/platform">오토피트 플랫폼</a>
            <a href="/parts">PARTS</a>
            <a href="/control">CONTROL</a>
            <a href="/ledger">LEDGER</a>
        </div>
    </body>
    </html>
    """

@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "AutoFit Platform Render",
        "base_dir": BASE_DIR
    })

@app.route("/platform")
def platform():
    return send_html(os.path.join(BASE_DIR, "templates"), "autofit_platform.html")

@app.route("/parts")
def parts():
    return send_html(os.path.join(BASE_DIR, "modules", "PARTS", "templates"), "index.html")

@app.route("/parts/api/load")
def parts_api_load():
    data_dir = os.path.join(BASE_DIR, "data", "PARTS")

    return jsonify({
        "ok": True,
        "inventory": load_json(os.path.join(data_dir, "parts_inventory.json"), []),
        "history": load_json(os.path.join(data_dir, "parts_history.json"), []),
        "audit": load_json(os.path.join(data_dir, "parts_audit_sessions.json"), []),
        "settings": load_json(os.path.join(data_dir, "settings.json"), {})
    })

@app.route("/parts/parts_inventory.json")
def parts_inventory_json():
    return send_from_directory(os.path.join(BASE_DIR, "data", "PARTS"), "parts_inventory.json")

@app.route("/parts/parts_history.json")
def parts_history_json():
    return send_from_directory(os.path.join(BASE_DIR, "data", "PARTS"), "parts_history.json")

@app.route("/parts/settings.json")
def parts_settings_json():
    return send_from_directory(os.path.join(BASE_DIR, "data", "PARTS"), "settings.json")

@app.route("/control")
def control():
    return send_html(os.path.join(BASE_DIR, "modules", "CONTROL", "templates"), "index.html")

@app.route("/ledger")
def ledger():
    return send_html(os.path.join(BASE_DIR, "modules", "LEDGER", "templates"), "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8790))
    app.run(host="0.0.0.0", port=port)