# Octos Channel 测试 Roadmap

> 黑盒测试视角：仅通过外部消息输入 / Bot 回复输出验证 octos 功能。

---

## 一、当前完成情况

通过 `Mock Server ↔ octos gateway ↔ 断言回复` 的黑盒方式，**全部 15 个 channel 已有测试文件**（对应 octos 所有 channel 实现）。

| Channel | 用例数 | 黑盒覆盖的外部功能 | 测试方式 |
|---------|:------:|------------------|----------|
| Telegram | 54 | `/new`, `/s`, `/back`, `/delete`, `/soul`, `/queue`, `/status`, `/reset`, `/adaptive`, `/abort`, `/clear`, LLM 消息、多用户隔离、白名单过滤、流式编辑、消息分片、10MB 限制、Inline Keyboard、Typing Indicator、Mention Gating、HTML Fallback、图片发送、消息去重 | Mock HTTP API |
| Slack | 51 | 会话管理命令、配置命令、LLM、中断、多用户隔离、并发限制、去重、白名单过滤 | Mock HTTP + WS |
| Matrix | 44 | 会话管理命令、配置命令、LLM、中断、多用户隔离、profile 路由、去重、白名单过滤 | Mock HTTP + Appservice |
| Discord | 41 | 会话管理命令、配置命令、LLM、中断、多频道隔离、并发限制、去重、白名单过滤、WS 断线重连、消息分片 | Mock HTTP + WS Gateway |
| Feishu | 38 | 会话管理命令、配置命令、LLM、中断、多用户隔离、流式编辑、10MB 限制、消息去重、白名单过滤 | Mock WS |
| WeChat | 37 | 会话管理命令、配置命令、LLM、中断、多用户隔离、并发限制、消息分片、10MB 限制、去重、WS 断线重连 | Mock WS Bridge |
| WhatsApp | 28 | 会话管理命令、配置命令、LLM、中断、多用户隔离、去重、白名单过滤、WS 断线重连 | Mock WS Bridge |
| LINE | 29 | 会话管理命令、配置命令、LLM、中断、多用户隔离、消息去重、白名单过滤、媒体消息（Image/Audio/Video/File/Location/Sticker）、@提及群组门控、Typing Indicator | Mock Webhook |
| QQ Bot | 35 | 群消息、C2C 私聊、会话管理命令、配置命令、LLM、中断、多用户隔离、消息去重、白名单过滤、消息分片、WS 断线重连、健康检查 | Mock WS Gateway |
| Twilio | 24 | SMS 消息、会话管理命令、配置命令、LLM、中断、多用户隔离、消息去重、白名单过滤、消息分片、健康检查 | Mock Webhook |
| WeCom Bot | 20 | WS 连接、认证、消息收发、会话管理命令、配置命令、LLM、流式编辑、多用户隔离、去重、白名单过滤、WS 断线重连、消息分片 | Mock WS |
| WeCom | 16 | URL 验证、加密回调、消息发送、会话管理命令、配置命令、LLM、多用户隔离、去重、白名单过滤、健康检查 | Mock REST + Webhook |
| Email | 3 | SMTP 发邮件 → IMAP 收回复（真实邮箱） | 真实 IMAP/SMTP |
| **API** | **38** | WS 连接/hello、session/list、session/open+turn/start、session/delete、session/snapshot、session/messages_page、session/status.get、session/title.set、content/list、turn/interrupt、system/status.get、/health、/api/version、/metrics、认证、Dashboard、启动/绑定地址 | WS JSON-RPC + REST |

---

## 二、已完成的黑盒功能覆盖

以下功能已通过**外部消息交互**验证：

