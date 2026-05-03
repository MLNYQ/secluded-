#!/usr/bin/env python3
import json
import os
import sys
import time
import hashlib
import shutil
import threading
import importlib.util
import queue
from datetime import datetime
import requests
import websocket
from websocket import WebSocketApp
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from flask import Flask, render_template, request, jsonify

CONFIG_FILE = "config.json"
VERSION_FILE = "version.txt"

LOCK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locks")
os.makedirs(LOCK_DIR, exist_ok=True)

def get_current_version():
    default_version = "1.0.4"
    if not os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            f.write(default_version)
        return default_version
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

def load_config():
    if not os.path.exists(CONFIG_FILE):
        template = {
            "WS_URL": "请填写",
            "TOKEN": "请填写",
            "PLUGIN_ID": "secluded.plugin.termux",
            "PLUGIN_NAME": "termux-bot",
            "TARGET_GROUP": "请填写",
            "SELF_QQ": "请填写",
            "PLUGIN_DIR": "BOT",
            "WEB_PORT": 5000,
            "WEB_PASSWORD": "请填写",
            "API_TOKEN": "请填写",
            "AUTO_UPDATE": True,
            "UPDATE_URL": "http://cj.slyun14.top/version.json"
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
        print(f"已生成配置文件 {CONFIG_FILE}，请编辑并填写实际值后重新启动程序。")
        sys.exit(0)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    required = ["WS_URL", "TOKEN", "TARGET_GROUP", "SELF_QQ", "WEB_PASSWORD", "API_TOKEN"]
    for key in required:
        value = config.get(key)
        if not value or value == "请填写":
            print(f"错误：配置文件 {CONFIG_FILE} 中的 {key} 未填写，请修改后重启。")
            sys.exit(0)
    defaults = {
        "AUTO_UPDATE": True,
        "UPDATE_URL": "http://cj.slyun14.top/version.json",
        "PLUGIN_DIR": "BOT",
        "WEB_PORT": 5000,
        "PLUGIN_ID": "secluded.plugin.termux",
        "PLUGIN_NAME": "termux-bot",
        "TARGET_GROUP": "",
        "SELF_QQ": "",
        "WEB_PASSWORD": "",
        "API_TOKEN": ""
    }
    for k, v in defaults.items():
        if k not in config:
            config[k] = v
    return config

config = load_config()
CURRENT_VERSION = get_current_version()

WS_URL = config["WS_URL"]
TOKEN = config["TOKEN"]
PLUGIN_ID = config["PLUGIN_ID"]
PLUGIN_NAME = config["PLUGIN_NAME"]
TARGET_GROUP = config["TARGET_GROUP"]
SELF_QQ = config["SELF_QQ"]
PLUGIN_DIR = config["PLUGIN_DIR"]
WEB_PORT = config["WEB_PORT"]
WEB_PASSWORD = config["WEB_PASSWORD"]
API_TOKEN = config["API_TOKEN"]
AUTO_UPDATE = config.get("AUTO_UPDATE", True)
UPDATE_URL = config.get("UPDATE_URL", "http://cj.slyun14.top/version.json")

seq = 0
seq_lock = threading.Lock()
plugins = {}
plugin_exports = {}
plugin_enabled = {}
plugin_admin_only = {}
bot_start_time = datetime.now()
current_ws = None
current_ws_lock = threading.Lock()
log_buffer = []
LOG_MAX_LINES = 200

admin_list = set()
ADMIN_FILE = "admin_list.json"
user_blacklist = set()
USER_BLACKLIST_FILE = "user_blacklist.json"
group_blacklist = set()
GROUP_BLACKLIST_FILE = "group_blacklist.json"

send_queue = queue.Queue()
ai_semaphore = threading.Semaphore(4)

def load_admin_list():
    global admin_list
    if os.path.exists(ADMIN_FILE):
        try:
            with open(ADMIN_FILE, "r") as f:
                admin_list = set(json.load(f))
        except:
            admin_list = set()
    else:
        admin_list = set()
        save_admin_list()

def save_admin_list():
    with open(ADMIN_FILE, "w") as f:
        json.dump(list(admin_list), f)

def load_user_blacklist():
    global user_blacklist
    if os.path.exists(USER_BLACKLIST_FILE):
        try:
            with open(USER_BLACKLIST_FILE, "r") as f:
                user_blacklist = set(json.load(f))
        except:
            user_blacklist = set()
    else:
        user_blacklist = set()
        save_user_blacklist()

def save_user_blacklist():
    with open(USER_BLACKLIST_FILE, "w") as f:
        json.dump(list(user_blacklist), f)

def load_group_blacklist():
    global group_blacklist
    if os.path.exists(GROUP_BLACKLIST_FILE):
        try:
            with open(GROUP_BLACKLIST_FILE, "r") as f:
                group_blacklist = set(json.load(f))
        except:
            group_blacklist = set()
    else:
        group_blacklist = set()
        save_group_blacklist()

def save_group_blacklist():
    with open(GROUP_BLACKLIST_FILE, "w") as f:
        json.dump(list(group_blacklist), f)

load_admin_list()
load_user_blacklist()
load_group_blacklist()

def get_lock_path(msg_id, group_id):
    key = f"{msg_id}_{group_id}"
    hash_key = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(LOCK_DIR, hash_key)

def is_message_processed(msg_id, group_id):
    lock_file = get_lock_path(msg_id, group_id)
    if os.path.exists(lock_file):
        return True
    with open(lock_file, 'w') as f:
        f.write(str(time.time()))
    return False

def clean_old_locks():
    while True:
        time.sleep(300)
        now = time.time()
        for fname in os.listdir(LOCK_DIR):
            filepath = os.path.join(LOCK_DIR, fname)
            if os.path.isfile(filepath) and now - os.path.getmtime(filepath) > 600:
                try:
                    os.remove(filepath)
                except:
                    pass

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    print(line)
    log_buffer.append(line)
    if len(log_buffer) > LOG_MAX_LINES:
        log_buffer.pop(0)

def get_seq():
    global seq
    with seq_lock:
        seq += 1
        return seq

def check_and_update(manual=False):
    if not AUTO_UPDATE and not manual:
        return
    try:
        resp = requests.get(UPDATE_URL, timeout=10)
        if resp.status_code != 200:
            log(f"检查更新失败：HTTP {resp.status_code}", "WARN")
            return
        data = resp.json()
        latest_version = data.get("version")
        download_url = data.get("url")
        version_download_url = data.get("version_url")
        if not latest_version or not download_url:
            log("版本信息格式错误", "WARN")
            return
        if latest_version == CURRENT_VERSION:
            log("当前已是最新版本", "INFO")
            return
        log(f"发现新版本 {latest_version}，开始下载...", "INFO")
        new_file = sys.argv[0] + ".new"
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(new_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        file_size = os.path.getsize(new_file)
        if file_size < 1000:
            log("下载文件大小异常，放弃更新", "ERROR")
            os.remove(new_file)
            return
        if "md5" in data:
            md5 = hashlib.md5(open(new_file, "rb").read()).hexdigest()
            if md5 != data["md5"]:
                log("文件校验失败，放弃更新", "ERROR")
                os.remove(new_file)
                return
        if version_download_url:
            new_version_file = VERSION_FILE + ".new"
            with requests.get(version_download_url, stream=True) as r:
                r.raise_for_status()
                with open(new_version_file, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            os.replace(new_version_file, VERSION_FILE)
        else:
            with open(VERSION_FILE, "w", encoding="utf-8") as vf:
                vf.write(latest_version)
        backup_file = sys.argv[0] + ".bak"
        shutil.copy(sys.argv[0], backup_file)
        log(f"已备份当前版本到 {backup_file}", "INFO")
        os.replace(new_file, sys.argv[0])
        log("更新完成，进程即将退出，将由 start.sh 自动重启", "INFO")
        sys.exit(0)
    except Exception as e:
        log(f"自动更新失败: {e}", "ERROR")

def save_plugin_config():
    with open("plugin_config.json", "w") as f:
        json.dump({
            "enabled": plugin_enabled,
            "admin_only": plugin_admin_only
        }, f, indent=2)

def load_plugins():
    global plugins, plugin_enabled, plugin_admin_only
    new_plugins = {}
    config_file = "plugin_config.json"
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            saved = json.load(f)
            plugin_enabled = saved.get("enabled", {})
            plugin_admin_only = saved.get("admin_only", {})
    else:
        plugin_enabled = {}
        plugin_admin_only = {}

    if not os.path.exists(PLUGIN_DIR):
        os.makedirs(PLUGIN_DIR)
        log(f"已创建插件目录: {PLUGIN_DIR}")
        return

    for filename in os.listdir(PLUGIN_DIR):
        if filename.endswith(".py"):
            cmd_name = filename[:-3]
            if cmd_name not in plugin_enabled:
                plugin_enabled[cmd_name] = True
            if cmd_name not in plugin_admin_only:
                plugin_admin_only[cmd_name] = False
            if plugin_enabled[cmd_name]:
                file_path = os.path.join(PLUGIN_DIR, filename)
                spec = importlib.util.spec_from_file_location(cmd_name, file_path)
                module = importlib.util.module_from_spec(spec)
                if cmd_name in sys.modules:
                    del sys.modules[cmd_name]
                try:
                    spec.loader.exec_module(module)
                except Exception as e:
                    log(f"加载插件 {filename} 失败: {e}", "ERROR")
                    continue
                if hasattr(module, "run"):
                    new_plugins[cmd_name] = module.run
                    log(f"加载插件: {cmd_name}")
                else:
                    log(f"插件 {filename} 缺少 run 函数", "WARN")
                if hasattr(module, "setup"):
                    ctx = {
                        "plugin_name": cmd_name,
                        "register_exports": lambda exports: register_plugin_exports(cmd_name, exports),
                        "get_plugin_exports": get_plugin_exports,
                        "call_plugin": call_plugin_by_name,
                        "is_admin": lambda qq: qq in admin_list,
                    }
                    try:
                        module.setup(ctx)
                    except Exception as e:
                        log(f"插件 {filename} setup 出错: {e}", "ERROR")
            else:
                log(f"插件 {cmd_name} 已禁用，跳过加载")
    plugins = new_plugins
    save_plugin_config()
    log(f"当前共 {len(plugins)} 个启用的插件: {list(plugins.keys())}")

def enable_plugin(name, enable=True):
    if name not in plugin_enabled:
        return
    plugin_enabled[name] = enable
    save_plugin_config()
    load_plugins()

def set_plugin_admin_only(name, admin_only):
    if name not in plugin_admin_only:
        return
    plugin_admin_only[name] = admin_only
    save_plugin_config()

def register_plugin_exports(plugin_name, exports):
    plugin_exports[plugin_name] = exports
    log(f"插件 {plugin_name} 已注册公共方法: {list(exports.keys())}")

def get_plugin_exports(plugin_name):
    return plugin_exports.get(plugin_name, {})

def call_plugin_by_name(plugin_name, func_name, *args, **kwargs):
    exports = get_plugin_exports(plugin_name)
    if func_name in exports:
        return exports[func_name](*args, **kwargs)
    raise AttributeError(f"插件 {plugin_name} 没有导出 {func_name}")

def sender_worker(ws):
    while True:
        packet = send_queue.get()
        try:
            if ws.sock and ws.sock.connected:
                ws.send(json.dumps(packet))
            else:
                log("WebSocket 未连接，丢弃一个待发消息", "WARN")
        except Exception as e:
            log(f"发送队列发送失败: {e}", "ERROR")
        send_queue.task_done()

def _enqueue_send(packet):
    if "seq" not in packet or packet["seq"] == 0:
        packet["seq"] = get_seq()
    send_queue.put(packet)

def send_raw(ws, packet):
    _enqueue_send(packet)
    log(f"加入队列：原始包 cmd={packet.get('cmd')}")

def send_binary(ws, binary_data):
    ws.send(binary_data, opcode=websocket.ABNF.OPCODE_BINARY)
    log(f"直接发送二进制包，长度: {len(binary_data)} 字节")

def send_group_message(ws, group_id, text):
    packet = {
        "seq": get_seq(),
        "cmd": "SendOicqMsg",
        "rsp": True,
        "data": [
            {"Account": SELF_QQ, "Group": "Group", "GroupId": group_id},
            {"Text": text}
        ]
    }
    _enqueue_send(packet)
    log(f"加入队列：群消息 -> {group_id}: {text}")

def send_log(ws, level, content):
    cmd_map = {"info": "PrintI", "debug": "PrintD", "error": "PrintE", "success": "PrintS", "warning": "PrintW"}
    cmd = cmd_map.get(level, "PrintI")
    packet = {"seq": get_seq(), "cmd": cmd, "data": content, "rsp": False}
    _enqueue_send(packet)

AI_API_URL = "https://api.s01s.cn/API/kimi/"
AI_TIMEOUT = 120

def call_ai_api(question, user_id):
    full_prompt = f"{question}"
    params = {"id": 8888888888, "text": full_prompt}
    url = AI_API_URL

    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36 EdgA/144.0.0.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate',
        'Referer': 'https://api.s01s.cn/API/kimi/',
        'Connection': 'keep-alive',
    }

    log(f"[AI] 请求 URL: {url}, id={user_id}, len={len(full_prompt)}", "DEBUG")
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=AI_TIMEOUT)
        log(f"[AI] 响应状态: {resp.status_code}", "DEBUG")
        raw_text = resp.text.strip()
        log(f"[AI] 原始响应: {raw_text[:500]}", "DEBUG")
        return raw_text if raw_text else "AI 返回了空内容。"
    except requests.exceptions.Timeout:
        log(f"[AI] 超时", "ERROR")
        return f"AI 请求超时（{AI_TIMEOUT}秒），请稍后重试。"
    except Exception as e:
        log(f"[AI] 异常: {type(e).__name__} - {e}", "ERROR")
        return f"AI 请求失败：{str(e)}"

def handle_message(msg_data, ws):
    if not isinstance(msg_data, list) or len(msg_data) < 2:
        return
    msg_id = None
    group_id = None
    sender_qq = None
    text_part = ""
    for item in msg_data:
        if isinstance(item, dict):
            if "MsgId" in item:
                msg_id = item["MsgId"]
            if "GroupId" in item:
                group_id = item["GroupId"]
            if "Uin" in item:
                sender_qq = str(item["Uin"])
            if "Text" in item:
                text_part += item["Text"]
    if not group_id or not text_part:
        return
    if msg_id and group_id and is_message_processed(msg_id, group_id):
        log(f"消息 {msg_id} 已被处理，跳过", "DEBUG")
        return
    if group_id in group_blacklist:
        return
    if sender_qq in user_blacklist:
        return

    if text_part.startswith("AI "):
        user_question = text_part[3:].strip()
        if not user_question:
            send_group_message(ws, group_id, "请问你想问什么？例如：AI 如何开发插件")
            return
        def do_ai():
            with ai_semaphore:
                try:
                    log(f"[AI] 处理问题: {user_question}", "INFO")
                    reply = call_ai_api(user_question, sender_qq or group_id)
                    send_group_message(ws, group_id, reply)
                except Exception as e:
                    log(f"[AI] 线程异常: {e}", "ERROR")
                    send_group_message(ws, group_id, f"AI 处理异常：{str(e)}")
        threading.Thread(target=do_ai, daemon=True).start()
        return

    if sender_qq in admin_list:
        if text_part.startswith("禁用群"):
            parts = text_part.split()
            if len(parts) >= 2 and parts[1].isdigit():
                group_blacklist.add(parts[1])
                save_group_blacklist()
                send_group_message(ws, group_id, f"已禁用群 {parts[1]}")
            return
        elif text_part.startswith("启用群"):
            parts = text_part.split()
            if len(parts) >= 2 and parts[1].isdigit():
                group_blacklist.discard(parts[1])
                save_group_blacklist()
                send_group_message(ws, group_id, f"已启用群 {parts[1]}")
            return

    for cmd_name, func in list(plugins.items()):
        if text_part.startswith(cmd_name):
            if plugin_admin_only.get(cmd_name, False) and sender_qq not in admin_list:
                send_group_message(ws, group_id, "此命令仅限管理员使用")
                return
            log(f"触发插件: {cmd_name}")
            def send_msg(arg1, arg2=None):
                if arg2 is None:
                    if isinstance(arg1, dict):
                        send_raw(ws, arg1)
                    elif isinstance(arg1, bytes):
                        send_binary(ws, arg1)
                else:
                    send_group_message(ws, arg1, arg2)
            try:
                func(msg_data, send_msg)
            except Exception as e:
                err_msg = f"插件 {cmd_name} 执行出错: {e}"
                log(err_msg, "ERROR")
                send_group_message(ws, group_id, f"[错误] {err_msg}")
            return

def on_message(ws, message):
    try:
        data = json.loads(message)
        cmd = data.get("cmd")
        if cmd == "Response":
            resp_data = data.get("data")
            status = None
            if isinstance(resp_data, dict):
                status = resp_data.get("status")
            elif isinstance(resp_data, list) and resp_data:
                status = resp_data[0].get("status")
            if status is True:
                log("插件上线成功！")
                send_log(ws, "info", "插件已上线")
                send_group_message(ws, TARGET_GROUP, f"当前机器人号:{SELF_QQ}已连接服务器")
            elif status is False:
                log("插件上线失败，Token 错误", "ERROR")
                ws.close()
        elif cmd == "PushOicqMsg":
            handle_message(data.get("data", []), ws)
        elif cmd == "UserInfoGet":
            resp_data = data.get("data", {})
            skey = resp_data.get("skey")
            pskey = resp_data.get("pskey")
            if skey and pskey:
                key_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "key")
                os.makedirs(key_dir, exist_ok=True)
                with open(os.path.join(key_dir, "keys.txt"), "w", encoding="utf-8") as f:
                    f.write(f"skey={skey}\npskey={pskey}")
                log("已保存 skey/pskey")
    except Exception as e:
        log(f"处理消息出错: {e}", "ERROR")

