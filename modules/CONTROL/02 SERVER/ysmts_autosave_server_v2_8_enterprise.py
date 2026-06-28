# YSMTS 업무관제센터 V2.8 Enterprise R2 네트워크 자동저장 서버
# 서버PC 1대에서 실행, 모든 PC는 http://서버PC_IP:8765 접속
# 기본 저장 위치: \\SVR-DC7CM66A0RF\WorkImages\업무관제센터\ysmts_work_vehicle_v25.json
# 필요시 환경변수 YSMTS_SAVE_DIR 로 저장 폴더를 변경할 수 있음.

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import json, time, os, shutil, threading, socket, traceback
from queue import Queue

HOST = "0.0.0.0"
PORT = 8765
DEFAULT_SAVE_DIR = r"\\SVR-DC7CM66A0RF\WorkImages\업무관제센터"
SAVE_DIR = Path(os.environ.get("YSMTS_SAVE_DIR", DEFAULT_SAVE_DIR))
SAVE_FILE = SAVE_DIR / "ysmts_work_vehicle_v25.json"
BACKUP_DIR = SAVE_DIR / "backup"
HTML_FILE = Path(__file__).with_name("ysmts_work_control_center_v2_8_enterprise.html")
PACKAGE_JSON = Path(__file__).with_name("ysmts_work_vehicle_v25.json")
LOCK = threading.RLock()
SAVE_QUEUE = Queue()
LAST_BACKUP = 0
LAST_SAVE_RESULT = {"ok": False, "error": "저장 전", "savedAt": "", "path": str(SAVE_FILE)}
LAST_DIR_ERROR = ""
BACKUP_INTERVAL_SEC = 300
CLIENT_TTL_SEC = 90
CLIENTS = {}

STATUS = ["미입고", "접수대기", "점검대기", "점검중", "작업대기", "작업중", "작업완료", "출고대기", "출고", "완료"]
ARRAY_KEYS = ["vehicles", "messages", "logs", "templates", "audit", "handovers"]
DEFAULT_OPTIONS = {
    "kinds": ["예약입고", "현장입고", "일반업무"],
    "statuses": STATUS,
    "workers": ["김정비", "박정비", "부품실", "사무실", "대표", "이부장님"],
    "makers": ["IVECO", "BMW", "BENZ", "AUDI", "VW", "HYUNDAI", "KIA", "LAND ROVER", "MASERATI"],
    "workItems": ["엔진오일", "DPF 점검", "진단점검", "브레이크", "하체점검", "전기장치", "시운전"],
    "priorities": ["긴급", "높음", "보통", "낮음"],
    "messageChannels": ["전체공지", "정비1반", "정비2반", "부품실", "사무실"],
    "messageTemplates": ["작업 시작 바랍니다.", "점검 결과 확인 바랍니다.", "부품 도착했습니다. 작업 진행 바랍니다.", "고객 승인 대기중입니다.", "시운전 후 결과 남겨주세요.", "출고 준비 바랍니다.", "긴급 확인 바랍니다."],
    "messageTypes": ["작업일지", "고객협의", "추가발견", "출고메모", "일반메모"],
}

def now_text(): return time.strftime("%Y-%m-%d %H:%M:%S")

def ensure_dirs():
    """네트워크 경로가 끊겨도 서버는 죽이지 않고 오류를 반환한다."""
    global LAST_DIR_ERROR
    try:
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        LAST_DIR_ERROR = ""
        return True, ""
    except Exception as e:
        LAST_DIR_ERROR = str(e)
        return False, LAST_DIR_ERROR

def compact(s): return str(s or "").replace(" ", "").strip().upper()

def stamp_score(x):
    for k in ("updatedMs", "createdMs"):
        try: return int(x.get(k) or 0)
        except Exception: pass
    for k in ("updatedAt", "createdAt"):
        try: return int(time.mktime(time.strptime(str(x.get(k)), "%Y-%m-%d %H:%M:%S")))
        except Exception: pass
    return 0

