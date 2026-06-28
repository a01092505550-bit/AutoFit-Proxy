from flask import Flask, send_from_directory, jsonify, request
from datetime import datetime
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates")
)

def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/")
def home():
    return """
    <html><head><meta charset="utf-8"><title>AutoFit Platform</title>
    <style>
    body{font-family:Arial;background:#f5f7fb;margin:0;padding:40px;}
    .box{max-width:900px;margin:auto;background:white;padding:30px;border-radius:18px;box-shadow:0 10px 30px rgba(0,0,0,.08);}
    a{display:block;margin:12px 0;padding:14px 18px;background:#0f172a;color:white;text-decoration:none;border-radius:10px;}
    </style></head>
    <body><div class="box">
    <h1>AutoFit Platform</h1>
    <a href="/health">서버 상태 확인</a>
    <a href="/platform">오토피트 플랫폼</a>
    <a href="/parts">PARTS</a>
    <a href="/iveco">IVECO</a>
    <a href="/control">CONTROL</a>
    <a href="/ledger">LEDGER</a>
    </div></body></html>
    """

@app.route("/health")
def health():
    return jsonify({"ok": True, "service": "AutoFit Platform Render", "base_dir": BASE_DIR})

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


@app.route("/parts/api/save", methods=["POST"])
@app.route("/api/save", methods=["POST"])
def parts_api_save():
    data_dir = os.path.join(BASE_DIR, "data", "PARTS")
    os.makedirs(data_dir, exist_ok=True)

    payload = request.get_json(silent=True) or {}

    inv_path = os.path.join(data_dir, "parts_inventory.json")
    history_path = os.path.join(data_dir, "parts_history.json")
    audit_path = os.path.join(data_dir, "parts_audit_sessions.json")
    settings_path = os.path.join(data_dir, "settings.json")

    parts = payload.get("parts") or payload.get("inventory") or payload.get("items")
    histories = payload.get("histories") or payload.get("history")
    audit_sessions = payload.get("auditSessions") or payload.get("audit")
    settings = payload.get("settings")

    if parts is not None:
        old = load_json(inv_path, {"schema": "ysm_parts_inventory_render", "items": []})
        if isinstance(old, dict):
            old["items"] = parts
            old["updated_at"] = now_text()
            save_json(inv_path, old)
        else:
            save_json(inv_path, {
                "schema": "ysm_parts_inventory_render",
                "updated_at": now_text(),
                "items": parts
            })

    if histories is not None:
        if isinstance(histories, dict):
            histories["updated_at"] = now_text()
            save_json(history_path, histories)
        else:
            save_json(history_path, {
                "updated_at": now_text(),
                "histories": histories
            })

    if audit_sessions is not None:
        if isinstance(audit_sessions, dict):
            audit_sessions["updated_at"] = now_text()
            save_json(audit_path, audit_sessions)
        else:
            save_json(audit_path, {
                "updated_at": now_text(),
                "audit_sessions": audit_sessions
            })

    if settings is not None:
        save_json(settings_path, settings)

    return jsonify({"ok": True, "saved": True, "updated_at": now_text()})

@app.route("/parts/parts_inventory.json")
def parts_inventory_json():
    return send_from_directory(os.path.join(BASE_DIR, "data", "PARTS"), "parts_inventory.json")

@app.route("/parts/parts_history.json")
def parts_history_json():
    return send_from_directory(os.path.join(BASE_DIR, "data", "PARTS"), "parts_history.json")

@app.route("/parts/settings.json")
def parts_settings_json():
    return send_from_directory(os.path.join(BASE_DIR, "data", "PARTS"), "settings.json")

@app.route("/iveco")
@app.route("/iveco/")
def iveco():
    return send_html(
        os.path.join(BASE_DIR, "modules", "PARTS", "06 MODULES", "IVECO", "01 APP"),
        "index.html"
    )

@app.route("/api/iveco/load")
def iveco_api_load():
    data_dir = os.path.join(BASE_DIR, "modules", "PARTS", "06 MODULES", "IVECO", "03 DATA")
    inv_path = os.path.join(data_dir, "iveco_parts_master_unified_sheets1_9.json")
    log_path = os.path.join(data_dir, "iveco_parts_log.json")
    users_path = os.path.join(data_dir, "iveco_parts_users.json")

    data = load_json(inv_path, {"items": []})
    items = data.get("items", data) if isinstance(data, dict) else data
    log_data = load_json(log_path, {"logs": []})
    logs = log_data.get("logs", log_data) if isinstance(log_data, dict) else log_data
    users_data = load_json(users_path, {"users": []})
    users = users_data.get("users", users_data) if isinstance(users_data, dict) else users_data

    return jsonify({
        "ok": True,
        "data": data,
        "items": items,
        "logs": logs,
        "users": users
    })

@app.route("/api/iveco/save", methods=["POST"])
def iveco_api_save():
    data_dir = os.path.join(BASE_DIR, "modules", "PARTS", "06 MODULES", "IVECO", "03 DATA")
    inv_path = os.path.join(data_dir, "iveco_parts_master_unified_sheets1_9.json")
    log_path = os.path.join(data_dir, "iveco_parts_log.json")
    users_path = os.path.join(data_dir, "iveco_parts_users.json")

    payload = request.get_json(silent=True) or {}

    data = payload.get("data") or payload.get("inventory")
    items = payload.get("items")
    logs = payload.get("logs")
    users = payload.get("users")

    if items is not None:
        old = load_json(inv_path, {"items": []})
        if isinstance(old, dict):
            old["items"] = items
            old["updated_at"] = now_text()
            data = old
        else:
            data = {"items": items, "updated_at": now_text()}

    if data is not None:
        if isinstance(data, dict):
            data["updated_at"] = now_text()
        save_json(inv_path, data)

    if logs is not None:
        save_json(log_path, {"logs": logs, "updated_at": now_text()})

    if users is not None:
        save_json(users_path, {"users": users, "updated_at": now_text()})

    return jsonify({"ok": True, "saved": True, "updated_at": now_text()})

@app.route("/api/iveco/history")
def iveco_history():
    data_dir = os.path.join(BASE_DIR, "modules", "PARTS", "06 MODULES", "IVECO", "03 DATA")
    log_path = os.path.join(data_dir, "iveco_parts_log.json")
    return jsonify(load_json(log_path, {"logs": []}))

@app.route("/control")
def control():
    return send_html(os.path.join(BASE_DIR, "modules", "CONTROL", "templates"), "index.html")

@app.route("/ledger")
def ledger():
    return send_html(os.path.join(BASE_DIR, "modules", "LEDGER", "templates"), "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8790))
    app.run(host="0.0.0.0", port=port)