- **会话管理**：`/new`, `/s`, `/back`, `/delete`, `/sessions`, `/clear`（全部已测 channel）
- **配置命令**：`/soul`, `/queue`, `/status`, `/reset`, `/adaptive`, `/help`（全部已测 channel）
- **LLM 消息**：英文/中文普通消息（全部已测 channel）
- **中断**：`/abort` + 中英日俄多语言触发词
- **多用户隔离**：不同 chat_id / channel_id 独立会话（全部已测 channel）
- **并发限制**：10 线程同时创建会话（Telegram, Slack, Feishu, WeChat）
- **消息分片**：超长消息自动拆分（WeChat 4000 字符等）
- **流式编辑**：飞书 PATCH 编辑后内容正确更新
- **10MB 限制**：超大消息 / 会话文件被限制
- **消息去重**：相同 message_id 只处理一次（Feishu, LINE, WhatsApp, WeChat, Discord, Slack, Matrix, QQ Bot, Twilio, WeCom Bot）
- **白名单过滤**：allowed_senders 非空时，非白名单用户消息被忽略（Telegram, LINE, WhatsApp, Discord, Slack, Matrix, Feishu, QQ Bot, Twilio, WeCom Bot, WeCom）
- **LINE 媒体消息**：Image/Audio/Video/File/Location/Sticker 事件注入（LINE）
- **LINE @提及群组门控**：群组 @mention 时回复，未 @mention 时沉默（LINE）
- **WS 断线重连**：断开 WS 连接后等待 bot 自动重连并验证通信（Discord, WeChat, WhatsApp, WeCom Bot, QQ Bot）
- **Email 消息分片**：超长 SMS 验证 bot 能处理（Twilio 1600+ 字符）
- **API Channel**：WS 连接/hello、session/list、session/open+turn/start、session/delete、session/snapshot、session/messages_page、session/status.get、session/title.set、content/list、turn/interrupt、system/status.get（API）
- **跨 channel 会话隔离**：同一 gateway 上 telegram + discord 同时发消息，各 channel session 独立隔离，互不干扰

---

## 三、现状分析与规划思路

### 3.1 各 Channel 测试充分度评估

**所有 15 个 octos channel 均已覆盖**，按充分度分层：

| 层级 | Channel | 当前用例数 | 评估 | 说明 |
|:----:|---------|:----------:|:----:|------|
| S | Telegram | 54 | **充分** | 包含边缘/高级特性测试（Keyboard/Typing/Mention/图片发送等） |
| A | Slack / Matrix / Discord | 41-51 | **较充分** | 核心路径全覆盖；少量高级特性未覆盖（Embed/Reaction/Typing/health_check） |
| B | Feishu / WeChat / WhatsApp / LINE / QQ Bot | 28-38 | **较充分** | 基本功能齐全；LINE 已补媒体/提及；QQ Bot Wi-Fi 断线重连 |
| C | Twilio / WeCom Bot / WeCom | 16-24 | **充分** | 核心命令全，去重+白名单已补 |
| D | API | 38 | **较充分** | task/approval 未覆盖（待评估是否必要） |
| E | Email | 3 | **较薄弱** | 仅手动测试，可补充更多真实邮箱测试用例 |

### 3.2 关键问题识别

1. **Email 测试较薄弱**：仅 3 个用例，LLM context 膨胀 / QQ 邮箱自发自收 UNSEEN 失效。保留真实邮箱测试，补充更多场景。
2. **session_delete_rx 阻塞 Bug（issue #1407）**：无 `--api-port` 时消息无法分发到 LLM，影响所有不带 api 的 gateway。需等待 octos 修复后回归验证。
3. **Telegram profile routing 缺失**：不同 chat_id 消息被路由到同一 profile，`test_soul_per_profile` 正确 skip。等待 octos 实现。
4. ~~**Discord / Matrix 部分高级特性未覆盖**~~ ✅ 已全覆盖：Embed、Reaction、health_check、Typing Indicator 均已补齐。

### 3.3 octos 代码 vs 测试覆盖交叉分析

从 octos main 分支代码中提取各 channel 功能，与测试覆盖交叉比对：

| Channel | octos 已实现 | 测试已覆盖 | 缺口 |
|---------|-------------|-----------|------|
| Discord | `send_embed`, `react_to_message/remove_reaction`, `delete_message` | dedup/白名单/重连/分片/Embed/Reaction/delete | ✅ **已全部覆盖** |
| Matrix | `health_check`, `send_typing`, `finish_stream` | 会话/配置/LLM/abort/profile/dedup/health_check/typing | ✅ **已全部覆盖** |
| WhatsApp | `send_typing` | 基础命令/去重/白名单/重连 | typing ❌ |
| Slack | `media_dir` | 基础命令/去重/白名单 | 媒体处理 ❌ |
| API | task/approval 端点 | WS RPC 基本功能 | task/approval ❌ |

### 3.4 优先级原则

排序依据：**测试缺口带来的风险 × 用户受影响的概率**

- **高优先级**：功能可能有缺陷、影响实际用户体验、当前完全无覆盖或严重不足
- **中优先级**：有基本覆盖但缺少平台特有场景验证
- **低优先级**：已有充分覆盖，或仅影响小众功能

---

## 四、待办清单（按优先级排序）

### P0 — 阻塞问题跟踪