def on_error(ws, error):
    log(f"WebSocket 错误: {error}", "ERROR")

def on_close(ws, close_status_code, close_msg):
    log("WebSocket 连接关闭")
    global current_ws
    with current_ws_lock:
        current_ws = None

def on_open(ws):
    global current_ws
    with current_ws_lock:
        current_ws = ws
    threading.Thread(target=sender_worker, args=(ws,), daemon=True).start()
    log("发送工作线程已启动")
    log("WebSocket 连接成功，发送上线包...")
    packet = {
        "seq": get_seq(),
        "cmd": "SyncOicq",
        "rsp": True,
        "data": {"pid": PLUGIN_ID, "name": PLUGIN_NAME, "token": TOKEN}
    }
    _enqueue_send(packet)

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = 'secluded_bot_secret'

def require_auth(f):
    def wrapper(*args, **kwargs):
        if WEB_PASSWORD:
            auth = request.cookies.get('bot_auth')
            if auth != WEB_PASSWORD:
                return render_template('login.html')
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@app.route('/')
@require_auth
def index():
    return render_template('dashboard.html',
                           target_group=TARGET_GROUP,
                           self_qq=SELF_QQ,
                           ws_url=WS_URL,
                           current_version=CURRENT_VERSION)

@app.route('/api/status')
@require_auth
def api_status():
    uptime = str(datetime.now() - bot_start_time).split('.')[0]
    return jsonify({
        'connected': current_ws is not None,
        'uptime': uptime,
        'plugins': list(plugin_enabled.keys()),
        'plugin_enabled': plugin_enabled,
        'plugin_admin_only': plugin_admin_only,
        'admin_list': list(admin_list),
        'user_blacklist': list(user_blacklist),
        'group_blacklist': list(group_blacklist),
        'log_lines': log_buffer[-50:],
        'current_version': CURRENT_VERSION
    })

