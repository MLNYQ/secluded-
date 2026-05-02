# secluded-
这是适配sec软件的插件，有完整的的教程和丰富的插件市场



# Secluded 机器人完整开发与部署指南
---

## 目录

1. [概述](#一概述)
2. [部署准备](#二部署准备)
3. [主程序配置与运行](#三主程序配置与运行)
4. [Web 管理面板](#四web-管理面板)
5. [插件开发完整教程](#五插件开发完整教程)
6. [高级功能](#六高级功能)
7. [常见问题排查](#七常见问题排查)
8. [附录：完整示例](#八附录完整示例)

---

## 一、概述

本教程涵盖 Secluded 框架机器人的完整生命周期：**部署 → 配置 → 开发 → 维护**。

### 核心特性

- **插件热加载**：修改插件文件后自动生效，无需重启主程序
- **多消息类型**：支持文本、图片、卡片（QQ音乐/酷狗/咪咕/B站等）、二进制包发送
- **Web 管理面板**：可视化权限控制、实时监控、日志查看
- **高级功能**：定时任务、插件间调用、数据持久化
- **自动更新**：可选的自动更新机制

### 适用环境

- Termux (Android)
- Linux 服务器
- Windows (Python 环境)

---

## 二、部署准备

### 2.1 确认 Secluded 服务端信息

在开始部署前，你需要从 Secluded 控制台获取以下信息：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| **WebSocket 地址** | Secluded 服务端的 WebSocket 地址（注意是 `ws://` 不是 `http://`） | `ws://123.456.789.0:8544` |
| **协议令牌 (Token)** | 在 Secluded 控制台的"协议令牌"中获取（**不是**前端令牌 `admin996`） | `admin12` |
| **机器人 QQ 号** | 已经登录到 Secluded 的 QQ 号 | `3955283804` |

### 2.2 本地环境安装

#### Termux (Android)

```bash
pkg update && pkg upgrade
pkg install python
```

#### Linux

```bash
sudo apt update
sudo apt install python3 python3-pip -y
```

### 2.3 安装 Python 依赖

```bash
pip install websocket-client watchdog requests beautifulsoup4
```

**依赖说明：**

| 依赖包 | 用途 |
|--------|------|
| `websocket-client` | WebSocket 连接，与 Secluded 服务端通信 |
| `watchdog` | 文件系统监控，实现插件热加载 |
| `requests` | HTTP 请求，用于调用外部 API（如天气、点歌） |
| `beautifulsoup4` | HTML 解析，用于部分需要爬取网页的插件 |

---

## 三、主程序配置与运行

### 3.1 下载主程序

将 `main.py` 放在工作目录（例如 `~/bot/`）。

### 3.2 目录结构规划

```
~/bot/
├── main.py          # 主程序（配置 + 核心逻辑）
├── start.sh         # 自动重启脚本（推荐用于生产环境）
├── bot.db           # SQLite 数据库（插件自动生成）
├── sign_data.json   # JSON 数据文件（插件自动生成）
└── BOT/             # 插件目录（PLUGIN_DIR 配置）
    ├── 签到.py
    ├── 天气.py
    ├── 菜单.py
    └── ...
```

### 3.3 配置 config

编辑主程序开头的配置项：

```python
# ==================== 核心连接配置 ====================
WS_URL = "ws://123.456.789.0:8544"    # WebSocket 地址（Secluded 服务端）
TOKEN = "admin12"                      # 协议令牌（控制台获取）
SELF_QQ = "3955283804"                 # 机器人自己的 QQ 号

# ==================== 插件标识配置 ====================
PLUGIN_ID = "my.test.bot"              # 插件唯一标识，可随意填写
PLUGIN_NAME = "mybot"                  # 插件名称，可随意
TARGET_GROUP = "123456789"             # 机器人上线后发送通知的群号（可选）
PLUGIN_DIR = "BOT"                     # 插件文件夹路径（默认为 BOT）

# ==================== Web 面板配置 ====================
WEB_PORT = 5000                        # Web 管理面板端口
WEB_PASSWORD = "admin123"              # 面板登录密码

# ==================== 其他功能配置 ====================
AUTO_UPDATE = False                    # 是否启用自动更新（True/False）
```

### 3.4 创建插件目录

```bash
mkdir BOT
```

### 3.5 运行机器人

#### 方式一：直接运行（适合测试）

```bash
python main.py
```

#### 方式二：使用自动重启脚本（推荐用于生产环境）

创建 `start.sh`：

```bash
cat > start.sh << 'EOF'
#!/bin/bash
while true; do
    python main.py
    echo "程序退出，3秒后重启..."
    sleep 3
done
EOF
chmod +x start.sh
./start.sh
```

> **提示：** 这样即使机器人崩溃或执行重启指令，也会自动恢复运行。

---

## 四、Web 管理面板

### 4.1 访问方式

- **地址**：`http://你的IP:WEB_PORT`
- **默认示例**：`http://127.0.0.1:5000`
- **密码**：`WEB_PASSWORD` 配置的值（默认 `admin123`）

### 4.2 功能列表

| 功能模块 | 说明 | 操作 |
|----------|------|------|
| **状态监控** | 查看机器人运行状态、连接状态、运行时间 | 只读查看 |
| **插件管理** | 查看所有插件，启用/禁用插件，设置"仅管理员可用" | 开关控制 |
| **权限管理** | 管理管理员 QQ 列表、用户黑名单、群黑名单 | 增删改查 |
| **消息测试** | 手动发送测试消息到指定群 | 发送消息 |
| **实时日志** | 查看主程序控制台的实时输出 | 只读查看 |
| **更新检查** | 手动触发更新检查（如果启用了自动更新） | 手动触发 |

### 4.3 权限控制说明

- **管理员列表**：拥有所有插件的使用权限（包括标记为"仅管理员"的插件）
- **用户黑名单**：被拉黑的用户无法触发任何插件
- **群黑名单**：机器人在被拉黑的群中不响应任何消息
- **插件级权限**：每个插件可在面板中单独设置"仅管理员可用"

> **注意：** 插件的"仅管理员"开关在 Web 面板中设置，无需在插件代码中硬编码管理员 QQ 列表。

---

## 五、插件开发完整教程

### 5.1 插件基本结构

每个插件是一个独立的 `.py` 文件，放在 `PLUGIN_DIR` 目录下（默认为 `BOT/`）。

**核心规则：**

1. **文件名 = 触发词**：例如 `测试.py`，用户在群中发送包含"测试"的消息即可触发
2. **必须包含 `run` 函数**：接收两个参数 `data` 和 `send_msg`
3. **热加载支持**：修改插件文件后，主程序自动重新加载，无需重启

**最小插件示例：**

```python
# 文件名：示例.py
def run(data, send_msg):
    # 插件逻辑
    pass
```

### 5.2 参数详解

#### data 参数（消息数据）

`data` 是 Secluded 推送的消息数据，类型为 `list[dict]`（列表，每个元素是字典）。

**常用字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `GroupId` | `str` | 群号 |
| `Uin` | `str` | 发送者的 QQ 号 |
| `UinName` | `str` | 发送者昵称 |
| `Text` | `str` | 文本内容（可能有多个片段） |
| `MsgId` | `str` | 消息 ID |
| `Reply` | `str` | 被回复的消息 ID（仅当引用回复时存在） |
| `AtUin` | `str` | 被 @ 的 QQ 号（出现在 @ 片段中） |
| `AtName` | `str` | 被 @ 的昵称 |
| `Url` | `str` | 图片链接（如果消息包含图片） |
| `Group` | `str` | 固定为 `"Group"`，表示群聊 |
| `Account` | `str` | 机器人账号 |

**消息数据示例（简化）：**

```json
[
  {"GroupId": "123456", "Uin": "987654", "UinName": "张三"},
  {"Text": "@李四 你好"},
  {"AtUin": "111111", "AtName": "李四"},
  {"Text": " 测试插件"}
]
```

#### send_msg 参数（发送消息回调）

`send_msg` 是一个回调函数，用于发送消息，有三种用法：

1. **发送文本**：`send_msg(群号, 文本内容)`
2. **发送原始 JSON 包**（卡片、图片等）：`send_msg(字典对象)`
3. **发送二进制包**：`send_msg(字节数据)`

### 5.3 消息数据解析实战

#### 5.3.1 获取群号和发送者 QQ

```python
def run(data, send_msg):
    group_id = None
    sender_qq = None

    for item in data:
        if isinstance(item, dict):
            if "GroupId" in item:
                group_id = item["GroupId"]
            if "Uin" in item:
                sender_qq = str(item["Uin"])

    if not group_id:
        return  # 不是群聊消息，忽略

    # 继续处理...
```

#### 5.3.2 获取用户输入的文本内容

```python
user_text = ""
for item in data:
    if isinstance(item, dict) and "Text" in item:
        user_text += item["Text"]   # 可能有多个文本片段，拼接起来

# 去除触发词（如"天气 北京" → "北京"）
if user_text.startswith("天气"):
    city = user_text[2:].strip()
```

#### 5.3.3 获取 @ 的用户 QQ

```python
at_uin = None
for item in data:
    if isinstance(item, dict) and "AtUin" in item:
        at_uin = str(item["AtUin"])
        break  # 通常只 @ 一个人，取第一个即可
```

#### 5.3.4 获取引用消息的 ID（回复）

```python
reply_msg_id = None
for item in data:
    if isinstance(item, dict) and "Reply" in item:
        reply_msg_id = item["Reply"]
        break
```

### 5.4 发送消息详解

#### 5.4.1 发送纯文本

```python
def run(data, send_msg):
    group_id = "123456"  # 实际应从 data 中获取
    send_msg(group_id, "你好，我是机器人 🤖")
```

#### 5.4.2 发送图片

```python
img_packet = {
    "cmd": "SendOicqMsg",
    "rsp": True,
    "data": [
        {"Account": "机器人QQ号", "Group": "Group", "GroupId": group_id},
        {"Img": "https://example.com/image.jpg"}
    ]
}
send_msg(img_packet)
```

**要求：**

- 图片链接必须是 **HTTPS** 公网可访问链接
- 支持常见格式：jpg、png、gif

#### 5.4.3 发送卡片（多种样式）

Secluded 支持多种卡片样式，通过不同字段指定：

| 卡片类型 | 字段 | 用途 |
|----------|------|------|
| QQ 音乐 | `JSON_QQ` | QQ 音乐分享样式 |
| 酷狗音乐 | `JSON_KG` | 酷狗音乐样式 |
| 咪咕音乐 | `JSON_MG` | 咪咕音乐样式 |
| QQ 空间 | `JSON_QQKJ` | QQ 空间分享样式 |
| Bilibili | `JSON_BL` | B站分享样式 |

**通用卡片结构：**

```python
card_packet = {
    "cmd": "SendOicqMsg",
    "rsp": True,
    "data": [
        {
            "Account": "机器人QQ号",
            "GroupId": group_id,
            "Title": "卡片标题",
            "Info": "卡片描述",
            "Url": "https://example.com",
            "JSON_QQ": "JSON_QQ",      # 指定卡片样式
            "CustomJson": "CustomJson"
        },
        {
            "Img": "https://example.com/cover.jpg"
        }
    ]
}
send_msg(card_packet)
```

#### 5.4.4 发送原始 JSON 包（自定义命令）

```python
custom_packet = {
    "cmd": "CustomCommand",
    "rsp": False,
    "data": {"key": "value"}
}
send_msg(custom_packet)
```

---

## 六、高级功能

### 6.1 权限控制（代码层面）

虽然 Web 面板可以设置"仅管理员可用"，但有时需要在代码中进行更细粒度的权限控制。

#### 6.1.1 使用 setup 注入上下文

如果插件需要调用主程序的功能（如管理员检查、插件间调用），需要实现 `setup` 函数：

```python
_admin_check = None  # 全局变量存储管理员检查函数

def setup(ctx):
    """初始化时调用，ctx 包含主程序提供的功能"""
    global _admin_check
    _admin_check = ctx["is_admin"]  # 获取管理员检查函数

def run(data, send_msg):
    # 解析发送者 QQ...
    sender_qq = None
    group_id = None
    for item in data:
        if isinstance(item, dict):
            if "Uin" in item:
                sender_qq = str(item["Uin"])
            if "GroupId" in item:
                group_id = item["GroupId"]

    if not group_id or not sender_qq:
        return

    # 检查权限
    if not _admin_check(sender_qq):
        send_msg(group_id, "❌ 权限不足，仅管理员可用")
        return

    # 管理员专属逻辑...
    send_msg(group_id, "✅ 管理员命令执行成功")
```

#### 6.1.2 硬编码管理员列表（不推荐）

简单场景下可以直接在代码中定义：

```python
ADMIN_LIST = ["123456", "789012"]  # 管理员 QQ 列表

def run(data, send_msg):
    sender_qq = None
    # ... 解析 sender_qq ...

    if sender_qq not in ADMIN_LIST:
        send_msg(group_id, "权限不足")
        return
```

> **不推荐原因**：需要修改代码才能调整权限，不如 Web 面板灵活。

### 6.2 插件间调用

通过 `setup` 注入的 `call_plugin` 方法，可以实现插件间的功能调用。

#### 6.2.1 暴露公共方法（被调用方）

```python
# 积分.py - 提供积分管理功能
_points = {}  # 内存存储（实际应用建议用数据库）

def setup(ctx):
    """注册对外接口"""
    ctx["register_exports"]({
        "add": add_points,    # 添加积分
        "get": get_points,    # 查询积分
        "reduce": reduce_points  # 扣除积分
    })

def add_points(user_id, delta):
    """给用户添加积分"""
    _points[user_id] = _points.get(user_id, 0) + delta
    return _points[user_id]

def get_points(user_id):
    """查询用户积分"""
    return _points.get(user_id, 0)

def reduce_points(user_id, delta):
    """扣除积分（不会扣到负数）"""
    current = _points.get(user_id, 0)
    if current < delta:
        return False, "积分不足"
    _points[user_id] = current - delta
    return True, _points[user_id]

def run(data, send_msg):
    # 普通指令处理（如查询积分）
    pass
```

#### 6.2.2 调用其他插件（调用方）

```python
# 签到.py - 调用积分插件
_call_plugin = None

def setup(ctx):
    global _call_plugin
    _call_plugin = ctx["call_plugin"]

def run(data, send_msg):
    # 解析群号和发送者...
    group_id = None
    sender_qq = None
    for item in data:
        if isinstance(item, dict):
            if "GroupId" in item:
                group_id = item["GroupId"]
            if "Uin" in item:
                sender_qq = str(item["Uin"])

    if not group_id or not sender_qq:
        return

    try:
        # 调用"积分"插件的"add"方法，给 sender_qq 增加 10 积分
        new_points = _call_plugin("积分", "add", sender_qq, 10)
        send_msg(group_id, f"✅ 签到成功，当前积分：{new_points}")
    except Exception as e:
        send_msg(group_id, f"❌ 签到失败：{e}")
```

### 6.3 定时任务

如果主程序启用了调度器（`ENABLE_SCHEDULER=true`），插件可以注册定时任务。

```python
def setup(ctx):
    """注册定时任务"""
    # 每 60 秒执行一次
    ctx["register_job"](
        auto_remind,           # 任务函数
        "interval",            # 触发器类型
        seconds=60,            # 间隔 60 秒
        args=[ctx.get("target_group")]  # 传递给任务的参数
    )

def auto_remind(group_id):
    """
    定时任务函数
    注意：定时任务中没有 data 参数，也没有直接的 send_msg
    """
    if not group_id:
        return

    # 方案 1：只做数据操作，不发送消息
    print(f"[{time.strftime('%H:%M:%S')}] 执行定时任务，目标群：{group_id}")

    # 方案 2：通过主程序提供的全局方法发送（需要主程序支持）
    # 实际使用时，可以通过主程序提供的全局 current_ws 和 send_group_message 函数
    # 或通过写入队列，由主程序统一发送

import time

def run(data, send_msg):
    # 普通消息处理
    pass
```

> **注意：** 定时任务中无法直接使用 `send_msg`，因为缺少 WebSocket 连接对象。建议定时任务只做数据操作，或通过主程序提供的其他 API 发送。

### 6.4 数据存储

#### 6.4.1 JSON 文件存储（适合简单数据）

```python
import json
import os

DATA_FILE = "sign_data.json"

def load_data():
    """加载数据"""
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    """保存数据"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def run(data, send_msg):
    # 示例：记录每个用户的调用次数
    sender = None
    group_id = None

    for item in data:
        if isinstance(item, dict):
            if "Uin" in item:
                sender = str(item["Uin"])
            if "GroupId" in item:
                group_id = item["GroupId"]

    if not sender or not group_id:
        return

    d = load_data()
    d[sender] = d.get(sender, 0) + 1
    save_data(d)

    send_msg(group_id, f"这是您第 {d[sender]} 次使用本插件")
```

#### 6.4.2 SQLite 存储（适合复杂数据）

```python
import sqlite3

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS counter (
            user TEXT PRIMARY KEY, 
            count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def add_count(user):
    """增加计数"""
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO counter (user, count) 
        VALUES (?, COALESCE((SELECT count FROM counter WHERE user=?), 0) + 1)
    """, (user, user))
    conn.commit()
    conn.close()

def get_count(user):
    """获取计数"""
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT count FROM counter WHERE user=?", (user,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

# 在插件启动时初始化数据库
init_db()

def run(data, send_msg):
    # 使用数据库...
    pass
```

### 6.5 调试与错误处理

#### 6.5.1 调试技巧

```python
import traceback

def run(data, send_msg):
    # 使用 print 输出调试信息，会显示在主程序控制台
    print("[调试] 收到消息：", data)

    try:
        # 可能出错的代码
        result = risky_operation()
        print("[调试] 操作成功：", result)

    except Exception as e:
        # 发送错误消息到群中，便于用户反馈
        error_msg = f"❌ 执行出错：{str(e)}"
        send_msg(group_id, error_msg)

        # 在控制台打印详细错误堆栈
        print("[错误详情]")
        print(traceback.format_exc())
```

#### 6.5.2 超时保护

主程序有插件超时保护（默认 6 秒），长时间运行的任务应该：

1. **使用异步处理**（如果主程序支持）
2. **分割任务**：先返回"处理中"，后台继续执行
3. **优化算法**：避免阻塞操作

```python
import threading

def long_task(group_id, send_msg):
    """耗时任务在后台执行"""
    import time
    time.sleep(10)  # 模拟耗时操作
    send_msg(group_id, "✅ 长时间任务完成")

def run(data, send_msg):
    # 启动后台线程
    thread = threading.Thread(target=long_task, args=(group_id, send_msg))
    thread.start()

    # 立即返回，避免超时
    send_msg(group_id, "⏳ 任务已提交，请稍候...")
```

---

## 七、常见问题排查

### 7.1 连接问题

#### 连接失败：Connection refused

- [ ] 检查 `WS_URL` 中的 IP 和端口是否正确
- [ ] 确认 Secluded 服务端已启动
- [ ] 检查防火墙/云安全组是否放行了该端口
- [ ] 尝试用 `curl http://IP:端口` 测试连通性

### 7.2 插件问题

#### 插件无反应

- [ ] 确认插件文件名与用户消息中的关键词一致（例如文件名"测试.py"，消息需包含"测试"）
- [ ] 查看控制台是否有 `[→] 触发插件: xxx` 日志。如果没有，说明匹配失败
- [ ] 确认插件中已正确获取 `group_id`
- [ ] 检查插件是否有语法错误（控制台会显示 Python 错误）

#### 插件导入错误（ModuleNotFoundError）

- [ ] 在 Termux 中安装缺失的库：`pip install 库名`
- [ ] 检查 Python 环境是否正确

### 7.3 消息发送问题

#### 发送图片/卡片不显示

- [ ] 图片链接必须是公网可访问的 HTTPS 链接
- [ ] 卡片样式可能被 QQ 屏蔽，尝试换用 `JSON_QQ`、`JSON_KG` 等不同样式
- [ ] 先用文本消息测试，确认网络通畅

#### 发送消息不显示

- [ ] 检查 `send_msg` 参数是否正确（先群号后文本）
- [ ] 确认机器人 QQ 在线且服务端正常
- [ ] 检查是否被群禁言或账号被风控

### 7.4 稳定性问题

#### 机器人频繁掉线

- [ ] 检查主程序的心跳设置（`ping_interval=30` 已内置）
- [ ] 确保服务器与 Secluded 服务端之间网络稳定
- [ ] 使用 `start.sh` 脚本实现自动重连

#### 内存占用过高

- [ ] 检查是否有插件内存泄漏（如无限增长的列表）
- [ ] 定期重启（可以设置每天自动重启）
- [ ] 使用 SQLite 代替大 JSON 文件

---

## 八、附录：完整示例

### 示例 1：签到插件（JSON 存储）

```python
# 签到.py
import json
import os
import time

SIGN_FILE = "sign_data.json"

def load_sign():
    """加载签到数据"""
    if not os.path.exists(SIGN_FILE):
        return {}
    with open(SIGN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_sign(data):
    """保存签到数据"""
    with open(SIGN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def run(data, send_msg):
    group_id = None
    sender_qq = None

    # 解析消息数据
    for item in data:
        if isinstance(item, dict):
            if "GroupId" in item:
                group_id = item["GroupId"]
            if "Uin" in item:
                sender_qq = str(item["Uin"])

    if not group_id or not sender_qq:
        return

    today = time.strftime("%Y-%m-%d")
    sign_data = load_sign()

    # 检查今天是否已签到
    if sign_data.get(sender_qq) == today:
        send_msg(group_id, "⚠️ 你今天已经签过到了，明天再来吧！")
        return

    # 记录签到
    sign_data[sender_qq] = today
    save_sign(sign_data)

    send_msg(group_id, f"✅ 签到成功！{sender_qq}\n📅 签到时间：{today}")
```

### 示例 2：天气查询插件（API 调用）

```python
# 天气.py
import requests

def run(data, send_msg):
    group_id = None
    user_text = ""

    # 解析数据
    for item in data:
        if isinstance(item, dict):
            if "GroupId" in item:
                group_id = item["GroupId"]
            if "Text" in item:
                user_text += item["Text"]

    if not group_id:
        return

    # 检查触发词
    if not user_text.startswith("天气"):
        return

    # 提取城市名
    city = user_text[2:].strip()
    if not city:
        send_msg(group_id, "❓ 请提供城市名，例如：天气 北京")
        return

    try:
        # 使用 wttr.in 免费天气 API
        url = f"https://wttr.in/{city}?format=%C+%t&lang=zh"
        resp = requests.get(url, timeout=10)
        weather = resp.text.strip()

        if "Unknown location" in weather:
            send_msg(group_id, f"😕 未找到城市：{city}")
        else:
            send_msg(group_id, f"🌤️ {city}天气：{weather}")

    except Exception as e:
        send_msg(group_id, f"❌ 查询失败：{e}")
```

### 示例 3：发送酷狗音乐卡片

```python
# 音乐.py

def run(data, send_msg):
    group_id = None

    # 获取群号
    for item in data:
        if isinstance(item, dict) and "GroupId" in item:
            group_id = item["GroupId"]
            break

    if not group_id:
        return

    # 构建酷狗音乐卡片
    card = {
        "cmd": "SendOicqMsg",
        "rsp": True,
        "data": [
            {
                "Account": "3955283804",  # 你的机器人QQ
                "GroupId": group_id,
                "Title": "十年",
                "Info": "陈奕迅 - 黑白灰",
                "Url": "https://www.kugou.com/song/#hash=8D8C8A0E1E1E1E1E",
                "JSON_KG": "JSON_KG",  # 酷狗样式
                "CustomJson": "CustomJson"
            },
            {
                "Img": "https://y.gtimg.cn/music/photo_new/T002R300x300M000001CYCzA3aXcQG.jpg"
            }
        ]
    }

    send_msg(card)
```

### 示例 4：菜单插件（自动列出所有插件）

```python
# 菜单.py
import os

def run(data, send_msg):
    group_id = None

    for item in data:
        if isinstance(item, dict) and "GroupId" in item:
            group_id = item["GroupId"]
            break

    if not group_id:
        return

    # 获取插件目录
    plugin_dir = os.path.dirname(__file__)

    # 列出所有 .py 文件（排除 __init__.py 和私有文件）
    plugins = []
    for f in os.listdir(plugin_dir):
        if f.endswith(".py") and not f.startswith("_") and f != "菜单.py":
            plugins.append(f[:-3])  # 去掉 .py 后缀

    if plugins:
        menu_text = "📋 机器人指令菜单\n" + "═" * 20 + "\n"
        for i, plugin in enumerate(sorted(plugins), 1):
            menu_text += f"{i}. {plugin}\n"
        menu_text += "═" * 20 + "\n💡 发送对应指令即可使用"
        send_msg(group_id, menu_text)
    else:
        send_msg(group_id, "📭 暂无可用插件")
```

### 示例 5：点歌插件（酷我音乐 + 卡片）

```python
# 点歌.py
import requests

def run(data, send_msg):
    group_id = None
    user_text = ""

    # 解析消息
    for item in data:
        if isinstance(item, dict):
            if "GroupId" in item:
                group_id = item["GroupId"]
            if "Text" in item:
                user_text = item["Text"]

    if not group_id:
        return

    # 检查触发词
    if not user_text.startswith("点歌"):
        return

    keyword = user_text[2:].strip()
    if not keyword:
        send_msg(group_id, "🎵 请提供歌曲名，例如：点歌 晴天")
        return

    try:
        # 调用酷我音乐 API
        api_url = "https://lengy.top/API/kwmusic.php"
        params = {"msg": keyword, "num": 1}

        resp = requests.get(api_url, params=params, timeout=10)

        if resp.status_code != 200:
            send_msg(group_id, "❌ 音乐服务暂时不可用")
            return

        result = resp.json()

        if result.get("code") == 0 and result.get("data"):
            song = result["data"][0]
            name = song.get("song", "未知")
            singer = song.get("singer", "未知")
            song_id = song.get("id")
            pic = song.get("pic", "")

            if song_id:
                # 发送卡片消息
                card = {
                    "cmd": "SendOicqMsg",
                    "rsp": True,
                    "data": [
                        {
                            "Account": "3955283804",  # 替换为你的机器人QQ
                            "GroupId": group_id,
                            "Title": name,
                            "Info": f"歌手：{singer}",
                            "Url": f"https://kuwo.cn/play_detail/{song_id}",
                            "JSON_KG": "JSON_KG",
                            "CustomJson": "CustomJson"
                        }
                    ]
                }

                # 如果有封面图，添加图片
                if pic:
                    card["data"].append({"Img": pic})

                send_msg(card)
            else:
                # 没有 ID，发送文本
                send_msg(group_id, f"🎵 {name} - {singer}")
        else:
            send_msg(group_id, f"😕 未找到歌曲：{keyword}")

    except requests.Timeout:
        send_msg(group_id, "⏱️ 请求超时，请稍后重试")
    except Exception as e:
        send_msg(group_id, f"❌ 错误：{str(e)}")
```

### 示例 6：积分系统（插件间调用 + SQLite）

```python
# 积分.py - 提供积分管理功能，供其他插件调用
import sqlite3
import os

DB_FILE = "points.db"

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS points (
            user_id TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# 初始化数据库
init_db()

def get_conn():
    return sqlite3.connect(DB_FILE)

# ===== 对外接口 =====

def add_points(user_id, amount):
    """增加积分"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO points (user_id, balance, total_earned) 
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            balance = balance + ?,
            total_earned = total_earned + ?
    """, (user_id, amount, amount, amount, amount))
    conn.commit()

    c.execute("SELECT balance FROM points WHERE user_id=?", (user_id,))
    result = c.fetchone()[0]
    conn.close()
    return result

def get_points(user_id):
    """查询积分"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM points WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def reduce_points(user_id, amount):
    """扣除积分，返回 (success, result)"""
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT balance FROM points WHERE user_id=?", (user_id,))
    result = c.fetchone()
    current = result[0] if result else 0

    if current < amount:
        conn.close()
        return False, "积分不足"

    c.execute("""
        UPDATE points 
        SET balance = balance - ?, total_spent = total_spent + ?
        WHERE user_id = ?
    """, (amount, amount, user_id))
    conn.commit()

    new_balance = current - amount
    conn.close()
    return True, new_balance

def get_rank(top=10):
    """获取排行榜"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, balance FROM points 
        ORDER BY balance DESC LIMIT ?
    """, (top,))
    results = c.fetchall()
    conn.close()
    return results

# ===== 注册对外接口 =====

def setup(ctx):
    ctx["register_exports"]({
        "add": add_points,
        "get": get_points,
        "reduce": reduce_points,
        "rank": get_rank
    })

# ===== 插件指令处理 =====

def run(data, send_msg):
    group_id = None
    sender_qq = None
    user_text = ""

    for item in data:
        if isinstance(item, dict):
            if "GroupId" in item:
                group_id = item["GroupId"]
            if "Uin" in item:
                sender_qq = str(item["Uin"])
            if "Text" in item:
                user_text += item["Text"]

    if not group_id or not sender_qq:
        return

    # 查询积分
    if user_text.strip() == "积分":
        points = get_points(sender_qq)
        send_msg(group_id, f"💰 你的积分：{points}")

    # 排行榜
    elif user_text.strip() == "积分排行":
        ranks = get_rank(5)
        if not ranks:
            send_msg(group_id, "📭 暂无积分数据")
            return

        msg = "🏆 积分排行榜 TOP5\n" + "═" * 20 + "\n"
        for i, (user, points) in enumerate(ranks, 1):
            msg += f"{i}. {user}: {points} 分\n"
        send_msg(group_id, msg)
```

---

## 总结

| 阶段 | 关键要点 |
|------|----------|
| **部署** | 配置 `WS_URL`/`TOKEN`/`SELF_QQ`，安装依赖，运行 `main.py` |
| **开发** | 文件名=触发词，实现 `run(data, send_msg)`，通过 `data` 解析消息，通过 `send_msg` 发送消息 |
| **调试** | 使用 `print()` 输出到控制台，查看 Web 面板日志，使用 `try/except` 捕获错误 |
| **维护** | 使用 `start.sh` 实现保活，通过 Web 面板管理权限，使用 JSON/SQLite 持久化数据 |

**快速开始清单：**

1. [ ] 获取 Secluded 服务端的 `WS_URL`、`TOKEN`、机器人 QQ
2. [ ] 安装 Python 和依赖库
3. [ ] 配置 `main.py` 并创建 `BOT/` 目录
4. [ ] 编写第一个插件（如 `测试.py`）
5. [ ] 运行 `python main.py` 测试
6. [ ] 部署 `start.sh` 保活脚本

---

> **获取更多帮助**
> 
> - 查看主程序控制台日志
> - 访问 Web 管理面板的日志区域
> - 联系作者：3870149287