| # | 事项 | 涉及 Channel | 说明 |
|---|------|-------------|------|
| 1 | **session_delete_rx 阻塞（issue #1407）回归** | 所有无 `--api-port` 的 channel | octos bug：无 API channel 时消息无法分发到 LLM，需等待修复后全面回归验证 |
| 2 | **Email LLM context 膨胀** | Email | 同一发件人后续邮件 bot 不再回复（LLM 400 错误），需 octos 修复 session compaction |
| 3 | **Mock Server 间歇崩溃** | 所有 WS 通道 | health check 连续失败 → pytest.skip，分析 mock server 不稳定性 |
| 4 | **Telegram profile routing 缺失** | Telegram | `test_soul_per_profile` 正确 skip，等待 octos 实现 chat_id → profile_id 路由 |

### P1 — 功能缺口（octos 代码已有实现，测试未覆盖）

| # | 事项 | 涉及 Channel | 说明 | 预估 | 状态 |
|---|------|-------------|------|:----:|:----:|
| 5 | **Discord Embed + Reaction** | Discord | `send_embed`、`react_to_message`、`remove_reaction`、`delete_message` | 1 天 | ✅ |
| 6 | **API Channel task 端点** | API | 代码中有 `GET /sessions/{id}/tasks`、`POST /tasks/{id}/cancel`、`POST /tasks/{id}/restart-from-node`；无 approval 端点。现有 38 用例已覆盖核心路径，task 端点为简单 REST 操作，测试价值有限 | — | ❌ 无需测试 |

### P2 — 中优先级

| # | 事项 | 涉及 Channel | 说明 | 预估 | 状态 |
|---|------|-------------|------|:----:|:----:|
| 7 | **Matrix health_check + typing** | Matrix | `health_check()` 和 `send_typing()` 在 octos 中已实现，未测试 | 0.5 天 | ✅ |
| 8 | **跨 channel 并发** | 跨通道 | 同一用户从 telegram+discord 同时发消息，验证 session 隔离 | 1 天 | ✅ |
| 9 | **Email 补充测试用例** | Email | 用真实邮箱补充命令测试（/new、/help、/clear、/s） | 1 天 | ✅ |
| 10 | **WhatsApp 媒体类型扩展** | WhatsApp | 视频消息、文档消息、location 消息注入和回复验证 | 1 天 | ✅ |

### P3 — 低优先级

| # | 事项 | 说明 | 预估 | 状态 |
|---|------|------|:----:|:----:|
| 11 | **Discord delete_message** | octos 已实现 delete_message，当前无测试 | 0.5 天 | ✅ |
| 12 | **Slack 媒体处理** | octos 有 media_dir 支持，未测试 | 0.5 天 | ✅ |
| 13 | **WhatsApp typing** | octos 有 send_typing，未测试 | 0.5 天 | ✅ |
| 14 | **Feishu Webhook 模式** | Feishu 支持 WS 和 Webhook 两种模式，现有只测了 WS | 1-2 天 |
| 15 | **gateway 重启后会话恢复** | `test_run.py` 支持中途重启 gateway → 验证历史会话仍可读 | 需框架改造 |
| 16 | **各 channel 媒体发送** | Telegram 发图片/音频/文档、Discord 发附件等 | 1-2 天 |

---

## 五、各 Channel 详细缺口分析

### 5.1 Telegram（54 用例 — 过剩，不建议再扩展）

| 覆盖度 | 功能 | 是否已测 |
|:------:|------|:--------:|
| ✅ | 会话管理命令 | 完整覆盖 |
| ✅ | 配置命令 | 完整覆盖 |
| ✅ | LLM 连通性 | 完整覆盖 |
| ✅ | 多语言 abort | 完整覆盖 |
| ✅ | 多用户隔离 | 完整覆盖 |
| ✅ | 并发限制 | 完整覆盖 |
| ✅ | 消息分片 | 完整覆盖 |
| ✅ | 10MB 限制 | 完整覆盖 |
| ✅ | 流式编辑 | 完整覆盖 |
| ✅ | Inline Keyboard | 已测 |
| ✅ | Mention Gating | 已测 |
| ✅ | Typing Indicator | 已测 |
| ✅ | HTML Fallback | 已测 |
| ✅ | 白名单过滤 | 已测 |
| ✅ | 消息去重 | 已测 |
| ✅ | 图片发送 | 已测 |
| ⬜ | 媒体消息（语音/视频/文档发送） | **未测** — 价值低 |
| ⬜ | WS 断线重连 | **未测** — Telegram 使用长轮询，无 WS |

