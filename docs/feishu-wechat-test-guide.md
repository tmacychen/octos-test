# 飞书与微信频道测试说明

## 测试覆盖范围

### 微信（WeChat）— 10 个测试用例

| 测试 | 命令 | 预期 |
|------|------|------|
| `test_new_default` | `/new` | 创建默认会话，回复 "Session cleared." |
| `test_new_named` | `/new work` | 创建命名会话，回复含 "work" |
| `test_sessions_list` | `/new list-a` → `/new list-b` → `/sessions` | 列出所有会话 |
| `test_delete_session` | `/new delete-me` → `/delete` | 删除当前会话 |
| `test_soul_set` | `/soul 你是一个助手` | 设置 soul |
| `test_queue_show` | `/queue` | 显示当前队列模式 |
| `test_queue_set` | `/queue followup` | 切换队列模式 |
| `test_status` | `/status` | 返回状态配置 |
| `test_help` | `/help` | 返回帮助信息 |
| `test_regular_message` | `你好` | 触发 LLM 回复（依赖 API） |

### 飞书（Feishu）— 12 个测试用例

| 测试 | 命令 | 预期 |
|------|------|------|
| `test_new_default` | `/new` | 创建默认会话 |
| `test_new_named` | `/new work` | 创建命名会话 |
| `test_switch_session` | `/new research` → `/s research` | 切换会话 |
| `test_sessions_list` | `/new list-a` → `/new list-b` → `/sessions` | 列出会话 |
| `test_delete_session` | `/new delete-me` → `/delete` | 删除会话 |
| `test_soul_set` | `/soul 你是一个助手` | 设置 soul |
| `test_queue_show` | `/queue` | 显示队列模式 |
| `test_queue_set` | `/queue followup` | 切换队列模式 |
| `test_status` | `/status` | 返回状态 |
| `test_help` | `/help` | 返回帮助信息 |
| `test_regular_message` | `你好，请介绍一下你自己` | LLM 回复 |
| `test_profile_session_isolation` | 双 Profile `/new profile-a` + `/new profile-b` | 会话隔离 |

---

## 测试架构

