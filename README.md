# Secluded 插件开发完整教程

本教程适用于基于 Secluded 框架的多账号机器人主程序。插件采用 Python 编写，每个插件是独立的 `.py` 文件，放在对应机器人 QQ 的插件目录下。

---

## 一、快速开始

### 1.1 环境要求
- Python 3.9+
- 系统：Linux / Termux (Android) / macOS / Windows (WSL)
- 依赖：`pip install requests websocket-client watchdog flask`

### 1.2 部署流程
1. 将 `main.py`、`dashboard.html`、`login.html` 放置于同一目录。
2. 运行 `python main.py` 启动主程序。首次运行会在同目录生成 `config.json` 配置文件。
3. 浏览器访问 `http://IP:端口`（默认 5000），使用默认密码 `admin` 登录。
4. 在 **账号管理** 页面添加机器人账号（填写 QQ、WS_URL、TOKEN 等）。
5. 添加后主程序自动为该 QQ 创建插件目录 `BOT/<QQ>/`，并启动 WebSocket 连接。

### 1.3 插件目录说明（新）
多账号架构下，每个机器人拥有独立的插件文件夹，结构如下：

```

BOT/
├── 111111/          # 机器人 QQ 111111 的插件
│   ├── 测试.py
│   └── 菜单.py
├── 222222/          # 机器人 QQ 222222 的插件
│   └── 音乐登录.py
...

```

**触发规则**  
- 文件名（不含 `.py`）即为触发词。  
- **严格匹配**：消息内容必须等于触发词，或触发词后跟一个空格才被识别。  
  例：`测试` 触发，`测试参数` 触发，但 `测试啊` 不触发。

**热加载**  
修改插件文件后自动重新加载，无需重启，且仅影响对应账号的插件。

---

## 二、插件开发基础

### 2.1 最小插件
```python
# 文件名：测试.py  放在 BOT/你的QQ/ 下
def run(data, send_msg):
    group_id = None
    for item in data:
        if isinstance(item, dict) and "GroupId" in item:
            group_id = item["GroupId"]
            break
    if group_id:
        send_msg(group_id, "你好，我是机器人")
```

2.2 data 参数详解

data 是主程序传入的消息数据列表，每个元素是字典。常用字段：

字段 类型 说明
GroupId str 群号
Uin str 发送者 QQ
UinName str 发送者昵称
Text str 文本内容（可能跨多个字典）
AtUin str 被 @ 的 QQ
AtName str 被 @ 的昵称
Reply str 引用的消息 ID
MsgId str 消息 ID
Url str 图片链接（如果消息含图）
Account str 机器人 QQ

2.3 send_msg 回调函数

用法一：发送文本
send_msg(群号, "文本")

用法二：发送原始 JSON 包（图片、卡片等）
send_msg(dict)

用法三：发送二进制数据（Protobuf）
send_msg(bytes)

---

三、消息发送进阶

3.1 发送图片

```python
img_packet = {
    "cmd": "SendOicqMsg",
    "rsp": True,
    "data": [
        {"Account": "机器人QQ", "Group": "Group", "GroupId": group_id},
        {"Img": "https://example.com/image.jpg"}  # 或本地路径
    ]
}
send_msg(img_packet)
```

3.2 发送卡片（音乐/分享等）

```python
card = {
    "cmd": "SendOicqMsg",
    "rsp": True,
    "data": [
        {
            "Account": "机器人QQ",
            "GroupId": group_id,
            "Title": "歌曲名",
            "Info": "歌手",
            "Url": "https://...",
            "JSON_KG": "JSON_KG",   # 酷狗；其他可选 JSON_QQ, JSON_BL, JSON_MG 等
            "CustomJson": "CustomJson"
        },
        {"Img": "https://封面图.jpg"}
    ]
}
send_msg(card)
```

3.3 发送语音、视频等

见官方协议文档，结构类似，替换字段即可。

---

四、消息解析技巧

4.1 提取群号和发送者

```python
group_id = sender_qq = None
for item in data:
    if isinstance(item, dict):
        if "GroupId" in item: group_id = item["GroupId"]
        if "Uin" in item: sender_qq = str(item["Uin"])
```

4.2 提取完整文本

```python
text = ""
for item in data:
    if isinstance(item, dict) and "Text" in item:
        text += item["Text"]
```

4.3 获取 @ 用户

```python
at_uin = None
for item in data:
    if isinstance(item, dict) and "AtUin" in item:
        at_uin = item["AtUin"]
        break
```

4.4 获取引用消息

```python
reply_id = None
for item in data:
    if isinstance(item, dict) and "Reply" in item:
        reply_id = item["Reply"]
        break
```

---

五、权限控制

5.1 管理员判断

主程序维护一个全局管理员列表，插件可通过参数判断：

```python
# 假设主程序已将 is_admin 注入（目前多账号版需通过 setup 传入）
# 若未注入，可自行维护管理员文件，或使用 plugin_admin_only 配置。
```