### 5.2 Slack / Matrix / Discord（41-51 用例 — 较充分）

核心缺口：
- Discord：~~Embed 消息、Emoji Reaction（P1）、delete_message（P3）~~ ✅ 已全部覆盖
- Matrix：~~Typing Indicator、health_check（P2）~~ ✅ 已全部覆盖
- Slack：Thread Reply、Bot 自消息过滤、媒体处理（P3）

### 5.3 WeCom Bot（20 用例 — 较充分）

| 覆盖度 | 功能 | 状态 |
|:------:|------|:----:|
| ✅ | WS 连接/认证 | 已测 |
| ✅ | 会话管理 | 已测 |
| ✅ | 配置命令 | 已测 |
| ✅ | LLM 消息 + 流式 | 已测 |
| ✅ | 中断 /abort | 已测 |
| ✅ | 多用户隔离 | 已测 |
| ✅ | 消息去重 | 已测 |
| ✅ | 白名单过滤 | 已测 |
| ✅ | WS 断线重连 | 已测 |

### 5.4 WeCom（16 用例 — 较充分）

| 覆盖度 | 功能 | 状态 |
|:------:|------|:----:|
| ✅ | URL 验证 | 已测 |
| ✅ | 加密回调 | 已测 |
| ✅ | 会话管理 | 已测 |
| ✅ | 配置命令 | 已测 |
| ✅ | LLM 消息 | 已测 |
| ✅ | 多用户隔离 | 已测 |
| ✅ | 消息去重 | 已测 |
| ✅ | 白名单过滤 | 已测 |
| ⬜ | Token 刷新 | 价值低 |
| ⬜ | 媒体上传发送 | 价值低 |

### 5.5 LINE（28 用例 — 命令齐全，媒体/提及已补）

| 覆盖度 | 功能 | 状态 |
|:------:|------|:----:|
| ✅ | 会话管理命令 | 已测 |
| ✅ | 配置命令 | 已测 |
| ✅ | LLM 消息 | 已测 |
| ✅ | 中断 /abort | 已测 |
| ✅ | 多用户隔离 | 已测 |
| ✅ | 消息去重 | 已测 |
| ✅ | 白名单过滤 | 已测 |
| ✅ | 媒体消息（Image/Audio/Video/File） | 已测 |
| ✅ | Sticker/Location 消息 | 已测 |
| ✅ | @提及群组门控 | 已测 |
| ⬜ | Webhook 签名验证 | 内部细节，不列入黑盒 |
| ⬜ | 消息分片（5000 字符） | **未测** |

### 5.6 QQ Bot（35 用例 — 较充分）

| 覆盖度 | 功能 | 状态 |
|:------:|------|:----:|
| ✅ | 群消息会话管理 | 已测 |
| ✅ | 配置命令 | 已测 |
| ✅ | LLM 消息 | 已测 |
| ✅ | 中断 /abort | 已测 |
| ✅ | 多用户隔离 | 已测 |
| ✅ | 消息去重 | 已测 |
| ✅ | 白名单过滤 | 已测 |
| ✅ | C2C 会话管理命令 | 已测 |
| ✅ | C2C 配置命令 | 已测 |
| ✅ | WS 断线重连 | 已测 |
| ✅ | 健康检查 | 已测 |
| ✅ | 消息分片（4000 字符） | 已测（QQ Bot v2 限制） |

### 5.7 Twilio（24 用例 — 较充分）

| 覆盖度 | 功能 | 状态 |
|:------:|------|:----:|
| ✅ | 会话管理命令 | 已测 |
| ✅ | 配置命令 | 已测 |
| ✅ | LLM 消息 | 已测 |
| ✅ | 中断 /abort | 已测 |
| ✅ | 多用户隔离 | 已测 |
| ✅ | 消息去重 | 已测 |
| ✅ | 白名单过滤 | 已测 |
| ✅ | 消息分片（1600+ 字符） | 已测 |
| ✅ | 健康检查 | 已测 |
| ⬜ | MMS 媒体消息 | 价值低 |

### 5.8 WhatsApp（28 用例 — 较充分）

| 覆盖度 | 功能 | 状态 |
|:------:|------|:----:|
| ✅ | 会话管理命令 | 已测 |
| ✅ | 配置命令 | 已测 |
| ✅ | LLM 消息 | 已测 |
| ✅ | 中断 /abort | 已测 |
| ✅ | 多用户隔离 | 已测 |
| ✅ | 消息去重 | 已测 |
| ✅ | 白名单过滤 | 已测 |
| ✅ | WS 断线重连 | 已测 |
| ⬜ | 媒体类型（视频/文档） | **未测** → P3 |
| ⬜ | Typing Indicator | **未测** → 价值低 |

