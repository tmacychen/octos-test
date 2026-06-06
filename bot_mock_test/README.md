# Bot Mock 测试框架

> 本文档覆盖 Bot 测试的架构、配置和运行方式。
> 统一入口脚本为 `test_run.py`（项目根目录）。

## 架构概览

octos-test 通过 **Mock Server + pytest + TestRunner** 对 octos gateway 进行黑盒测试。每个 channel 有 3 个核心组件：

| 组件 | 文件命名 | 职责 |
|------|---------|------|
| **Mock Server** | `mock_<channel>.py` | 模拟第三方平台 API（HTTP/WebSocket） |
| **Test Runner** | `runner_<channel>.py` | 测试辅助工具，提供注入/断言方法 |
| **Test Cases** | `test_<channel>.py` | pytest 测试用例 |

### 已实现 Channel（11 个）

| Channel | Mock Server | 端口 | 协议 | 测试用例 | 充分度 |
|---------|-------------|:----:|------|:-------:|:------:|
| Telegram | `mock_tg.py` | 5000 | HTTP REST (长轮询) | 51 | 较充分 |
| Discord | `mock_discord.py` | 5001 | REST + WebSocket Gateway | 40 | 较充分 |
| Matrix | `mock_matrix.py` | 5002 | REST + Appservice | 44 | 较充分 |
| Slack | `mock_slack.py` | 5003 | Events API | 51 | 较充分 |
| Feishu | `mock_feishu.py` | 5004 | Webhook | 38 | 中等 |
| WeChat | `mock_wechat.py` | 5005 | WebSocket Bridge | 36 | 中等 |
| WhatsApp | `mock_whatsapp.py` | 5006 | WebSocket Bridge | 27 | 中等 |
| LINE | `mock_line.py` | 5007 | Webhook | 21 | 中等 |
| WeCom | `mock_wecom.py` | 5009 | REST + Webhook | 14 | 较少 |
| WeCom Bot | `mock_wecom_bot.py` | 5008 | WebSocket | 17 | 较少 |
| Email | — | — | 真实 IMAP/SMTP | 3 | 仅手动 |

### 未实现 Channel（4 个）

| Channel | 说明 |
|---------|------|
| API | REST API Channel，无 Mock Server |
| QQ Bot | WebSocket 事件流 |
| Twilio | SMS/WhatsApp Webhook |

## 运行测试

### 统一入口（推荐）

```bash
# 项目根目录
uv run python test_run.py --test bot              # 全部 Bot 测试
uv run python test_run.py --test bot telegram     # 仅 Telegram
uv run python test_run.py --test bot discord      # 仅 Discord
uv run python test_run.py --test bot slack        # 仅 Slack
uv run python test_run.py --test bot feishu       # 仅飞书
uv run python test_run.py --test bot matrix       # 仅 Matrix
uv run python test_run.py --test bot tg test_new_default  # 单个用例
uv run python test_run.py --test bot list         # 列出模块
uv run python test_run.py --test bot cases tg     # 列出用例
```

### 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `ANTHROPIC_API_KEY` | ✅ Bot 测试 | LLM API 密钥 |
| `TELEGRAM_BOT_TOKEN` | Telegram | Mock 模式下任意非空值 |
| `DISCORD_BOT_TOKEN` | 否 | Mock 模式自动填充 |
| `SLACK_BOT_TOKEN` | Slack | Mock 模式下任意非空值 |

## 通用测试模式

所有 Bot 测试遵循相同的黑盒测试流程：

```python
# 1. 注入用户消息
runner.inject("Hello!", chat_id=123)

# 2. 等待 bot 回复
msg = runner.wait_for_reply(count_before=0, timeout=TIMEOUT_COMMAND)

# 3. 断言回复内容
assert msg is not None, "Bot 未回复"
assert "expected text" in msg["text"]
```

### 超时配置

每个 channel 的超时配置在其 `test_<channel>.py` 中定义：

- `TIMEOUT_COMMAND` — 命令类（session/queue/reset）：20-30s
- `TIMEOUT_LLM` — LLM 消息：40-90s
- `TIMEOUT_ABORT` — 中断命令：60s
- `TIMEOUT_LARGE` — 大对话：180s

## 文件结构

```
bot_mock_test/
├── mock_<channel>.py       # Mock Server
├── runner_<channel>.py     # TestRunner
├── test_<channel>.py       # 测试用例
├── base_runner.py          # 基础 Runner 类
├── conftest.py             # pytest fixtures (cleanup_state)
├── test_helpers.py         # 辅助函数
├── test_gateway_events.py  # Gateway 事件测试
├── wecom_crypto.py         # 企微加密辅助
├── diagnose_gateway.py     # Gateway 诊断工具
├── diagnose_mock.py        # Mock Server 诊断工具
├── SLACK_TESTING.md        # Slack 测试详细指南
├── requirements.txt
└── README.md
```

## 添加新 Channel 测试

1. 创建 `mock_<channel>.py` — Mock Server（FastAPI）
2. 创建 `runner_<channel>.py` — TestRunner（继承 base_runner.py）
3. 创建 `test_<channel>.py` — pytest 用例
4. 在 `test_run.py` 的模块列表注册新 channel

## 已知限制

- LLM 测试受网络延迟影响
- 媒体文件（图片/语音）Mock 返回假数据
- 每次运行 bot 全新启动，不保留会话状态
- Discord Mock 不模拟 rate limit / 权限检查
- Mock Server 偶发崩溃可能导致后半段测试被 skip（见 `TEST_SKIP_ANALYSIS.md`）