def better_dict(a, b):
    out = {**a, **b} if stamp_score(b) >= stamp_score(a) else {**b, **a}
    if isinstance(a.get("statusHistory"), list) or isinstance(b.get("statusHistory"), list):
        hist, seen = [], set()
        for h in (a.get("statusHistory") or []) + (b.get("statusHistory") or []):
            key = json.dumps(h, ensure_ascii=False, sort_keys=True) if isinstance(h, dict) else str(h)
            if key not in seen: hist.append(h); seen.add(key)
        out["statusHistory"] = hist
    return out

def vehicle_key(v):
    job = compact(v.get("jobNo")); car = compact(v.get("carNo")); date = str(v.get("date") or "").strip()
    if job and car: return f"JOBCAR|{job}|{car}"
    if car and date: return f"CARDATE|{car}|{date}"
    return ""

def normalize_vehicle(v):
    if not isinstance(v, dict): return None
    if not v.get("id"): v["id"] = f"srv-{int(time.time()*1000)}"
    if v.get("status") == "부품대기": v["status"] = "작업대기"
    if v.get("status") not in STATUS: v["status"] = "접수대기"
    if not isinstance(v.get("milestones"), dict): v["milestones"] = {}
    return v

def dedupe_vehicles(items):
    by_id, by_key = {}, {}
    for item in items if isinstance(items, list) else []:
        item = normalize_vehicle(item)
        if not item: continue
        by_id[item["id"]] = better_dict(by_id[item["id"]], item) if item["id"] in by_id else item
    for item in by_id.values():
        k = vehicle_key(item) or "ID|" + item.get("id", "")
        by_key[k] = better_dict(by_key[k], item) if k in by_key else item
    return list(by_key.values())

def merge_array(current, incoming):
    result = {}
    for arr in (current if isinstance(current, list) else []), (incoming if isinstance(incoming, list) else []):
        for item in arr:
            if isinstance(item, dict) and item.get("id"):
                old = result.get(item["id"], {})
                result[item["id"]] = better_dict(old, item) if old else item
    return list(result.values())

def merge_options(a, b):
    out = {}
    keys = set(DEFAULT_OPTIONS.keys()) | (set(a.keys()) if isinstance(a, dict) else set()) | (set(b.keys()) if isinstance(b, dict) else set())
    for k in keys:
        av = a.get(k) if isinstance(a, dict) else None
        bv = b.get(k) if isinstance(b, dict) else None
        src = bv if isinstance(bv, list) else av if isinstance(av, list) else DEFAULT_OPTIONS.get(k, [])
        out[k] = list(dict.fromkeys(src)) if isinstance(src, list) else src
    out["statuses"] = STATUS[:]
    return out

def normalize_db(data):
    if not isinstance(data, dict): data = {}
    data["version"] = "2.8E-R2"
    data["vehicles"] = dedupe_vehicles(data.get("vehicles", []))
    for k in ARRAY_KEYS:
        if k != "vehicles" and not isinstance(data.get(k), list): data[k] = []
    data["options"] = merge_options(data.get("options", {}), {})
    data["savePath"] = str(SAVE_FILE)
    data["fileName"] = SAVE_FILE.name
    return data

def read_json_file(path: Path):
    ok, err = ensure_dirs()
    if not ok: raise RuntimeError("저장 폴더 접근 실패: " + err)
    if not path.exists():
        # 최초 설치 편의: 패키지에 동봉된 JSON이 있으면 서버 폴더로 복사한다.
        if PACKAGE_JSON.exists() and PACKAGE_JSON.resolve() != path.resolve():
            shutil.copy2(PACKAGE_JSON, path)
        else:
            return normalize_db({})
    last = {}
    for _ in range(5):
        try:
            txt = path.read_text(encoding="utf-8")
            last = json.loads(txt) if txt.strip() else {}
            return normalize_db(last)
        except Exception:
            time.sleep(0.15)
    return normalize_db(last)

def merge_db(current, incoming):
    current, incoming = normalize_db(current), normalize_db(incoming)
    merged = {**current, **incoming}
    for k in ARRAY_KEYS:
        merged[k] = merge_array(current.get(k, []), incoming.get(k, []))
    merged["vehicles"] = dedupe_vehicles(merged.get("vehicles", []))
    merged["options"] = merge_options(current.get("options", {}), incoming.get("options", {}))
    merged["serverSavedAt"] = now_text()
    merged["savePath"] = str(SAVE_FILE)
    merged["fileName"] = SAVE_FILE.name
    return normalize_db(merged)

