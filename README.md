# Octos 自动化测试框架

## 一、快速开始

### 前置要求

1. **Python 环境**
   ```bash
   # 需要 Python 3.8+
   python3 --version

   # 推荐使用 uv（超快的 Python 包管理器）
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # 安装所有依赖
   uv sync
   ```

2. **Octos 二进制文件**

   测试脚本自动查找 octos 二进制，搜索顺序：
   - `OCTOS_BINARY` 环境变量
   - `./target/release/octos`
   - `../target/release/octos`
   - 系统 `PATH`

   ```bash
   # 设置环境变量（推荐）
   export OCTOS_BINARY=/path/to/octos/target/release/octos

   # 或手动编译（需要 octos 源码）
   cargo build --release -p octos-cli --features telegram,discord,slack,matrix,feishu,wechat,whatsapp,line,wecom,wecom-bot,email,api
   ```

3. **环境变量**
   ```bash
   # Bot 测试必需（二选一，都指向 NVIDIA OpenAI 兼容 API）
   export OPENAI_API_KEY=nvapi-your-nvidia-key    # 推荐
   export ANTHROPIC_API_KEY=your_api_key
   export TELEGRAM_BOT_TOKEN=your_bot_token  # Mock 模式下任意非空值
   ```

### 运行测试

```bash
# 全部测试
uv run python test_run.py all

# Bot 测试
uv run python test_run.py --test bot
uv run python test_run.py --test bot telegram   # 仅 Telegram
uv run python test_run.py --test bot discord    # 仅 Discord

# CLI 测试
uv run python test_run.py --test cli
uv run python test_run.py --test cli -s Init

# Serve 测试
uv run python test_run.py --test serve
uv run python test_run.py --test serve 8.1
```

---

## 二、测试模块

### 2.1 Bot Mock 测试

通过 **Mock Server + pytest** 对 octos gateway 进行黑盒测试。每个 channel 模拟第三方平台 API，验证 octos 在对话管理、命令响应、多用户隔离等方面的行为。

#### 已实现 Channel（11 个）

| Channel | Mock Server | 端口 | 协议 | 用例数 | 充分度 |
|---------|-------------|:----:|------|:------:|:------:|
| Telegram | `mock_tg.py` | 5000 | HTTP REST (长轮询) | 51 | 较充分 |
| Discord | `mock_discord.py` | 5001 | REST + WebSocket Gateway | 37 | 较充分 |
| Matrix | `mock_matrix.py` | 5002 | REST + Appservice | 41 | 较充分 |
| Slack | `mock_slack.py` | 5003 | Events API | 47 | 较充分 |
| Feishu | `mock_feishu.py` | 5004 | Webhook | 34 | 中等 |
| WeChat | `mock_wechat.py` | 5005 | WebSocket Bridge | 34 | 中等 |
| WhatsApp | `mock_whatsapp.py` | 5006 | WebSocket Bridge | 23 | 基础 |
| LINE | `mock_line.py` | 5007 | Webhook | 9 | 较少 |
| WeCom | `mock_wecom.py` | 5008 | REST + Webhook | 7 | 较少 |
| WeCom Bot | `mock_wecom_bot.py` | 5009 | WebSocket | 14 | 较少 |
| Email | — | — | 真实 IMAP/SMTP | 3 | 仅手动 |

#### 未实现 Channel（4 个）

| Channel | 说明 |
|---------|------|
| API | REST API Channel，无 Mock Server |
| QQ Bot | WebSocket 事件流 |
| Twilio | SMS/WhatsApp Webhook |

#### 已覆盖的黑盒功能

| 功能类别 | 说明 |
|---------|------|
| 会话管理 | `/new`, `/s`, `/back`, `/delete`, `/sessions` |
| 配置命令 | `/soul`, `/queue`, `/status`, `/reset`, `/adaptive`, `/help` |
| LLM 消息 | 英文/中文/身份信息 |
| 中断命令 | 中/英/日/俄语 abort |
| 多用户隔离 | 不同 chat_id 独立会话 |
| 消息分片 | 超长消息自动拆分 |
| 文件限制 | 10MB 大小上限 |
| Stream 编辑 | 消息逐步更新（Telegram/Feishu/Discord） |
| 并发限制 | 10 线程同时创建会话 |

### 2.2 CLI 测试

通过 `test_cases.json` 驱动的 CLI 子命令测试（35 个用例）：

| 类别 | 用例数 | 说明 |
|------|:------:|------|
| CLI | 3 | `--help`, `--version`, 单消息模式 |
| Init | 4 | `init --help`, `--defaults`, config.json 检查 |
| Clean | 3 | `clean --help`, 无/空目录清理 |
| Status | 2 | 状态查询 |
| Skills | 5 | list/search/remove |
| Auth | 2 | 登录状态 |
| Channels | 2 | 频道状态 |
| 其他 | 14 | Completions/Cron/Chat/Gateway/Serve/Docs/Tools/Security |
| **合计** | **35** | |

### 2.3 Serve 测试

通过 `test_serve.py` 验证 `octos serve` 的 REST API、SSE 流式响应、Dashboard 和认证（7 个用例）。

### 2.4 其他测试

| 模块 | 文件 | 用例数 |
|------|------|:------:|
| Gateway 事件 | `test_gateway_events.py` | 2 |
| NVIDIA API | `test_nvidia_api.py` | 2 |
| Matrix 扩展 | `test_matrix_extensions.py` | 3 |