更推荐：在 Web 面板的插件管理中，勾选“仅管理员可用”，无需修改代码。

5.2 黑白名单

系统已在消息入口处检查全局用户/群黑名单，插件无需额外处理。

---

六、插件进阶

6.1 数据持久化

JSON 文件存储

```python
import json, os

DATA_FILE = "my_data.json"

def load():
    if not os.path.exists(DATA_FILE): return {}
    with open(DATA_FILE, "r") as f: return json.load(f)

def save(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, ensure_ascii=False, indent=2)
```

SQLite 存储

```python
import sqlite3

def init_db():
    conn = sqlite3.connect("bot.db")
    conn.execute("CREATE TABLE IF NOT EXISTS users (qq TEXT PRIMARY KEY, score INTEGER)")
    conn.commit()
    conn.close()

init_db()
```

6.2 插件间调用

插件 A 导出方法：

```python
# 积分.py
_points = {}

def setup(ctx):
    ctx["register_exports"]({
        "add": add_points,
        "get": get_points
    })

def add_points(user_id, delta):
    _points[user_id] = _points.get(user_id, 0) + delta
    return _points[user_id]

def get_points(user_id):
    return _points.get(user_id, 0)
```

插件 B 调用（需通过 setup 获取 call_plugin）：

```python
# 签到.py
def setup(ctx):
    global _call_plugin
    _call_plugin = ctx["call_plugin"]

def run(data, send_msg):
    # ... 获取 sender_qq, group_id ...
    new = _call_plugin("积分", "add", sender_qq, 10)
    send_msg(group_id, f"签到成功，积分：{new}")
```

6.3 后台线程（耗时任务）

```python
import threading

def long_task(group_id, send_msg):
    import time; time.sleep(5)
    send_msg(group_id, "后台任务完成")

def run(data, send_msg):
    t = threading.Thread(target=long_task, args=(group_id, send_msg))
    t.start()
    send_msg(group_id, "任务已提交...")
```

---

七、调试与错误处理

7.1 日志与错误捕获

```python
import traceback

def run(data, send_msg):
    try:
        # 你的逻辑
        pass
    except Exception as e:
        print("异常详情:", traceback.format_exc())
        send_msg(group_id, f"出错啦：{e}")
```

7.2 超时说明

主程序默认插件执行超时 6 秒，长时间任务请放入后台线程，避免阻塞。

---

八、常见问题

问题 可能原因 解决方案
插件无反应 文件名与触发词不一致；插件被禁用；未放对机器人目录 检查 BOT/<QQ>/ 下文件名，Web 面板查看启用状态
消息发送失败 WebSocket 未连接；图片链接不可达 先发送纯文本测试，确认机器人在线
图片不显示 防盗链或路径错误 将图片下载到本地再发送，或使用公网可访问链接
多账号互相干扰 两个机器人收到同一指令都回复（刷屏） 插件自行判断发送者或群号，或利用管理员指令规避
重启后插件丢失 配置文件未同步 所有配置通过 Web 面板操作即可持久化，无需手动编辑文件

---

九、完整示例

9.1 签到插件

```python
# 签到.py 放在 BOT/<QQ>/ 下
import json, os, time

DATA_FILE = "sign_data.json"

def load():
    if not os.path.exists(DATA_FILE): return {}
    with open(DATA_FILE) as f: return json.load(f)

def save(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, ensure_ascii=False)

def run(data, send_msg):
    group_id = sender = None
    for item in data:
        if isinstance(item, dict):
            if "GroupId" in item: group_id = item["GroupId"]
            if "Uin" in item: sender = str(item["Uin"])
    if not group_id or not sender: return

    today = time.strftime("%Y-%m-%d")
    signs = load()
    if signs.get(sender) == today:
        send_msg(group_id, "今天已签到")
        return
    signs[sender] = today
    save(signs)
    send_msg(group_id, f"{sender} 签到成功")
```

9.2 天气查询

```python
# 天气.py
import requests

def run(data, send_msg):
    group_id = text = ""
    for item in data:
        if isinstance(item, dict):
            if "GroupId" in item: group_id = item["GroupId"]
            if "Text" in item: text += item["Text"]
    if not text.startswith("天气"): return
    city = text[2:].strip()
    if not city:
        send_msg(group_id, "用法：天气 北京")
        return
    try:
        r = requests.get(f"https://wttr.in/{city}?format=%C+%t", timeout=10)
        send_msg(group_id, f"{city}天气：{r.text.strip()}")
    except Exception as e:
        send_msg(group_id, f"查询失败：{e}")
```

---

更新说明（v2.0）

· 插件目录变更为 BOT/<QQ>/，适配多账号架构。
· 触发规则改为严格匹配（完全相等或后跟空格）。
· 新增账号管理方式：通过 Web 面板添加/删除/重启机器人，无需手动编辑配置文件。
· 各账号插件独立，热加载仅影响自身，避免冲突。

如有任何问题，请参考主程序文档或联系开发者。3870149287
