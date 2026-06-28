# -*- coding: utf-8 -*-
"""
YSM Parts Center R8 Storage Engine
- 01 WEB/index.html 제공
- 03 DATA JSON 저장
- 04 BACKUP 자동백업
- 입고/출고/실사/관리자조정 API 제공
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime
import json, shutil, mimetypes, socket, traceback, urllib.parse

SERVER_DIR = Path(__file__).resolve().parent
ROOT = SERVER_DIR.parent
WEB_DIR = ROOT / "01 WEB"
DATA_DIR = ROOT / "03 DATA"
BACKUP_DIR = ROOT / "04 BACKUP"
INV_FILE = DATA_DIR / "parts_inventory.json"
HIS_FILE = DATA_DIR / "parts_history.json"
AUD_FILE = DATA_DIR / "parts_audit_sessions.json"
SET_FILE = DATA_DIR / "settings.json"

# IVECO module paths
IVECO_DIR = ROOT / "06 MODULES" / "IVECO"
IVECO_APP_DIR = IVECO_DIR / "01 APP"
IVECO_DATA_DIR = IVECO_DIR / "03 DATA"
IVECO_ASSETS_DIR = IVECO_DIR / "04 ASSETS"
IVECO_BACKUP_DIR = IVECO_DIR / "99 BACKUP"
IVECO_INV_FILE = IVECO_DATA_DIR / "iveco_parts_master_unified_sheets1_9.json"
IVECO_LOG_FILE = IVECO_DATA_DIR / "iveco_parts_log.json"
IVECO_USERS_FILE = IVECO_DATA_DIR / "iveco_parts_users.json"

PORT = 8788

for d in (WEB_DIR, DATA_DIR, BACKUP_DIR, IVECO_APP_DIR, IVECO_DATA_DIR, IVECO_ASSETS_DIR, IVECO_BACKUP_DIR):
    d.mkdir(parents=True, exist_ok=True)

def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def read_json(path, default):
    if not path.exists():
        write_json(path, default, backup=False)
        return default
    try:
        txt = path.read_text(encoding="utf-8-sig")
        if not txt.strip(): return default
        return json.loads(txt)
    except Exception:
        return default

def write_json(path, data, backup=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        make_single_backup(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def make_single_backup(path):
    month_dir = BACKUP_DIR / datetime.now().strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, month_dir / f"{path.stem}_{stamp()}{path.suffix}")

def backup_all(reason="manual"):
    month_dir = BACKUP_DIR / datetime.now().strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)
    made=[]
    for p in [INV_FILE, HIS_FILE, AUD_FILE, SET_FILE]:
        if p.exists():
            out = month_dir / f"{p.stem}_{stamp()}_{reason}{p.suffix}"
            shutil.copy2(p, out)
            made.append(str(out))
    return made

def make_iveco_single_backup(path):
    month_dir = IVECO_BACKUP_DIR / datetime.now().strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, month_dir / f"{path.stem}_{stamp()}{path.suffix}")

def write_iveco_json(path, data, backup=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        make_iveco_single_backup(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def read_iveco_json(path, default):
    if not path.exists():
        write_iveco_json(path, default, backup=False)
        return default
    try:
        txt = path.read_text(encoding="utf-8-sig")
        if not txt.strip():
            return default
        return json.loads(txt)
    except Exception:
        return default

def iveco_inventory_obj():
    default = {
        "schema": "iveco_parts_unified_v2",
        "updated_at": "",
        "program_ready": True,
        "primary_key": "maker_part_no",
        "items": []
    }
    data = read_iveco_json(IVECO_INV_FILE, default)
    if isinstance(data, list):
        data = {"schema": "iveco_parts_unified_v2_legacy_array", "updated_at": "", "items": data}
    data.setdefault("items", [])
    return data

def iveco_log_obj():
    data = read_iveco_json(IVECO_LOG_FILE, {"version": "IVECO_R8", "created_at": now_text(), "logs": []})
    if isinstance(data, list):
        data = {"version": "IVECO_R8", "logs": data}
    data.setdefault("logs", [])
    return data

def iveco_users_obj():
    data = read_iveco_json(IVECO_USERS_FILE, {"version": "IVECO_R8", "users": []})
    if isinstance(data, list):
        data = {"version": "IVECO_R8", "users": data}
    data.setdefault("users", [])
    return data

def iveco_backup_all(reason="manual"):
    month_dir = IVECO_BACKUP_DIR / datetime.now().strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for p in [IVECO_INV_FILE, IVECO_LOG_FILE, IVECO_USERS_FILE]:
        if p.exists():
            out = month_dir / f"{p.stem}_{stamp()}_{reason}{p.suffix}"
            shutil.copy2(p, out)
            made.append(str(out))
    return made

def inventory_obj():
    default = {"schema":"ysm_parts_inventory_r8","updated_at":"","items":[]}
    data = read_json(INV_FILE, default)
    if isinstance(data, list):
        data = {"schema":"ysm_parts_inventory_r8_legacy_array","updated_at":"","items":data}
    if "items" not in data: data["items"] = []
    return data

def history_obj():
    data = read_json(HIS_FILE, {"version":"R8","program":"YSM Parts Management Center","created_at":now_text(),"histories":[]})
    if isinstance(data, list): data = {"version":"R8","histories":data}
    data.setdefault("histories", [])
    return data

def audit_obj():
    data = read_json(AUD_FILE, {"version":"R8","program":"YSM Parts Management Center","created_at":now_text(),"last_updated":"","next_session_no":1,"audit_sessions":[]})
    if isinstance(data, list): data = {"version":"R8","audit_sessions":data, "next_session_no":1}
    data.setdefault("audit_sessions", [])
    data.setdefault("next_session_no", 1)
    return data

def settings_obj():
    return read_json(SET_FILE, {"version":"R8","port":PORT,"web_folder":"01 WEB","data_folder":"03 DATA","backup_folder":"04 BACKUP"})

def get_items():
    return inventory_obj().get("items", [])

def save_inventory_items(items, inv=None):
    if inv is None: inv = inventory_obj()
    inv["items"] = items
    inv["updated_at"] = now_text()
    if "summary" in inv and isinstance(inv["summary"], dict):
        inv["summary"]["master_part_count"] = len(items)
        inv["summary"]["total_stock"] = sum(to_num(x.get("현재고", x.get("current_stock",0))) for x in items)
    write_json(INV_FILE, inv)

def to_num(v):
    try:
        if v is None or v == "": return 0
        return int(float(str(v).replace(",", "")))
    except Exception:
        return 0

def norm(v): return "" if v is None else str(v).strip()

def row_key(p):
    return "|".join([norm(p.get("윤성관리번호") or p.get("ys_part_no")), norm(p.get("실입고품번") or p.get("actual_part_no")), norm(p.get("브랜드") or p.get("maker")), norm(p.get("대표품번") or p.get("represent_part_no"))])

def find_part(items, query=None, key=None):
    if key:
        for p in items:
            if row_key(p) == key: return p
    q = norm(query).upper()
    if not q: return None
    fields = ["윤성관리번호","YS품번","ys_part_no","대표품번","represent_part_no","실입고품번","actual_part_no","OEM번호","바코드","part_id"]
    for p in items:
        if any(norm(p.get(f)).upper() == q for f in fields): return p
    for p in items:
        if any(q in norm(p.get(f)).upper() for f in fields): return p
    return None

def add_history(entry):
    h = history_obj()
    h["histories"].insert(0, entry)
    h["last_updated"] = now_text()
    write_json(HIS_FILE, h)

def create_response(ok=True, **kwargs):
    d={"ok":ok}; d.update(kwargs); return d

class Handler(BaseHTTPRequestHandler):
    server_version = "YSMPartsR8/1.0"
    def log_message(self, fmt, *args):
        print("[%s] %s" % (now_text(), fmt%args))
    def _send(self, code=200, ctype="application/json; charset=utf-8", body=b""):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
    def send_json(self, obj, code=200):
        self._send(code, "application/json; charset=utf-8", json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"))
    def do_OPTIONS(self): self._send(204)
    def do_GET(self):
        try:
            path = urllib.parse.urlparse(self.path).path
            if path in ("/api/health", "/api/status"):
                return self.send_json(create_response(True, root=str(ROOT), web=str(WEB_DIR), data=str(DATA_DIR), backup=str(BACKUP_DIR), version="R8"))
            if path in ("/api/iveco/health", "/api/iveco/status"):
                inv = iveco_inventory_obj()
                return self.send_json(create_response(True, module="IVECO", root=str(IVECO_DIR), app=str(IVECO_APP_DIR), data=str(IVECO_DATA_DIR), backup=str(IVECO_BACKUP_DIR), items=len(inv.get("items", []))))
            if path == "/api/iveco/load":
                inv = iveco_inventory_obj(); log = iveco_log_obj(); users = iveco_users_obj()
                return self.send_json(create_response(True, module="IVECO", data=inv, items=inv.get("items", []), logs=log.get("logs", []), users=users.get("users", []), counts={"items": len(inv.get("items", [])), "logs": len(log.get("logs", [])), "users": len(users.get("users", []))}))
            if path == "/api/iveco/history":
                return self.send_json(iveco_log_obj())
            if path == "/api/iveco/users":
                return self.send_json(iveco_users_obj())
            if path == "/api/load":
                inv=inventory_obj(); his=history_obj(); aud=audit_obj(); sett=settings_obj()
                return self.send_json(create_response(True, parts=inv.get("items",[]), histories=his.get("histories",[]), auditSessions=aud.get("audit_sessions",[]), settings=sett, counts={"parts":len(inv.get("items",[])),"histories":len(his.get("histories",[])),"auditSessions":len(aud.get("audit_sessions",[]))}))
            if path == "/api/history": return self.send_json(history_obj())
            if path == "/api/audit_sessions": return self.send_json(audit_obj())
            if path == "/api/dashboard":
                items=get_items()
                low=[p for p in items if to_num(p.get("현재고",p.get("current_stock"))) <= to_num(p.get("안전재고",p.get("safe_stock")))]
                return self.send_json(create_response(True, total=len(items), stock=sum(to_num(p.get("현재고",p.get("current_stock"))) for p in items), low=len(low)))
            if path in ("/iveco", "/iveco/", "/iveco/index.html"):
                f = IVECO_APP_DIR / "index.html"
            elif path.startswith("/iveco/assets/"):
                safe = path.replace("/iveco/assets/", "", 1).replace("..", "")
                f = IVECO_ASSETS_DIR / safe
            elif path in ("/", "", "/index.html"):
                f=WEB_DIR/"index.html"
            else:
                safe = path.lstrip("/").replace("..", "")
                f=WEB_DIR/safe
            if f.exists() and f.is_file():
                ctype=mimetypes.guess_type(str(f))[0] or "application/octet-stream"
                return self._send(200, ctype+"; charset=utf-8" if ctype.startswith("text") else ctype, f.read_bytes())
            return self.send_json(create_response(False, error="not found", path=path), 404)
        except Exception as e:
            traceback.print_exc(); return self.send_json(create_response(False, error=str(e)), 500)
    def read_body(self):
        length=int(self.headers.get("Content-Length",0)); raw=self.rfile.read(length) if length else b"{}"
        if not raw: return {}
        return json.loads(raw.decode("utf-8"))
    def do_POST(self):
        try:
            path=urllib.parse.urlparse(self.path).path
            body=self.read_body()
            if path == "/api/iveco/save":
                reason = body.get("reason", "iveco_save")
                data = body.get("data") or body.get("inventory")
                items = body.get("items")
                logs = body.get("logs")
                users = body.get("users")

                inv = iveco_inventory_obj()
                if isinstance(data, dict):
                    data["updated_at"] = now_text()
                    write_iveco_json(IVECO_INV_FILE, data)
                elif isinstance(items, list):
                    inv["items"] = items
                    inv["updated_at"] = now_text()
                    write_iveco_json(IVECO_INV_FILE, inv)

                if isinstance(logs, list):
                    log = iveco_log_obj()
                    log["logs"] = logs
                    log["last_updated"] = now_text()
                    write_iveco_json(IVECO_LOG_FILE, log)

                if isinstance(users, list):
                    user_obj = iveco_users_obj()
                    user_obj["users"] = users
                    user_obj["last_updated"] = now_text()
                    write_iveco_json(IVECO_USERS_FILE, user_obj)

                made = iveco_backup_all(reason)
                return self.send_json(create_response(True, module="IVECO", saved=True, backup=made, data=str(IVECO_DATA_DIR)))

            if path == "/api/iveco/backup":
                return self.send_json(create_response(True, module="IVECO", backup=iveco_backup_all(body.get("reason", "manual"))))

            if path == "/api/save":
                reason=body.get("reason","snapshot")
                parts=body.get("parts")
                histories=body.get("histories")
                auditSessions=body.get("auditSessions")
                inv=inventory_obj()
                if isinstance(parts, list):
                    inv["items"] = parts; inv["updated_at"] = now_text(); write_json(INV_FILE, inv)
                if isinstance(histories, list):
                    h=history_obj(); h["histories"] = histories; h["last_updated"] = now_text(); write_json(HIS_FILE, h)
                if isinstance(auditSessions, list):
                    a=audit_obj(); a["audit_sessions"] = auditSessions; a["last_updated"] = now_text(); write_json(AUD_FILE, a)
                made=backup_all(reason)
                return self.send_json(create_response(True, saved=True, backup=made))
            if path in ("/api/inbound", "/api/outbound", "/api/admin_adjust"):
                return self.handle_stock(path, body)
            if path == "/api/audit_save":
                return self.handle_audit_save(body)
            if path == "/api/audit_apply":
                return self.handle_audit_apply(body)
            if path == "/api/backup":
                return self.send_json(create_response(True, backup=backup_all(body.get("reason","manual"))))
            return self.send_json(create_response(False, error="unknown api", path=path), 404)
        except Exception as e:
            traceback.print_exc(); return self.send_json(create_response(False, error=str(e)), 500)
    def handle_stock(self, path, body):
        inv=inventory_obj(); items=inv.get("items",[])
        p=find_part(items, query=body.get("query"), key=body.get("key"))
        if not p: return self.send_json(create_response(False, error="part not found"), 404)
        before=to_num(p.get("현재고", p.get("current_stock",0)))
        qty=to_num(body.get("qty",0)); price=to_num(body.get("price",0)); user=body.get("user","관리자"); memo=body.get("memo",""); ref=body.get("ref","")
        if path == "/api/inbound":
            after=before+qty; kind="입고"; signed=qty
            p["최근매입가"] = price or p.get("최근매입가",0); p["last_buy_price"] = p["최근매입가"]; p["최종입고일"] = now_text()[:10]; p["last_in_at"] = p["최종입고일"]; p["거래처"] = ref or p.get("거래처","")
        elif path == "/api/outbound":
            after=before-qty; kind="출고"; signed=-qty
            p["최근출고가"] = price or p.get("최근출고가",0); p["last_sell_price"] = p["최근출고가"]; p["최종출고일"] = now_text()[:10]; p["last_out_at"] = p["최종출고일"]; p["사용횟수"] = to_num(p.get("사용횟수",0)) + qty
        else:
            after=qty; kind="관리자조정"; signed=after
        p["현재고"] = after; p["current_stock"] = after
        save_inventory_items(items, inv)
        add_history({"일자":now_text(),"구분":kind,"윤성관리번호":p.get("윤성관리번호"),"대표품번":p.get("대표품번"),"실입고품번":p.get("실입고품번"),"브랜드":p.get("브랜드"),"이전수량":before,"수량":signed,"차이":after-before,"단가":price,"거래처":ref,"담당자":user,"메모":memo})
        made=backup_all(kind)
        return self.send_json(create_response(True, before=before, after=after, diff=after-before, backup=made))
    def handle_audit_save(self, body):
        a=audit_obj()
        sess=body.get("session") or {}
        if not sess:
            sess={"id":body.get("id") or f"AUD-{stamp()}","일시":now_text(),"실사자":body.get("user","관리자"),"상태":"실사대기","항목수":len(body.get("items",[])),"items":body.get("items",[])}
        a["audit_sessions"].insert(0, sess)
        a["next_session_no"] = to_num(a.get("next_session_no",1))+1
        a["last_updated"] = now_text()
        write_json(AUD_FILE, a)
        add_history({"일자":now_text(),"구분":"실사대기","sessionId":sess.get("id"),"윤성관리번호":f"{sess.get('항목수', len(sess.get('items',[])))}개 항목","대표품번":"실사묶음 생성","거래처":"실사조사"})
        made=backup_all("audit_save")
        return self.send_json(create_response(True, session=sess, backup=made))
    def handle_audit_apply(self, body):
        sid=body.get("sessionId") or body.get("id")
        inv=inventory_obj(); items=inv.get("items",[]); a=audit_obj(); found=None
        for s in a.get("audit_sessions",[]):
            if s.get("id") == sid: found=s; break
        if not found: return self.send_json(create_response(False, error="session not found"), 404)
        if found.get("상태") != "실사대기": return self.send_json(create_response(False, error="not pending"), 400)
        applied=0
        for it in found.get("items",[]):
            p=find_part(items, key=it.get("key")) or find_part(items, query=it.get("윤성관리번호"))
            if not p: continue
            before=to_num(p.get("현재고",p.get("current_stock",0))); after=to_num(it.get("실사수량", before)); diff=after-before
            p["현재고"]=after; p["current_stock"]=after; p["최종실사일"]=now_text()[:10]; p["last_audit_at"]=p["최종실사일"]
            add_history({"일자":now_text(),"구분":"실사반영","sessionId":sid,"윤성관리번호":p.get("윤성관리번호"),"대표품번":p.get("대표품번"),"실입고품번":p.get("실입고품번"),"브랜드":p.get("브랜드"),"이전수량":before,"수량":after,"차이":diff,"거래처":"이력관리"})
            applied+=1
        found["상태"]="반영완료"; found["반영일시"]=now_text(); found["반영수량"]=applied
        save_inventory_items(items, inv); write_json(AUD_FILE, a)
        made=backup_all("audit_apply")
        return self.send_json(create_response(True, applied=applied, backup=made))

def local_ip():
    try:
        s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8",80)); ip=s.getsockname()[0]; s.close(); return ip
    except Exception: return "<SERVER-PC-IP>"

if __name__ == "__main__":
    print("----------------------------------------")
    print("YSM Parts Center R8 Storage Engine")
    print(f"Project ROOT: {ROOT}")
    print(f"Web folder  : {WEB_DIR}")
    print(f"Data folder : {DATA_DIR}")
    print(f"Backup      : {BACKUP_DIR}")
    print(f"IVECO app   : {IVECO_APP_DIR}")
    print(f"IVECO data  : {IVECO_DATA_DIR}")
    print(f"Local URL   : http://127.0.0.1:{PORT}")
    print(f"Network URL : http://{local_ip()}:{PORT}")
    print("APIs: /api/load /api/save /api/inbound /api/outbound /api/audit_save /api/audit_apply /api/admin_adjust")
    print("IVECO: /iveco /api/iveco/load /api/iveco/save /api/iveco/backup")
    print("----------------------------------------")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