---

## 三、框架架构

```
octos-test/
├── test_run.py                    # 统一测试入口
├── AGENTS.md                      # CodeBuddy 项目指引
├── ROADMAP.md                     # 测试覆盖路线图
├── README.md                      # 本文档
│
├── bot_mock_test/                 # Bot Mock 测试
│   ├── mock_<channel>.py          # Mock Server (11 个)
│   ├── runner_<channel>.py        # TestRunner (11 个)
│   ├── test_<channel>.py          # 测试用例
│   ├── base_runner.py             # 基础 Runner 类
│   ├── conftest.py                # pytest fixtures
│   ├── test_helpers.py            # 辅助函数
│   ├── wecom_crypto.py            # 企微加密
│   └── diagnose_gateway.py        # 诊断工具
│
├── cli_test/                      # CLI 测试
│   ├── test_cli.py                # 测试运行器
│   └── test_cases.json            # 用例定义（35 个）
│
├── serve/                         # Serve 测试
│   ├── test_serve.py              # Serve 功能测试
│   ├── run_serve_tests.py         # 运行脚本
│   └── README.md
│
├── docs/                          # 文档
│   ├── channel_test_coverage_analysis.md   # 覆盖分析
│   ├── email_context_issue.md              # Email 上下文膨胀
│   └── SPEC_bot_flaky_retry.md             # Flaky retry SPEC
│
├── archive/                       # 归档的旧文档
└── test_*.py                      # 根目录独立测试
```

### 核心机制

| 机制 | 说明 |
|------|------|
| **二进制自动检测** | 支持环境变量、相对路径、系统 PATH |
| **可选编译** | 自动检测 octos 源码并触发 `cargo build` |
| **Mock Server 模式** | 无需真实 API 凭证即可运行 |
| **Flaky 重试** | 失败检测 + 服务重启 + 重试机制 |
| **目录隔离** | CLI/每个测试类别独立目录 |
| **Session 日志** | 全部 stdout/stderr 输出到时间戳日志文件 |

---

## 四、使用说明

```bash
# 查看帮助
uv run python test_run.py --help

# Bot 测试
uv run python test_run.py --test bot                    # 全部
uv run python test_run.py --test bot telegram           # 仅 Telegram
uv run python test_run.py --test bot tg test_new_default  # 单个用例
uv run python test_run.py --test bot list               # 列出模块
uv run python test_run.py --test bot cases tg           # 列出用例
uv run python test_run.py --test bot tg --from-test test_abort  # 从指定用例开始

# CLI 测试
uv run python test_run.py --test cli
uv run python test_run.py --test cli -s Init
uv run python test_run.py --test cli -v

# Serve 测试
uv run python test_run.py --test serve
uv run python test_run.py --test serve 8.1
uv run python test_run.py --test serve list
```

### 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `OCTOS_BINARY` | 否 | octos 二进制路径（自动检测） |
| `ANTHROPIC_API_KEY` | Bot 测试 | LLM API 密钥 |
| `TELEGRAM_BOT_TOKEN` | Telegram | Mock 模式下任意非空值 |
| `DISCORD_BOT_TOKEN` | 否 | Mock 模式自动填充 |
| `SLACK_BOT_TOKEN` | Slack | Mock 模式下任意非空值 |

### 测试输出

```
/tmp/octos_test/
├── .octos/                             # Bot 测试配置
│   ├── test_telegram_config.json
│   ├── test_discord_config.json
│   └── ...
├── cli/                                # CLI 测试隔离工作区
│   ├── Init_<timestamp>/
│   └── Clean_<timestamp>/
└── logs/
    ├── build.log
    ├── cli_test.log
    ├── octos_*_bot_test_<ts>.log
    └── sessions/<timestamp>.log
```

---

## 五、Rust 代码修改

为支持 Mock 测试模式，对 octos 进行了以下必要修改（不影响生产环境）：

| 文件 | 改动 | 说明 |
|------|------|------|
| `telegram_channel.rs` | `TELOXIDE_API_URL` 环境变量 | 重定向所有 API 请求到 Mock Server |
| `discord_channel.rs` | `DISCORD_API_BASE_URL` + `HttpBuilder::proxy()` | 支持自定义 API base URL + 禁 ratelimiter |
| `gateway_dispatcher.rs` | Soul 按 chat_id 隔离存储 | `{data_dir}/users/{chat_id}/soul.md` |
| `gateway_runtime.rs` | 补充缺失的 `MAIN_PROFILE_ID` import | 编译修复 |

详见 [AGENTS.md](AGENTS.md) 和 [TELEGRAM_PROFILE_ROUTING_ANALYSIS.md](TELEGRAM_PROFILE_ROUTING_ANALYSIS.md)。

---

## 六、当前统计

| 模块 | 用例数 |
|------|:------:|
| Telegram | 51 |
| Discord | 37 |
| Matrix | 41 |
| Slack | 47 |
| Feishu | 34 |
| WeChat | 34 |
| WhatsApp | 23 |
| LINE | 9 |
| WeCom | 7 |
| WeCom Bot | 14 |
| Email | 3 |
| Gateway Events | 2 |
| CLI | 35 |
| Serve | 7 |
| NVIDIA API | 2 |
| Matrix Ext | 3 |
| **Bot 测试合计** | **302** |
| **全部测试合计** | **349** |
