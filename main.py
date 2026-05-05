#!/usr/bin/env python3
import json, os, sys, time, hashlib, shutil, threading, importlib.util, queue
from datetime import datetime
import requests, websocket
from websocket import WebSocketApp
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from flask import Flask, render_template, request, jsonify

CONFIG_FILE = "config.json"
VERSION_FILE = "version.txt"
LOCK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locks")
os.makedirs(LOCK_DIR, exist_ok=True)

CURRENT_VERSION = "1.0.7"
if not os.path.exists(VERSION_FILE):
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(CURRENT_VERSION)
else:
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        CURRENT_VERSION = f.read().strip()

def load_config():
    if not os.path.exists(CONFIG_FILE):
        template = {
            "accounts": [],
            "WEB_PORT": 5000,
            "WEB_PASSWORD": "admin",
            "API_TOKEN": "请修改",
            "AUTO_UPDATE": False,
            "UPDATE_URL": ""
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    config.setdefault("accounts", [])
    config.setdefault("WEB_PORT", 5000)
    config.setdefault("WEB_PASSWORD", "admin")
    config.setdefault("API_TOKEN", "请修改")
    config.setdefault("AUTO_UPDATE", False)
    config.setdefault("UPDATE_URL", "")
    return config

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

config = load_config()
ACCOUNTS = config["accounts"]
GLOBAL_WEB_PORT = config["WEB_PORT"]
GLOBAL_WEB_PASSWORD = config["WEB_PASSWORD"]
GLOBAL_API_TOKEN = config["API_TOKEN"]
AUTO_UPDATE = config.get("AUTO_UPDATE", False)
UPDATE_URL = config.get("UPDATE_URL", "")

bot_start_time = datetime.now()
log_buffer = []
LOG_MAX_LINES = 200
log_lock = threading.Lock()

admin_list = set()
ADMIN_FILE = "admin_list.json"
user_blacklist = set()
USER_BLACKLIST_FILE = "user_blacklist.json"
group_blacklist = set()
GROUP_BLACKLIST_FILE = "group_blacklist.json"

ai_semaphore = threading.Semaphore(4)
instances = {}

def load_global_data():
    global admin_list, user_blacklist, group_blacklist
    for file, target in [
        (ADMIN_FILE, admin_list), (USER_BLACKLIST_FILE, user_blacklist), (GROUP_BLACKLIST_FILE, group_blacklist)
    ]:
        if os.path.exists(file):
            try:
                with open(file, "r") as f:
                    target.update(json.load(f))
            except:
                pass
    save_admin_list()
    save_user_blacklist()
    save_group_blacklist()

def save_admin_list():
    with open(ADMIN_FILE, "w") as f:
        json.dump(list(admin_list), f)

def save_user_blacklist():
    with open(USER_BLACKLIST_FILE, "w") as f:
        json.dump(list(user_blacklist), f)

def save_group_blacklist():
    with open(GROUP_BLACKLIST_FILE, "w") as f:
        json.dump(list(group_blacklist), f)

load_global_data()

def get_lock_path(msg_id, group_id, uid):
    return os.path.join(LOCK_DIR, f"{msg_id}_{group_id}_{uid}.lock")

def is_message_processed(msg_id, group_id, uid):
    lock_file = get_lock_path(msg_id, group_id, uid)
    if os.path.exists(lock_file):
        return True
    try:
        with open(lock_file, 'w') as f:
            f.write(str(time.time()))
        return False
    except:
        return True

def clean_old_locks():
    while True:
        time.sleep(300)
        now = time.time()
        for f in os.listdir(LOCK_DIR):
            path = os.path.join(LOCK_DIR, f)
            if os.path.isfile(path) and now - os.path.getmtime(path) > 600:
                try:
                    os.remove(path)
                except:
                    pass

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    print(line)
    with log_lock:
        log_buffer.append(line)
        if len(log_buffer) > LOG_MAX_LINES:
            log_buffer.pop(0)

AI_API_URL = "https://api.s01s.cn/API/kimi/"
AI_TIMEOUT = 120
def call_ai_api(question, user_id):
    params = {"id": 8888888888, "text": question}
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://api.s01s.cn/API/kimi/'}
    try:
        resp = requests.get(AI_API_URL, params=params, headers=headers, timeout=AI_TIMEOUT)
        return resp.text.strip() or "AI 返回了空内容。"
    except Exception as e:
        return f"AI 请求失败：{str(e)}"

class BotInstance:
    def __init__(self, cfg):
        self.qq = cfg["SELF_QQ"]
        self.ws_url = cfg["WS_URL"]
        self.token = cfg["TOKEN"]
        self.plugin_id = cfg.get("PLUGIN_ID", "")
        self.plugin_name = cfg.get("PLUGIN_NAME", "")
        self.target_group = cfg.get("TARGET_GROUP", "")
        self.plugin_dir = os.path.join("BOT", self.qq)
        os.makedirs(self.plugin_dir, exist_ok=True)

        self.seq = 0
        self.seq_lock = threading.Lock()
        self.plugins = {}
        self.plugin_enabled = {}
        self.plugin_admin_only = {}
        self.send_queue = queue.Queue()
        self.ws = None
        self.ws_lock = threading.Lock()
        self._stop_event = threading.Event()
        self.start_time = datetime.now()

    def log(self, msg, level="INFO"):
        log(f"[{self.qq}] {msg}", level)

    def get_seq(self):
        with self.seq_lock:
            self.seq += 1
            return self.seq

    def load_plugins(self):
        config_file = f"plugin_config_{self.qq}.json"
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                saved = json.load(f)
                self.plugin_enabled = saved.get("enabled", {})
                self.plugin_admin_only = saved.get("admin_only", {})
        else:
            self.plugin_enabled, self.plugin_admin_only = {}, {}
        new_plugins = {}
        for fname in os.listdir(self.plugin_dir):
            if fname.endswith(".py"):
                cmd = fname[:-3]
                if cmd not in self.plugin_enabled:
                    self.plugin_enabled[cmd] = True
                if cmd not in self.plugin_admin_only:
                    self.plugin_admin_only[cmd] = False
                if not self.plugin_enabled[cmd]:
                    continue
                path = os.path.join(self.plugin_dir, fname)
                spec = importlib.util.spec_from_file_location(f"{self.qq}_{cmd}", path)
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                except Exception as e:
                    self.log(f"加载插件 {fname} 失败: {e}", "ERROR")
                    continue
                if hasattr(module, "run"):
                    new_plugins[cmd] = module.run
        self.plugins = new_plugins
        with open(config_file, "w") as f:
            json.dump({"enabled": self.plugin_enabled, "admin_only": self.plugin_admin_only}, f, indent=2)
        self.log(f"插件加载完成，共 {len(self.plugins)} 个")

    def enable_plugin(self, name, enable=True):
        if name in self.plugin_enabled:
            self.plugin_enabled[name] = enable
            self.load_plugins()

    def set_plugin_admin(self, name, admin_only):
        if name in self.plugin_admin_only:
            self.plugin_admin_only[name] = admin_only
            with open(f"plugin_config_{self.qq}.json", "w") as f:
                json.dump({"enabled": self.plugin_enabled, "admin_only": self.plugin_admin_only}, f, indent=2)
            self.load_plugins()

    def sender_worker(self):
        while not self._stop_event.is_set():
            try:
                packet = self.send_queue.get(timeout=1)
                with self.ws_lock:
                    ws = self.ws
                if ws and ws.sock and ws.sock.connected:
                    ws.send(json.dumps(packet))
                else:
                    self.log("WS断开，丢弃消息", "WARN")
                self.send_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.log(f"发送异常: {e}", "ERROR")

    def _enqueue(self, pkt):
        if "seq" not in pkt or pkt["seq"] == 0:
            pkt["seq"] = self.get_seq()
        self.send_queue.put(pkt)

    def send_group_msg(self, gid, text):
        self._enqueue({
            "seq": self.get_seq(), "cmd": "SendOicqMsg", "rsp": True,
            "data": [{"Account": self.qq, "Group": "Group", "GroupId": gid}, {"Text": text}]
        })

    def send_raw(self, packet):
        self._enqueue(packet)

    def handle_push(self, msg_data):
        if not isinstance(msg_data, list) or len(msg_data) < 2:
            return
        msg_id = group_id = sender_qq = None
        text = ""
        for item in msg_data:
            if isinstance(item, dict):
                if "MsgId" in item:
                    msg_id = item["MsgId"]
                if "GroupId" in item:
                    group_id = item["GroupId"]
                if "Uin" in item:
                    sender_qq = str(item["Uin"])
                if "Text" in item:
                    text += item["Text"]
        if not group_id or not text:
            return
        if msg_id and group_id and is_message_processed(msg_id, group_id, self.qq):
            return
        if group_id in group_blacklist or sender_qq in user_blacklist:
            return

        if text.startswith("AI ") or text == "AI":
            question = text[3:].strip() if len(text) > 2 else ""
            if not question:
                self.send_group_msg(group_id, "请问你想问什么？例如：AI 如何开发插件")
                return
            def do_ai():
                with ai_semaphore:
                    try:
                        reply = call_ai_api(question, sender_qq or group_id)
                        self.send_group_msg(group_id, reply)
                    except Exception as e:
                        self.send_group_msg(group_id, f"AI 异常：{e}")
            threading.Thread(target=do_ai, daemon=True).start()
            return

        if sender_qq in admin_list:
            parts = text.split(maxsplit=1)
            if len(parts) == 2:
                cmd, arg = parts[0], parts[1]
                if cmd == "禁用群" and arg.isdigit():
                    group_blacklist.add(arg)
                    save_group_blacklist()
                    self.send_group_msg(group_id, f"已禁用群 {arg}")
                    return
                elif cmd == "启用群" and arg.isdigit():
                    group_blacklist.discard(arg)
                    save_group_blacklist()
                    self.send_group_msg(group_id, f"已启用群 {arg}")
                    return

        for cmd, func in list(self.plugins.items()):
            if text == cmd or (text.startswith(cmd) and len(text) > len(cmd) and text[len(cmd)] == ' '):
                if self.plugin_admin_only.get(cmd, False) and sender_qq not in admin_list:
                    self.send_group_msg(group_id, "此命令仅限管理员使用")
                    return
                self.log(f"触发插件: {cmd}")
                def send_msg(arg1, arg2=None):
                    if arg2 is None:
                        if isinstance(arg1, dict):
                            self.send_raw(arg1)
                        elif isinstance(arg1, bytes):
                            with self.ws_lock:
                                ws = self.ws
                            if ws:
                                ws.send(arg1, opcode=websocket.ABNF.OPCODE_BINARY)
                    else:
                        self.send_group_msg(arg1, arg2)
                try:
                    func(msg_data, send_msg)
                except Exception as e:
                    err = f"插件 {cmd} 执行出错: {e}"
                    self.log(err, "ERROR")
                    self.send_group_msg(group_id, f"[错误] {err}")
                return

    def on_open(self, ws):
        with self.ws_lock:
            self.ws = ws
        threading.Thread(target=self.sender_worker, daemon=True).start()
        self.log("WebSocket 已连接")
        self._enqueue({
            "seq": self.get_seq(), "cmd": "SyncOicq", "rsp": True,
            "data": {"pid": self.plugin_id, "name": self.plugin_name, "token": self.token}
        })

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            cmd = data.get("cmd")
            if cmd == "Response":
                resp = data.get("data")
                status = None
                if isinstance(resp, dict):
                    status = resp.get("status")
                elif isinstance(resp, list) and resp:
                    status = resp[0].get("status")
                if status is True:
                    self.log("上线成功")
                    self.send_group_msg(self.target_group, f"机器人 {self.qq} 已连接服务器")
                elif status is False:
                    self.log("Token错误", "ERROR")
                    ws.close()
            elif cmd == "PushOicqMsg":
                self.handle_push(data.get("data", []))
        except Exception as e:
            self.log(f"消息处理异常: {e}", "ERROR")

    def on_error(self, ws, error):
        self.log(f"WebSocket 错误: {error}", "ERROR")

    def on_close(self, ws, code, msg):
        self.log("连接关闭")
        with self.ws_lock:
            self.ws = None

    def stop(self):
        self._stop_event.set()
        with self.ws_lock:
            if self.ws:
                try:
                    self.ws.close()
                except:
                    pass
                self.ws = None

    def run(self):
        self.load_plugins()
        while not self._stop_event.is_set():
            self.log(f"正在连接 {self.ws_url}")
            try:
                ws_app = WebSocketApp(self.ws_url,
                                      on_open=self.on_open,
                                      on_message=self.on_message,
                                      on_error=self.on_error,
                                      on_close=self.on_close)
                ws_app.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                self.log(f"连接异常: {e}", "ERROR")
            if self._stop_event.is_set():
                break
            time.sleep(5)

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = 'secluded_bot_secret'

def require_auth(f):
    def wrapper(*args, **kwargs):
        if GLOBAL_WEB_PASSWORD:
            auth = request.cookies.get('bot_auth')
            if auth != GLOBAL_WEB_PASSWORD:
                return render_template('login.html')
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@app.route('/')
@require_auth
def index():
    return render_template('dashboard.html')

@app.route('/login', methods=['POST'])
def login():
    pwd = request.form.get('password')
    if pwd == GLOBAL_WEB_PASSWORD:
        resp = jsonify({'success': True})
        resp.set_cookie('bot_auth', GLOBAL_WEB_PASSWORD, max_age=86400)
        return resp
    return jsonify({'success': False, 'error': '密码错误'}), 401

@app.route('/api/status')
@require_auth
def api_status():
    insts = []
    for qq, bot in instances.items():
        insts.append({
            "qq": qq,
            "connected": bot.ws is not None,
            "uptime": str(datetime.now() - bot.start_time).split('.')[0],
            "plugins": list(bot.plugins.keys()),
            "plugin_enabled": bot.plugin_enabled,
            "plugin_admin_only": bot.plugin_admin_only
        })
    return jsonify({
        "instances": insts,
        "admin_list": list(admin_list),
        "user_blacklist": list(user_blacklist),
        "group_blacklist": list(group_blacklist),
        "log_lines": log_buffer[-50:],
        "current_version": CURRENT_VERSION
    })

@app.route('/api/add_account', methods=['POST'])
@require_auth
def api_add_account():
    data = request.get_json()
    required = ["SELF_QQ", "WS_URL", "TOKEN"]
    for k in required:
        if not data.get(k):
            return jsonify({'error': f'缺少字段 {k}'}), 400
    qq = data['SELF_QQ']
    if qq in instances:
        return jsonify({'error': '账号已存在'}), 400
    acc = {
        "SELF_QQ": qq,
        "WS_URL": data["WS_URL"],
        "TOKEN": data["TOKEN"],
        "PLUGIN_ID": data.get("PLUGIN_ID", ""),
        "PLUGIN_NAME": data.get("PLUGIN_NAME", ""),
        "TARGET_GROUP": data.get("TARGET_GROUP", "")
    }
    config["accounts"].append(acc)
    save_config(config)
    bot = BotInstance(acc)
    instances[qq] = bot
    threading.Thread(target=bot.run, daemon=True).start()
    log(f"新账号添加: {qq}")
    return jsonify({'success': True, 'qq': qq})

@app.route('/api/remove_account', methods=['POST'])
@require_auth
def api_remove_account():
    qq = request.get_json().get('qq')
    if not qq:
        return jsonify({'error': '缺少qq'}), 400
    bot = instances.pop(qq, None)
    if bot:
        bot.stop()
        log(f"账号 {qq} 已移除")
    config["accounts"] = [a for a in config["accounts"] if a["SELF_QQ"] != qq]
    save_config(config)
    return jsonify({'success': True})

@app.route('/api/restart_account', methods=['POST'])
@require_auth
def api_restart_account():
    qq = request.get_json().get('qq')
    if not qq:
        return jsonify({'error': '缺少qq'}), 400
    bot = instances.pop(qq, None)
    if bot:
        bot.stop()
    acc = next((a for a in config["accounts"] if a["SELF_QQ"] == qq), None)
    if acc:
        new_bot = BotInstance(acc)
        instances[qq] = new_bot
        threading.Thread(target=new_bot.run, daemon=True).start()
        log(f"账号 {qq} 已重启")
        return jsonify({'success': True})
    return jsonify({'error': '账号不存在'}), 404

@app.route('/api/enable_plugin', methods=['POST'])
@require_auth
def api_enable_plugin():
    data = request.get_json()
    qq, name, enable = data.get('qq'), data.get('name'), data.get('enable', True)
    bot = instances.get(qq)
    if not bot:
        return jsonify({'error': '账号不存在'}), 404
    bot.enable_plugin(name, enable)
    return jsonify({'success': True})

@app.route('/api/set_plugin_admin', methods=['POST'])
@require_auth
def api_set_plugin_admin():
    data = request.get_json()
    qq, name, admin_only = data.get('qq'), data.get('name'), data.get('admin_only', False)
    bot = instances.get(qq)
    if not bot:
        return jsonify({'error': '账号不存在'}), 404
    bot.set_plugin_admin(name, admin_only)
    return jsonify({'success': True})

@app.route('/api/add_admin', methods=['POST'])
@require_auth
def api_add_admin():
    qq = str(request.get_json().get('qq', ''))
    if not qq.isdigit():
        return jsonify({'error': 'QQ号必须为数字'}), 400
    admin_list.add(qq)
    save_admin_list()
    return jsonify({'success': True})

@app.route('/api/remove_admin', methods=['POST'])
@require_auth
def api_remove_admin():
    qq = str(request.get_json().get('qq', ''))
    admin_list.discard(qq)
    save_admin_list()
    return jsonify({'success': True})

@app.route('/api/add_user_blacklist', methods=['POST'])
@require_auth
def api_add_user_blacklist():
    qq = str(request.get_json().get('qq', ''))
    if not qq.isdigit():
        return jsonify({'error': 'QQ号必须为数字'}), 400
    user_blacklist.add(qq)
    save_user_blacklist()
    return jsonify({'success': True})

@app.route('/api/remove_user_blacklist', methods=['POST'])
@require_auth
def api_remove_user_blacklist():
    qq = str(request.get_json().get('qq', ''))
    user_blacklist.discard(qq)
    save_user_blacklist()
    return jsonify({'success': True})

@app.route('/api/add_group_blacklist', methods=['POST'])
@require_auth
def api_add_group_blacklist():
    g = str(request.get_json().get('group', ''))
    if not g.isdigit():
        return jsonify({'error': '群号必须为数字'}), 400
    group_blacklist.add(g)
    save_group_blacklist()
    return jsonify({'success': True})

@app.route('/api/remove_group_blacklist', methods=['POST'])
@require_auth
def api_remove_group_blacklist():
    g = str(request.get_json().get('group', ''))
    group_blacklist.discard(g)
    save_group_blacklist()
    return jsonify({'success': True})

@app.route('/api/send', methods=['POST'])
@require_auth
def api_send():
    data = request.get_json()
    qq, group, text = data.get('qq'), data.get('group_id'), data.get('text')
    if not qq or not text:
        return jsonify({'error': '参数缺失'}), 400
    bot = instances.get(qq)
    if not bot:
        return jsonify({'error': '账号不存在'}), 404
    if not bot.ws:
        return jsonify({'error': '未连接'}), 503
    bot.send_group_msg(group, text)
    return jsonify({'success': True})

@app.route('/api/ai_chat', methods=['POST'])
@require_auth
def api_ai_chat():
    question = request.get_json().get('question', '').strip()
    if not question:
        return jsonify({'error': '问题不能为空'}), 400
    with ai_semaphore:
        reply = call_ai_api(question, "web")
    return jsonify({'reply': reply})

@app.route('/api/check_update', methods=['POST'])
@require_auth
def api_check_update():
    return jsonify({'success': True, 'msg': '手动更新暂未实现'})

class HotReloadHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.is_directory or not event.src_path.endswith(".py"):
            return
        for bot in instances.values():
            if event.src_path.startswith(bot.plugin_dir + os.sep):
                bot.load_plugins()
                break

def main():
    threading.Thread(target=clean_old_locks, daemon=True).start()
    for acc in config["accounts"]:
        bot = BotInstance(acc)
        instances[acc["SELF_QQ"]] = bot
        threading.Thread(target=bot.run, daemon=True).start()
    observer = Observer()
    observer.schedule(HotReloadHandler(), "BOT", recursive=True)
    observer.start()
    web_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=GLOBAL_WEB_PORT, debug=False, use_reloader=False),
        daemon=True
    )
    web_thread.start()
    log(f"Web 面板已启动，端口 {GLOBAL_WEB_PORT}，默认密码 {GLOBAL_WEB_PASSWORD}")
    while True:
        time.sleep(10)

if __name__ == "__main__":
    main()
