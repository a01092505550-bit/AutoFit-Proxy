# -*- coding: utf-8 -*-
"""
YSM Parts Center R7 Storage Engine - API / WEB PATH FINAL
Folder standard:
  ROOT\01 WEB\index.html
  ROOT\02 SERVER\this file
  ROOT\03 DATA\parts_inventory.json, parts_history.json, parts_audit_sessions.json, settings.json
  ROOT\04 BACKUP\*.json
"""
from __future__ import annotations

import json
import shutil
import socket
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PORT = 8788

SERVER_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVER_DIR.parent
WEB_DIR = ROOT_DIR / "01 WEB"
DATA_DIR = ROOT_DIR / "03 DATA"
BACKUP_DIR = ROOT_DIR / "04 BACKUP"

INDEX_FILE = WEB_DIR / "index.html"
INV_FILE = DATA_DIR / "parts_inventory.json"
HISTORY_FILE = DATA_DIR / "parts_history.json"
AUDIT_FILE = DATA_DIR / "parts_audit_sessions.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def read_json(path: Path, default):
    if not path.exists():
        write_json(path, default, backup=False)
        return default
    try:
        text = path.read_text(encoding="utf-8-sig").strip()
        if not text:
            return default
        return json.loads(text)
    except Exception:
        return default


def write_json(path: Path, data, backup: bool = True):
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        backup_name = f"{path.stem}_{now_stamp()}{path.suffix}"
        try:
            shutil.copy2(path, BACKUP_DIR / backup_name)
        except Exception:
            pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def ensure_defaults():
    if not INV_FILE.exists():
        write_json(INV_FILE, {"schema": "ysm_parts_inventory", "items": []}, backup=False)
    if not HISTORY_FILE.exists():
        write_json(HISTORY_FILE, [], backup=False)
    if not AUDIT_FILE.exists():
        write_json(AUDIT_FILE, [], backup=False)
    if not SETTINGS_FILE.exists():
        write_json(SETTINGS_FILE, {"port": PORT, "version": "R7"}, backup=False)


def find_part(items, key):
    key = str(key or "").strip()
    if not key:
        return None
    fields = ["윤성관리번호", "대표품번", "실입고품번", "OEM번호", "바코드", "id"]
    for p in items:
        for f in fields:
            if str(p.get(f, "")).strip() == key:
                return p
    return None


def get_items(inv):
    if isinstance(inv, list):
        return inv
    if isinstance(inv, dict):
        if isinstance(inv.get("items"), list):
            return inv["items"]
        if isinstance(inv.get("data"), list):
            return inv["data"]
    return []


def set_items(inv, items):
    if isinstance(inv, list):
        return items
    if isinstance(inv, dict):
        inv["items"] = items
        inv["updated_at"] = datetime.now().isoformat()
        return inv
    return {"schema": "ysm_parts_inventory", "updated_at": datetime.now().isoformat(), "items": items}


