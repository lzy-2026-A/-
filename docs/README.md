# 旅客服务系统智能管理广播平台

火车站广播调度系统

## 项目结构

```
旅客服务系统智能管理广播平台/
├── backend/                  Rust 后端（TCP 服务，端口 8888）
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs           程序入口：装配各模块并启动服务器
│       ├── config.rs         配置模块（端口、音频目录、数据目录）
│       ├── account.rs        账号管理（加盐哈希、注册/登录、持久化）
│       ├── audio.rs          音频管理（播放/停止/暂停/恢复/音量/队列）
│       ├── broadcast.rs      广播调度（车次状态机、自动/手动广播、优先级队列）
│       └── communication.rs  前后端通信（JSON 协议、GBK/UTF-8 编码互通）
├── frontend/                 易语言前端（备选，需易语言正版授权）
│   ├── 启动窗口.e / 登录窗口.e / 注册窗口.e
│   ├── 后端通信.e            后端通信类（WinSock TCP + JSON 解析封装）
│   └── 主工控窗口.e          主控制台
├── frontend_py/              **Python(tkinter) 前端（推荐，无需任何授权）**
│   ├── main.py               程序入口（登录 -> 主控制台）
│   ├── client.py             TCP 通信客户端（JSON/GBK 协议封装）
│   ├── login_window.py       登录窗口
│   ├── register_window.py    注册窗口
│   └── main_window.py        主控制台（车次/广播/音频/状态）
├── docs/                     文档
├── audio/                    后端音频文件目录（可选，运行时自动创建）
├── assets/                   资源
└── images/                   前端图片（启动画面 startup.png 等）
```

## 启动步骤

### 1. 启动后端（Rust）

需要 Rust 工具链（rustup / cargo）。

```bash
cd backend
cargo build --release
target\release\train_broadcast_backend.exe   # 或直接 cargo run --release
```

首次运行会自动创建配置文件与数据目录：
- 配置：`%APPDATA%\train_broadcast_system\config.json`
- 账号：`%APPDATA%\train_broadcast_system\accounts.json`
- 音频：`%APPDATA%\train_broadcast_system\audio\`
- 日志：`%APPDATA%\train_broadcast_system\server.log`（日志写入文件，避免无控制台时管道阻塞）

服务器默认监听 `127.0.0.1:8888`。

> 关闭系统：前端主控制台"关闭系统"按钮会发送 `Shutdown` 请求，后端正常退出（1 秒内）。

### 2. 启动前端（Python，推荐）

需要 Python 3（自带 tkinter，无需额外安装任何库）：

```bash
cd frontend_py
python main.py
```

流程：登录窗口（可注册新账号）→ 主控制台。

> 主控制台**禁止直接点窗口右上角 X 关闭**，必须通过右下角【关闭系统】按钮退出；【退出登录】可返回登录窗口。

## 通信协议

- 传输层：TCP（127.0.0.1:8888）
- 消息格式：JSON，以换行符 `\n` 结尾（后端响应同样以 `\n` 定界）
- 编码：前端（易语言）发送 ANSI/GBK，后端自动识别；后端响应转 GBK 发送，前端直接显示
- 请求示例：
  - 登录：`{"Login":{"username":"admin","password":"123456"}}`
  - 添加车次：`{"AddTrain":{"train_number":"G123","departure_station":"北京南","arrival_station":"上海虹桥","departure_time":"08:00","platform":"3","status":"Scheduled"}}`
  - 无参数请求（单元请求）直接发送字符串：`"GetQueueStatus"`、`"GetActiveTrains"`、`"StopAudio"`、`"Shutdown"` 等
- 车次状态枚举：`Scheduled`（计划中）、`Boarding`（检票中）、`Delayed`（晚点）、`Departed`（已发车）、`Arrived`（已到达）、`Cancelled`（取消）
- 广播类型枚举：`BoardingAnnouncement`、`DelayAnnouncement`、`SafetyReminder`、`WelcomeMessage`、`FarewellMessage`、`EmergencyNotice`、`PlatformChange`

## 音频说明

自动/手动广播会触发音频播放。音频文件按文件名在音频目录中查找：

- 建议文件名：`welcome.mp3`、`boarding.mp3`、`boarding_start.mp3`、`delay.mp3`、`safety.mp3`、`departure.mp3`、`cancelled.mp3`
- 主控制台"音频控制"输入文件名即可播放（后端自动拼接音频目录），也支持绝对路径

无音频文件时广播只记录文字内容，不报错。

## 开发说明

- 后端编译：`cd backend && cargo build`（当前保留 4 个 warning，均为预留 API 与冗余导入，不影响运行）
- 广播调度：后端每 1 秒处理一条广播队列（自动模式下）；车次状态变化自动生成对应广播
- 安全：密码使用随机盐 + Base64 摘要存储，不保存明文
- 端到端测试：`backend\test_protocol.py`（需先启动服务器），覆盖注册/登录/车次/广播/音频/关机等 18 项协议用例，结果写入 `protocol_test_result.txt`

## 已知修复记录（2026-09-25）

1. **账号保存死锁**：`save()` 内部再次获取 accounts 读锁，而调用方已持有写锁（parking_lot RwLock 不可重入）导致注册/登录卡死。修复为 `save(&self, accounts: &HashMap)` 接收数据引用。
2. **日志阻塞冻结**：日志写 stdout 时，若 stdout 为无人消费的管道（Windows 匿名管道缓冲约 4KB），日志积满后写日志线程（广播循环、连接处理）全部阻塞，导致整个进程冻结。修复为日志写入 `server.log` 文件。
3. **关闭不退出**：accept 循环阻塞在 `accept().await`，Shutdown 后进程不退出。修复为 accept 增加 500ms 超时轮询退出标志。