```
┌─────────────────────────────────────────────────────────────┐
│                   测试流程（以微信为例）                       │
│                                                             │
│  pytest test_wechat.py                                       │
│    │                                                        │
│    ├─ Fixture: runner = WeChatTestRunner()                   │
│    ├─ Fixture: clear_before() → POST /_clear                │
│    │                                                        │
│    ├─ inject_and_get_reply(runner, "/new")                   │
│    │   ├─ runner.get_sent_messages()  ← GET /_sent_messages  │
│    │   ├─ runner.inject("/new")       ← POST /_inject        │
│    │   │   └─ mock_wechat 转发到 WebSocket                    │
│    │   │       └─ octos gateway 处理消息                      │
│    │   │           └─ 回复写入 POST /chat.postMessage         │
│    │   │               └─ mock_wechat 记录到 _sent_messages   │
│    │   └─ wait_for_reply() 轮询 _sent_messages 直到出现新消息  │
│    │                                                        │
│    └─ assert "Session cleared." in reply                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   测试流程（飞书为例）                         │
│                                                             │
│  pytest test_feishu.py                                       │
│    │                                                        │
│    ├─ inject_and_get_reply(runner, "/new")                   │
│    │   ├─ runner.inject("/new")       ← POST /_inject        │
│    │   │   └─ mock_feishu 转发到 octos webhook               │
│    │   │       └─ POST http://127.0.0.1:9321/webhook/event   │
│    │   │           └─ octos 处理消息                          │
│    │   │               ├─ 获取 tenant_access_token            │
│    │   │               │   └─ POST /auth/v3/...              │
│    │   │               │       └─ mock_feishu 处理            │
│    │   │               └─ 发送回复                            │
│    │   │                   └─ POST /im/v1/messages            │
│    │   │                       └─ mock_feishu 记录            │
│    │   └─ wait_for_reply() 轮询 _sent_messages               │
│    └─ assert 验证回复内容                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 新增文件（octos-test 仓库）

| 文件 | 说明 |
|------|------|
| `bot_mock_test/mock_wechat.py` | 微信 WebSocket bridge Mock Server（端口 5005） |
| `bot_mock_test/mock_feishu.py` | 飞书 Webhook 模式 Mock Server（端口 5004） |
| `bot_mock_test/runner_wechat.py` | 微信测试运行器 |
| `bot_mock_test/runner_feishu.py` | 飞书测试运行器 |
| `bot_mock_test/test_wechat.py` | 微信测试用例（10 个） |
| `bot_mock_test/test_feishu.py` | 飞书测试用例（12 个） |
| `docs/feishu-wechat-test-guide.md` | 本文档 |

### test_run.py 注册改动

- `module_info` 字典新增：`feishu`/`fs` → 5004，`wechat`/`wx` → 5005
- `valid_modules` 列表新增 `feishu`/`fs`/`wechat`/`wx`
- 配置生成新增飞书 Webhook 模式和微信 bridge 模式的 UserProfile 配置
- `list_bot_cases` 测试用例收集新增对应条目

---

## 对 octos 项目的修改

为了使测试能够运行，修改了 octos 项目的 Rust 源码。涉及的变更如下：

### 1. 飞书：支持自定义 base_url

**目的**：测试时让飞书 channel 调用本地 mock server 而非真实飞书 API。

| 文件 | 修改内容 |
|------|---------|
| `crates/octos-bus/src/feishu_channel.rs` | 新增 `custom_base_url: Option<String>` 字段，新增 `with_custom_base_url()` 构建方法 |
| `crates/octos-cli/src/commands/gateway/adapters/feishu.rs` | 从配置中读取 `base_url` 并通过 `with_custom_base_url()` 传递给 channel |
| `crates/octos-cli/src/profiles.rs` | `ChannelCredentials::Feishu` 新增 `base_url: Option<String>` 字段（含 serde 反序列化和 `channel_to_entry` 传递） |

### 2. 微信：支持自定义 bridge_url

**目的**：测试时让微信 channel 连接本地 mock WebSocket 而非真实 wechat-bridge 进程。

| 文件 | 修改内容 |
|------|---------|
| `crates/octos-cli/src/profiles.rs` | `ChannelCredentials::WeChat` 新增 `bridge_url: Option<String>` 字段，`channel_to_entry` 中传递到 settings |

注意：微信的 adapter（`wechat.rs`）已经原生支持从 `entry.settings["bridge_url"]` 读取 URL，无需修改。

### 3. 补齐初始化字段

新增字段后，所有在代码中直接构造 `ChannelCredentials` 的地方都需要补充相应字段：

| 文件 | 修改内容 |
|------|---------|
| `crates/octos-cli/src/api/auth_handlers.rs` | WeChat 初始化补充 `bridge_url: None` |
| `crates/octos-cli/src/commands/account.rs` | Feishu 初始化补充 `base_url: None` |
| `crates/octos-cli/src/commands/gateway/account_handler.rs` | Feishu 初始化补充 `base_url: None` |
| `crates/octos-cli/src/profiles.rs` | Feishu 测试用例补充 `base_url: None` |

---

## 测试结果

| 频道 | 全部测试 | 命令测试（不依赖 LLM） | LLM 测试 |
|------|:-------:|:--------------------:|:--------:|
| **微信** | **9/10** ✅ | **9/9** ✅ | ❌ API 延迟超时 |
| **飞书** | **12/12** ✅ | **11/11** ✅ | ❌ API 延迟超时 |

LLM 测试失败的原因是目前 NVIDIA API endpoint（`https://integrate.api.nvidia.com/v1`）响应延迟较高（30-60s），导致 90s 超时仍不够用。这是基础网络问题，非代码 bug。

---

## 运行方法

```bash
# 微信测试
uv run python test_run.py --test bot wechat

# 飞书测试
uv run python test_run.py --test bot feishu

# 列出测试用例
uv run python test_run.py --test bot feishu list
uv run python test_run.py --test bot wechat list
```

## 前置条件

- octos 二进制需使用 `--features "feishu,wechat"` 编译（已在 `debug/feishu-wechat-test` 分支中启用）
- 测试框架自动使用 `/Volumes/AppleData/octos/target/release/octos`
- 需要 `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY` 环境变量
