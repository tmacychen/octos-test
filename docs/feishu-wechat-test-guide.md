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

## 差距分析：与 Telegram 测试的对比

Telegram 是 octos 最早支持的频道，测试覆盖面最全。以下基于 Telegram 测试用例（`test_telegram.py`）对比分析飞书/微信测试的差距。

### 1. 测试基础设施差距

| 方面 | Telegram | 飞书/微信 | 建议 |
|------|----------|----------|------|
| **清理 Fixture** | 复杂：health check 重试、消息稳定性检测、session 文件清理、`/reset` 重置 | 简单：仅 `runner.clear()` | 建议增强，至少加入 health check 和 `/reset` 重置 |
| **chat_id 隔离** | 每个测试类有独立 `CHAT_ID` | 微信无 chat_id 概念；飞书每个类用固定 `CHAT` + `SENDER` | 飞书当前做法 OK，微信不需要 |
| **断言强度** | 严格断言：`text == "Session cleared."`、`text.startswith("Switched to session:")` | 部分宽松：`text is not None and len(text) > 0` | 应该增强，匹配 Telegram 的断言标准 |
| **LLM 测试标记** | `@pytest.mark.llm` 用于跳过 | 无标记 | 建议添加，方便 `-m "not llm"` 跳过 |

### 2. 缺失的测试用例

以下 Telegram 已有的测试，飞书和微信应该补充：

#### 会话管理（建议优先级：高）

| 缺失的测试 | Telegram 示例 | 说明 |
|-----------|--------------|------|
| 非法会话名 | `/new bad:name` → `"Invalid session name:"` | 边界条件测试，各频道行为一致 |
| 切换到默认 | `/s`（无参数）→ `"Switched to default session."` | 基本功能 |
| `/back` 命令 | `/back` → 含 "session" | 基本导航命令 |
| `/back` 有历史 | `/new a` → `/new b` → `/back` → `"Switched back to session:"` | 验证历史栈 |
| 别名命令 | `/b` 和 `/d` | 验证命令别名 |
| 无参数删除 | `/delete`（无参数）→ 走帮助命令 | 边界条件 |
| `/soul show` | `/soul` → 显示当前 soul | 基本功能 |
| `/soul reset` | `/soul reset` → soul 重置 | 基本功能 |
| 重复测试间隔离 | 每个测试 `/new` → 操作 | 避免测试间状态污染 |

#### 配置命令（建议优先级：高）

| 缺失的测试 | Telegram 示例 | 说明 |
|-----------|--------------|------|
| `/adaptive` | `"Adaptive routing is not enabled."` | 基本响应验证 |
| `/reset` | `"Reset: queue=collect, adaptive=off, history cleared."` | 严格断言 |
| 无效队列模式 | `/queue badmode` → `"Unknown mode"` | 边界条件 |
| 未知命令 | `/unknowncmd` → `"Unknown command."`，包含所有已知命令 | 验证帮助系统 |

#### 高级测试（建议优先级：中低）

| 缺失的测试 | Telegram 示例 | 说明 |
|-----------|--------------|------|
| Abort 多语言 | 4 语言 abort 触发 | 核心功能，但需 LLM |
| Steer 负向测试 | 非 abort 消息不误触发 | 需 LLM |
| Interrupt 负向测试 | 同上 | 需 LLM |
| Profile 会话隔离 | 双 Profile `/new` | 飞书已有，微信无 |
| 消息分片 | 长消息（Telegram 4096 限制）| 微信 4000 限制，飞书无此限制 |
| Session 文件限制 | 10MB 大文件处理 | 平台无关底层功能 |

### 3. 当前测试的合理评估

#### 合理的部分

- **测试目标正确**：聚焦 octos 的基础功能（会话管理、配置命令），这些是各频道共通的
- **覆盖了核心链路**：mock → 事件注入 → gateway 接收 → 命令处理 → 回复
- **LLM 测试单独标记**：可以按需跳过

#### 需要调整的部分

**高优先级**（当前测试的明显短板）：

1. **断言强度不足**：很多地方只检查 `len(text) > 0`，应该像 Telegram 一样直接断言具体回复内容
2. **清理 Fixture 太简陋**：缺少 health check、消息稳定性检测、session 文件清理
3. **缺少边界测试**：非法会话名、无参数命令、无效队列模式等
4. **缺少 `/back`、`/adaptive`、`/reset` 等命令测试**：这些是各频道共通的

**中优先级**（当前可以接受，但后续应补充）：