### 5.9 API Channel（38 用例 — 较充分）

| 覆盖度 | 功能 | 状态 |
|:------:|------|:----:|
| ✅ | WS 连接/hello | 已测 |
| ✅ | Session list/open/delete | 已测 |
| ✅ | Turn/start/interrupt | 已测 |
| ✅ | System status/health | 已测 |
| ✅ | Messages/page | 已测 |
| ✅ | Content/list | 已测 |
| ✅ | Session/snapshot/status.get/title.set | 已测 |
| ~~⬜~~ | ~~POST /chat SSE 流式响应~~ | N/A — `POST /api/chat` 已废弃，WS RPC 8.10 已覆盖 |
| ⬜ | Task list/cancel | **未测** → P3 |
| ⬜ | Approval list/respond | **未测** → P3 |
| ⬜ | Session files/list | **未测** → P3 |

### 5.10 Email（3 用例 — 较薄弱）

Email 是唯一使用**真实邮箱**测试的 channel（无 Mock），当前问题：
1. **LLM context 膨胀**：同一发件人持续交互 → context 超限 → bot 400 错误无法回复
2. **QQ 邮箱自发自收 UNSEEN 失效**：QQ 邮箱将自发邮件自动标记已读，无法检测新邮件

→ 方向：保留真实邮箱测试方式，补充更多测试场景（命令测试、多用户隔离、消息分片等）。
   LLM context 膨胀问题需 octos 修复 session compaction。

---

## 六、建议执行顺序

### ✅ 本周已完成
1. **Discord Embed + Reaction + delete_message** — 增强 mock，4 个新测试用例
2. **Matrix health_check + typing** — 增强 mock，3 个新测试用例
3. **WhatsApp typing + 媒体扩展** — 增强 mock，6 个新测试用例
4. **Email 补充测试用例** — 新增 4 个命令测试（/new、/help、/clear、/s）
5. **Slack 媒体处理** — 增强 mock（文件附件注入），2 个新测试用例
6. **API task 评估** — 端点简单且无 approval 端点，决定无需额外测试
7. **跨 channel 并发测试** — 新增独立测试文件 `test_cross_channel.py`，整合 tg+dc mock + 合并 gateway

### 仅剩待办
- **Feishu Webhook 模式** — P3，需要 mock 增强以支持 Webhook 模式
- **gateway 重启后会话恢复** — P3，需 test_run.py 框架改造
- **Telegram profile routing** — 阻塞，等待 octos 实现 chat_id → profile_id 路由

### 长期
8. **Slack 媒体处理** — 低优先级按需投入
9. **Feishu Webhook 模式 / gateway 重启恢复** — 需框架改造
10. **Telegram profile routing** — 等待 octos 实现后启用被 skip 的测试

---

## 七、黑盒边界说明

以下属于**内部实现细节**，无法通过"发消息 → 看回复"验证，**不列入本 roadmap**：

- AES-256-CBC 加解密过程、HMAC-SHA256 签名验证
- Token TTL 刷新逻辑、签名有效期计算
- WebSocket 帧协议细节、心跳包格式

这些应归属于 octos 自身的单元测试 / 集成测试范畴。

---

## 八、已知阻塞（黑盒视角）

| 问题 | 外部可见行为 | 状态 |
|------|-------------|:----:|
| `session_delete_rx` 阻塞（issue #1407） | 无 `--api-port` 时 channel 消息无法分发到 LLM，所有不带 api 的 gateway 消息阻塞 | **octos 功能缺陷**，等待修复后全面回归 |
| Telegram `test_soul_per_profile` / `test_queue_mode_per_profile` 被 skip | 不同 chat_id 消息被路由到同一 profile，会话未隔离 | **octos 功能缺陷**，测试正确 skip，等待修复后启用 |
| Email 上下文膨胀 | 同一发件人后续邮件 bot 不再回复（LLM 400 错误） | **octos 功能缺陷**，见 `docs/email_context_issue.md` |
| Mock Server 间歇崩溃导致后半段 skip | health check 连续失败 → pytest.skip | **测试框架稳定性问题**，见 `TEST_SKIP_ANALYSIS.md` |
| Email QQ 邮箱自发自收 IMAP UNSEEN 失效 | QQ 邮箱将自发自收邮件自动标记已读 | **QQ 邮箱行为限制**，建议换双邮箱测试 |