class Handler(BaseHTTPRequestHandler):
    server_version = "YSMPartsR7/1.0"

    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (datetime.now().strftime("%H:%M:%S"), fmt % args))

    def send_bytes(self, data: bytes, content_type="application/octet-stream", code=200):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, data, code=200):
        self.send_bytes(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), "application/json; charset=utf-8", code)

    def send_text(self, text: str, code=200):
        self.send_bytes(text.encode("utf-8"), "text/plain; charset=utf-8", code)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            if not INDEX_FILE.exists():
                self.send_text(f"index.html not found: {INDEX_FILE}", 404)
                return
            self.send_bytes(INDEX_FILE.read_bytes(), "text/html; charset=utf-8")
            return

        # HTML 구버전 호환: 직접 JSON 파일 요청 처리
        if path == "/parts_inventory.json":
            self.send_json(read_json(INV_FILE, {"items": []}))
            return
        if path == "/parts_history.json":
            self.send_json(read_json(HISTORY_FILE, []))
            return
        if path == "/parts_audit_sessions.json":
            self.send_json(read_json(AUDIT_FILE, []))
            return
        if path == "/settings.json":
            self.send_json(read_json(SETTINGS_FILE, {}))
            return

        # API 호환
        if path in ("/api/load", "/api/data", "/api/status"):
            self.send_json({
                "ok": True,
                "version": "R7_PATH_WEB_API_FINAL",
                "root": str(ROOT_DIR),
                "web": str(WEB_DIR),
                "data": str(DATA_DIR),
                "backup": str(BACKUP_DIR),
                "inventory": read_json(INV_FILE, {"items": []}),
                "history": read_json(HISTORY_FILE, []),
                "audit_sessions": read_json(AUDIT_FILE, []),
                "settings": read_json(SETTINGS_FILE, {}),
            })
            return

        self.send_text(f"404 Not Found: {path}", 404)

    def read_body_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8-sig"))

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self.read_body_json()
        except Exception as e:
            self.send_json({"ok": False, "error": f"invalid json: {e}"}, 400)
            return

        try:
            if path in ("/api/save", "/api/save_all"):
                if "inventory" in body:
                    write_json(INV_FILE, body["inventory"])
                if "history" in body:
                    write_json(HISTORY_FILE, body["history"])
                if "audit_sessions" in body:
                    write_json(AUDIT_FILE, body["audit_sessions"])
                if "settings" in body:
                    write_json(SETTINGS_FILE, body["settings"])
                self.send_json({"ok": True, "saved_at": datetime.now().isoformat()})
                return

            if path in ("/api/save_inventory", "/api/inventory/save"):
                data = body.get("inventory", body.get("data", body))
                write_json(INV_FILE, data)
                self.send_json({"ok": True, "file": str(INV_FILE)})
                return

            if path in ("/api/save_history", "/api/history/save"):
                data = body.get("history", body.get("data", body))
                write_json(HISTORY_FILE, data)
                self.send_json({"ok": True, "file": str(HISTORY_FILE)})
                return

            if path in ("/api/save_audit", "/api/audit/save", "/api/audit_session"):
                sessions = read_json(AUDIT_FILE, [])
                if isinstance(sessions, dict) and isinstance(sessions.get("sessions"), list):
                    sessions_list = sessions["sessions"]
                elif isinstance(sessions, list):
                    sessions_list = sessions
                else:
                    sessions_list = []
                session = body.get("session", body)
                if "id" not in session:
                    session["id"] = "AUD-" + datetime.now().strftime("%Y%m%d-%H%M%S")
                session.setdefault("created_at", datetime.now().isoformat())
                session.setdefault("status", "실사대기")
                sessions_list.insert(0, session)
                write_json(AUDIT_FILE, sessions_list)

                history = read_json(HISTORY_FILE, [])
                if not isinstance(history, list):
                    history = []
                history.insert(0, {"일자": datetime.now().isoformat(), "구분": "실사대기", "묶음ID": session.get("id"), "항목수": len(session.get("items", [])), "출처": "실사조사"})
                write_json(HISTORY_FILE, history)
                self.send_json({"ok": True, "session_id": session.get("id")})
                return

            if path in ("/api/stock_move", "/api/move"):
                inv = read_json(INV_FILE, {"items": []})
                items = get_items(inv)
                key = body.get("key") or body.get("윤성관리번호") or body.get("part_no")
                move_type = str(body.get("type") or body.get("구분") or "").upper()
                qty = float(body.get("qty") or body.get("수량") or 0)
                part = find_part(items, key)
                if not part:
                    self.send_json({"ok": False, "error": "part not found", "key": key}, 404)
                    return
                old = float(part.get("현재고") or 0)
                new = old + qty if move_type in ("IN", "입고") else old - qty
                part["현재고"] = int(new) if new.is_integer() else new
                write_json(INV_FILE, set_items(inv, items))
                history = read_json(HISTORY_FILE, [])
                if not isinstance(history, list):
                    history = []
                history.insert(0, {"일자": datetime.now().isoformat(), "구분": "입고" if move_type in ("IN", "입고") else "출고", "윤성관리번호": part.get("윤성관리번호"), "이전수량": old, "수량": qty, "변경후": new, "메모": body.get("memo", "")})
                write_json(HISTORY_FILE, history)
                self.send_json({"ok": True, "old": old, "new": new})
                return

            self.send_json({"ok": False, "error": f"unknown endpoint: {path}"}, 404)
        except Exception as e:
            self.send_json({"ok": False, "error": str(e)}, 500)


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "<SERVER-PC-IP>"


if __name__ == "__main__":
    ensure_defaults()
    print("----------------------------------------")
    print("YSM Parts Center R7 Storage Engine - API FINAL")
    print(f"Project ROOT: {ROOT_DIR}")
    print(f"Server folder: {SERVER_DIR}")
    print(f"Web folder: {WEB_DIR}")
    print(f"Local URL: http://127.0.0.1:{PORT}")
    print(f"Network URL: http://{local_ip()}:{PORT}")
    print("Save files:")
    print(f" - {INV_FILE}")
    print(f" - {HISTORY_FILE}")
    print(f" - {AUDIT_FILE}")
    print(f"Settings: {SETTINGS_FILE}")
    print(f"Backup: {BACKUP_DIR}")
    print("----------------------------------------")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