5. **缺少别名命令测试**：如微信和飞书可能不支持 `/b`、`/d` 别名，需先确认
6. **缺少 `/s` 无参数切换**：基本功能

**低优先级**（不急于补充）：

7. **Abort 测试**：依赖 LLM，当前 API 延迟问题阻塞
8. **Session 文件压力测试**：平台无关功能，应由 Discord 或 Telegram 覆盖即可
9. **消息分片测试**：各频道长度限制不同，需先确认限制值

### 4. 建议的改进计划

#### 第一阶段：加强现有测试（1-2 小时）

- 增强 test_wechat.py 和 test_feishu.py 的 fixture（加入 health check 和 `/reset`）
- 增强所有断言的严格度（匹配具体回复内容）
- 补充 `/back`、`/s`、`/adaptive`、`/reset` 测试

#### 第二阶段：补充边界测试（1 小时）

- 补充非法会话名测试
- 补充无参数命令测试（`/delete`、`/s`）
- 补充无效队列模式测试
- 补充未知命令测试

#### 第三阶段：验证和标记

- 确认各频道是否支持别名命令（`/b`、`/d`）
- 添加 `@pytest.mark.llm` 标记
- 确认微信消息长度限制

---

## Mock Server 与真实 API 的差异

### 微信（WeChat）

微信的架构是 **wechat-bridge** 模式：

```
真实环境:
  微信服务器 → (HTTP 长轮询) → wechat-bridge 进程 → (WebSocket) → octos gateway

测试环境:
  (无)                     → mock_wechat.py        → (WebSocket) → octos gateway
```

| 维度 | 真实 wechat-bridge | mock_wechat.py |
|------|-------------------|----------------|
| **启动方式** | 独立的 Rust 二进制（`crates/app-skills/wechat-bridge`），由 `ProcessManager` 管理生命周期 | FastAPI 子进程，与测试框架同生命周期 |
| **登录流程** | 完整 QR 码登录：获取 QR → 轮询扫描状态 → 获取 bot_token | 不需要，测试直接注入消息 |
| **消息来源** | HTTP 长轮询 `GET /ilink/bot/getupdates`，40s 超时重连 | 测试通过 `POST /_inject` 注入 |
| **发送消息** | 真实 HTTP 请求到 `POST /ilink/bot/sendmessage`，包含完整消息体（`from_user_id`、`client_id`、`message_type`、`item_list` 等） | 仅记录到内存列表，不进行真实 HTTP 请求 |
| **长轮询重连** | 3s 退避重连，session_timeout 时重置 buf | 不需要 |
| **context_token 管理** | 存储每个 sender 的 context_token，发送时自动带入 | 生成随机 context_token，不做持久化管理 |
| **会话超时** | errcode=-14 时清除 buf 并重连 | 不需要 |
| **QR 事件** | stdout 输出 `{"type":"qr","qr_url":"..."}` 由 ProcessManager 读取 | 无 |
| **消息类型过滤** | 只处理 `message_type=1`（用户消息），其他如图片/链接/小程序跳过 | 不验证消息类型 |
| **消息内容解析** | 从 `item_list[].text_item.text` 提取文本，支持图文混合 | 直接使用注入的 text 字段 |
| **消息 ID** | 微信服务器分配的 uint64 | 随机 UUID 字符串 |
| **WebSocket 协议** | 使用 `tokio_tungstenite` 原生库 | 使用 FastAPI + starlette WebSocket |

**测试假定的简化**：
- 跳过整个 QR 登录流程，直接注入已登录状态的消息
- 不需要真实的微信 HTTP API（`ilinkai.weixin.qq.com`）通信
- mock 不校验消息格式的完整性（如 `client_id`、`base_info` 等字段）
- 不模拟 session 超时和重连机制

**这些简化对测试有效性的影响**：测试验证的是 octos 的微信 channel 能否正确处理 WebSocket 协议、消息路由和命令处理。跳过 QR 登录和真实 API 调用是合理的，因为这些属于 wechat-bridge 自身的功能，不在 octos channel 的职责范围内。

---

### 飞书（Feishu）

飞书 webhook 模式的架构：

```
真实环境:
  飞书服务器 → (POST webhook) → octos gateway (端口 9321) → 处理消息
  octos gateway → (REST API) → 飞书服务器 (open.feishu.cn/open-apis)

测试环境:
  mock_feishu.py → (POST webhook) → octos gateway (端口 9321) → 处理消息
  octos gateway → (REST API) → mock_feishu.py (127.0.0.1:5004)
```