@app.route('/api/enable_plugin', methods=['POST'])
@require_auth
def api_enable_plugin():
    data = request.get_json()
    name = data.get('name')
    enable = data.get('enable', True)
    if name in plugin_enabled:
        enable_plugin(name, enable)
        return jsonify({'success': True})
    return jsonify({'error': '插件不存在'}), 404

@app.route('/api/set_plugin_admin', methods=['POST'])
@require_auth
def api_set_plugin_admin():
    data = request.get_json()
    name = data.get('name')
    admin_only = data.get('admin_only', False)
    if name in plugin_admin_only:
        set_plugin_admin_only(name, admin_only)
        return jsonify({'success': True})
    return jsonify({'error': '插件不存在'}), 404

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
    group = str(request.get_json().get('group', ''))
    if not group.isdigit():
        return jsonify({'error': '群号必须为数字'}), 400
    group_blacklist.add(group)
    save_group_blacklist()
    return jsonify({'success': True})

@app.route('/api/remove_group_blacklist', methods=['POST'])
@require_auth
def api_remove_group_blacklist():
    group = str(request.get_json().get('group', ''))
    group_blacklist.discard(group)
    save_group_blacklist()
    return jsonify({'success': True})

@app.route('/api/send', methods=['POST'])
@require_auth
def api_send():
    data = request.get_json()
    group_id = data.get('group_id', TARGET_GROUP)
    text = data.get('text', '')
    if not text:
        return jsonify({'error': '文本不能为空'}), 400
    if current_ws is None:
        return jsonify({'error': '机器人未连接'}), 503
    send_group_message(current_ws, group_id, text)
    return jsonify({'success': True})