def backup_if_needed():
    global LAST_BACKUP
    if SAVE_FILE.exists() and time.time() - LAST_BACKUP > BACKUP_INTERVAL_SEC:
        shutil.copy2(SAVE_FILE, BACKUP_DIR / f"ysmts_work_vehicle_v25_{time.strftime('%Y%m%d_%H%M%S')}.json")
        LAST_BACKUP = time.time()

def write_json_safe(data):
    ok, err = ensure_dirs()
    if not ok: return False, "저장 폴더 접근 실패: " + err
    try: backup_if_needed()
    except Exception as e: return False, "백업 실패: " + str(e)
    payload = json.dumps(normalize_db(data), ensure_ascii=False, indent=2)
    temp_file = SAVE_DIR / f".{SAVE_FILE.name}.{int(time.time()*1000)}.tmp"
    last_err = None
    for _ in range(10):
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(payload); f.flush(); os.fsync(f.fileno())
            try:
                os.replace(temp_file, SAVE_FILE)
            except PermissionError:
                with open(SAVE_FILE, "w", encoding="utf-8") as f:
                    f.write(payload); f.flush(); os.fsync(f.fileno())
                try: temp_file.unlink(missing_ok=True)
                except Exception: pass
            return True, ""
        except Exception as e:
            last_err = e; time.sleep(0.25)
    return False, str(last_err)

def clean_clients():
    cut = time.time() - CLIENT_TTL_SEC
    for k in list(CLIENTS.keys()):
        if CLIENTS[k].get("ts", 0) < cut: CLIENTS.pop(k, None)

def register_client(handler, data=None):
    ip = handler.client_address[0] if handler.client_address else "unknown"
    name = ""
    if isinstance(data, dict):
        c = data.get("client") or {}
        if isinstance(c, dict): name = str(c.get("user") or "")
    key = f"{ip}|{name or ip}"
    CLIENTS[key] = {"ip": ip, "user": name or ip, "lastSeen": now_text(), "ts": time.time()}
    clean_clients()

def client_list():
    clean_clients(); return [{"ip": v["ip"], "user": v["user"], "lastSeen": v["lastSeen"]} for v in CLIENTS.values()]

def local_ips():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127."): ips.add(ip)
    except Exception: pass
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(("8.8.8.8",80)); ips.add(s.getsockname()[0]); s.close()
    except Exception: pass
    return sorted(ips)

def test_write_permission():
    ok, err = ensure_dirs()
    if not ok: return False, "저장 폴더 접근 실패: " + err
    p = SAVE_DIR / ".ysmts_write_test.tmp"
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write("write-test " + now_text()); f.flush(); os.fsync(f.fileno())
        p.unlink(missing_ok=True); return True, ""
    except Exception as e:
        try: p.unlink(missing_ok=True)
        except Exception: pass
        return False, str(e)

def file_meta(run_write_test=False):
    dir_ok, dir_err = ensure_dirs()
    write_ok, write_err = (None, "")
    if run_write_test:
        write_ok, write_err = test_write_permission()
    data = normalize_db({})
    read_error = ""
    if dir_ok:
        try:
            data = read_json_file(SAVE_FILE) if SAVE_FILE.exists() or PACKAGE_JSON.exists() else normalize_db({})
        except Exception as e:
            read_error = str(e)
    mtime = ""
    size = 0
    if dir_ok and SAVE_FILE.exists():
        try:
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(SAVE_FILE.stat().st_mtime))
            size = SAVE_FILE.stat().st_size
        except Exception as e:
            read_error = read_error or str(e)
    try: backup_count = len([x for x in BACKUP_DIR.glob("*.json")]) if dir_ok and BACKUP_DIR.exists() else 0
    except Exception: backup_count = 0
    err = dir_err or read_error or write_err
    return {"ok": bool(dir_ok and (write_ok is not False)), "path": str(SAVE_FILE), "saveDir": str(SAVE_DIR), "fileName": SAVE_FILE.name,
            "jsonExists": bool(dir_ok and SAVE_FILE.exists()), "jsonMtime": mtime, "jsonSize": size,
            "vehicleCount": len([v for v in data.get("vehicles", []) if not v.get("deleted")]), "messageCount": len(data.get("messages", [])),
            "logCount": len(data.get("logs", [])), "backupDir": str(BACKUP_DIR), "backupExists": bool(dir_ok and BACKUP_DIR.exists()), "backupCount": backup_count,
            "writeTest": write_ok, "clients": client_list(), "lastSave": LAST_SAVE_RESULT, "queue": SAVE_QUEUE.qsize(),
            "serverTime": now_text(), "error": err, "dirOk": dir_ok}