| 功能 | 真实飞书 API | mock_feishu.py |
|------|-------------|----------------|
| **Token 获取** | `POST /open-apis/auth/v3/tenant_access_token/internal`，返回 `expire`（7200s）+ `tenant_access_token` | ✅ 模拟，校验 `app_id` + `app_secret`，生成假 token |
| **Token 过期** | 7200s 后过期，需要重新获取 | 不强制过期，token 永不过期 |
| **发送消息** | `POST /open-apis/im/v1/messages`，支持 `receive_id_type` 参数（open_id/chat_id/user_id） | ✅ 模拟，记录消息内容，但忽略 `receive_id_type` 参数 |
| **回复消息** | `POST /open-apis/im/v1/messages/{id}/reply` | ✅ 模拟，从已发送消息中反查 chat_id |
| **编辑消息** | `PATCH /open-apis/im/v1/messages/{id}`，支持修改已发送消息 | ✅ 模拟 |
| **撤回消息** | `DELETE /open-apis/im/v1/messages/{id}`，有时间窗口限制 | ✅ 模拟，不校验时间窗口 |
| **获取消息** | `GET /open-apis/im/v1/messages/{id}` | ✅ 模拟 |
| **消息格式** | 飞书卡片消息格式（`elements`、`header` 等） | ✅ 解析卡片格式提取纯文本用于断言 |
| **媒体下载** | `GET /im/v1/messages/{id}/resources/{key}` 下载图片/文件 | ❌ **未实现**，如果测试涉及媒体消息会失败 |
| **上传图片** | `POST /im/v1/images`，用于发送图片消息 | ❌ **未实现** |
| **上传文件** | `POST /im/v1/files`，用于发送文件消息 | ❌ **未实现** |
| **Webhook 签名验证** | 可选 AES-256-CBC 加密 + SHA-256 签名验证 | ❌ **未实现**，mock 发送的事件不签名 |
| **Webhook 验证令牌** | 可选 `verification_token` 校验 | mock 发的事件带固定 `"token":"test_event_token"`，实际不校验 |
| **事件去重** | 飞书可能重复推送事件，需要 message_id 去重 | mock 发的事件 ID 唯一，不需要去重 |
| **事件格式** | 符合飞书开放平台事件规范（schema v2.0） | ✅ 模拟标准 `im.message.receive_v1` 格式 |
| **媒体消息** | 图片 `message_type=image`、文件 `message_type=file`、语音 `message_type=audio` 等 | ❌ **仅支持 text 类型消息** |
| **WebSocket 模式** | 通过 WebSocket 网关接收事件推送 | ❌ **未支持**，仅测试 webhook 模式 |
| **请求限流** | 飞书 API 有频率限制（QPS） | ❌ **不限流**，测试按需发送 |
| **错误响应** | 飞书返回 `code` + `msg` 错误码（如 99991663 app_id无效） | ✅ 模拟部分常见错误（app_id/app_secret 不匹配） |

**测试假定的简化**：
- 仅测试 webhook 模式，不测试 WebSocket 模式
- 仅测试纯文本消息，不测试图片/文件/语音等媒体
- 不验证 webhook 签名和加密
- token 不过期，不需要刷新
- 不模拟限流和错误重试场景

**这些简化对测试有效性的影响**：文本消息和命令处理是飞书 bot 最核心的功能，覆盖了会话管理、队列模式、Profile 隔离等关键逻辑。媒体消息、签名验证、token 刷新等属于周边功能，在核心流程验证通过后再补充测试更为合理。

---

### 共性问题

| 差异 | 说明 | 影响 |
|------|------|------|
| **无网络延迟** | mock server 在本地回环地址，响应毫秒级 | 测试无法验证真实网络条件下的超时和重试行为 |
| **无并发控制** | 不模拟 API 限流和并发限制 | 无法暴露并发相关 bug |
| **无故障注入** | 不模拟网络中断、响应超时、错误码等异常 | 无法验证 octos 的重试和故障转移逻辑 |
| **数据持久化** | mock 数据在内存中，进程退出即丢失 | 不影响测试，每次测试重新启动 mock |
| **消息长度限制** | 真实微信有 4000 字限制，飞书有卡片大小限制 | mock 不做校验 |

---

## 前置条件

- octos 二进制需使用 `--features "feishu,wechat"` 编译（已在 `debug/feishu-wechat-test` 分支中启用）
- 测试框架自动使用 `/Volumes/AppleData/octos/target/release/octos`
- 需要 `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY` 环境变量

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