@app.route('/api/check_update', methods=['POST'])
@require_auth
def api_check_update():
    threading.Thread(target=check_and_update, args=(True,), daemon=True).start()
    return jsonify({'success': True, 'msg': '已开始检查更新'})

@app.route('/api/ai_chat', methods=['POST'])
@require_auth
def api_ai_chat():
    question = request.get_json().get('question', '').strip()
    if not question:
        return jsonify({'error': '问题不能为空'}), 400
    with ai_semaphore:
        log(f"[Web AI] 处理: {question}", "INFO")
        reply = call_ai_api(question, "8888888888")
    return jsonify({'reply': reply})

@app.route('/login', methods=['POST'])
def login():
    pwd = request.form.get('password')
    if pwd == WEB_PASSWORD:
        resp = jsonify({'success': True})
        resp.set_cookie('bot_auth', WEB_PASSWORD, max_age=86400)
        return resp
    return jsonify({'success': False, 'error': '密码错误'}), 401

@app.route('/external/send', methods=['GET', 'POST'])
def external_send():
    if request.method == 'GET':
        token = request.args.get('api_token')
        group_id = request.args.get('group_id')
        text = request.args.get('text')
    else:
        data = request.get_json()
        token = data.get('api_token') if data else None
        group_id = data.get('group_id') if data else None
        text = data.get('text') if data else None
    if token != API_TOKEN:
        return jsonify({'error': 'Invalid token'}), 401
    if not group_id or not text:
        return jsonify({'error': 'Missing group_id or text'}), 400
    if current_ws is None:
        return jsonify({'error': 'Bot not connected'}), 503
    send_group_message(current_ws, group_id, text)
    return jsonify({'success': True})

class PluginReloadHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.is_directory or not event.src_path.endswith(".py"):
            return
        log(f"检测到插件文件变化: {event.src_path}")
        time.sleep(0.5)
        load_plugins()

def start_web():
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False)

def main():
    threading.Thread(target=clean_old_locks, daemon=True).start()
    if AUTO_UPDATE:
        check_and_update()
    load_plugins()
    web_thread = threading.Thread(target=start_web, daemon=True)
    web_thread.start()
    log(f"Web 管理面板已启动，http://0.0.0.0:{WEB_PORT} 密码: {WEB_PASSWORD}")
    log(f"外部API: http://0.0.0.0:{WEB_PORT}/external/send Token: {API_TOKEN}")
    log(f"主程序版本: {CURRENT_VERSION}")

    observer = Observer()
    observer.schedule(PluginReloadHandler(), path=PLUGIN_DIR, recursive=False)
    observer.start()
    log(f"插件热加载监控已启动: {PLUGIN_DIR}")

    while True:
        log(f"正在连接 {WS_URL}")
        ws = WebSocketApp(WS_URL, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close)
        ws.run_forever(ping_interval=30, ping_timeout=10)
        log("连接断开，5秒后重连...")
        time.sleep(5)

if __name__ == "__main__":
    main()