def save_worker():
    global LAST_SAVE_RESULT
    while True:
        incoming, event = SAVE_QUEUE.get()
        try:
            with LOCK:
                current = read_json_file(SAVE_FILE)
                merged = merge_db(current, incoming)
                ok, err = write_json_safe(merged)
                LAST_SAVE_RESULT = {"ok": ok, "error": err, "savedAt": merged.get("serverSavedAt", now_text()), "path": str(SAVE_FILE)}
        except Exception as e:
            LAST_SAVE_RESULT = {"ok": False, "error": str(e), "savedAt": now_text(), "path": str(SAVE_FILE)}
        finally:
            event.set(); SAVE_QUEUE.task_done()

class Handler(BaseHTTPRequestHandler):
    def _headers(self, code=200, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
    def do_OPTIONS(self): self._headers(204)
    def do_GET(self):
        try:
            register_client(self)
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                html = HTML_FILE.read_text(encoding="utf-8")
                self._headers(200, "text/html; charset=utf-8"); self.wfile.write(html.encode("utf-8")); return
            if path in ("/api/status", "/api/verify"):
                data = file_meta(run_write_test=True); data.update({"host": HOST, "port": PORT, "ips": local_ips(), "time": now_text()})
                self._headers(200); self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8")); return
            if path == "/api/testsave":
                ok, err = test_write_permission(); data = file_meta(run_write_test=False)
                data.update({"ok": ok, "writeTest": ok, "error": err})
                self._headers(200 if ok else 500); self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8")); return
            if path == "/api/load":
                with LOCK:
                    data = read_json_file(SAVE_FILE); data["clients"] = client_list()
                self._headers(200); self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8")); return
            self._headers(404); self.wfile.write(json.dumps({"ok":False,"error":"not found"}).encode("utf-8"))
        except Exception as e:
            self._headers(500); self.wfile.write(json.dumps({"ok":False,"error":str(e), "path": str(SAVE_FILE)}, ensure_ascii=False).encode("utf-8"))
    def do_POST(self):
        if urlparse(self.path).path != "/api/save":
            self._headers(404); self.wfile.write(b"{}"); return
        try:
            length = int(self.headers.get("Content-Length", "0")); body = self.rfile.read(length).decode("utf-8")
            incoming = json.loads(body) if body.strip() else {}
            register_client(self, incoming)
            event = threading.Event(); SAVE_QUEUE.put((incoming, event)); event.wait(timeout=12)
            result = dict(LAST_SAVE_RESULT); result["clients"] = client_list()
            self._headers(200 if result.get("ok") else 500)
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            traceback.print_exc(); self._headers(500); self.wfile.write(json.dumps({"ok":False,"error":str(e), "path": str(SAVE_FILE)}, ensure_ascii=False).encode("utf-8"))
    def log_message(self, *args): pass

if __name__ == "__main__":
    threading.Thread(target=save_worker, daemon=True).start()
    ips = local_ips()
    meta = file_meta(run_write_test=True)
    print("YSMTS 업무관제센터 V2.8 Enterprise R2 네트워크 자동저장 서버")
    print("저장 위치:", SAVE_FILE)
    print("서버 폴더 상태:", "정상" if meta.get("dirOk") else "실패")
    if meta.get("error"): print("오류:", meta.get("error"))
    print("서버 바인딩: 0.0.0.0:%s" % PORT)
    print("이 PC 접속: http://127.0.0.1:%s" % PORT)
    for ip in ips: print("타 PC 접속: http://%s:%s" % (ip, PORT))
    print("----------------------------------------")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
