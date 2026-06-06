# Octos Channel 测试 Roadmap

> 黑盒测试视角：仅通过外部消息输入 / Bot 回复输出验证 octos 功能。

---

## 一、当前完成情况

通过 `Mock Server ↔ octos gateway ↔ 断言回复` 的黑盒方式，**14 个 channel 已有测试文件**。

| Channel | 用例数 | 黑盒覆盖的外部功能 | 测试方式 |
|---------|:------:|------------------|----------|
| Telegram | 54 | `/new`, `/s`, `/back`, `/delete`, `/soul`, `/queue`, `/status`, `/reset`, `/adaptive`, `/abort`, `/clear`, LLM 消息、多用户隔离、白名单过滤、流式编辑、消息分片、10MB 限制、Inline Keyboard、Typing Indicator、Mention Gating、HTML Fallback、图片发送 | Mock HTTP API |
| Slack | 51 | 会话管理命令、配置命令、LLM、中断、多用户隔离、并发限制、去重、白名单过滤 | Mock HTTP + WS |
| Matrix | 44 | 同上一批命令 + profile 路由 + 去重 + 白名单过滤 | Mock HTTP |
| Discord | 41 | 同上一批命令 + 多频道隔离 + 去重 + 白名单过滤 + WS 断线重连 | Mock HTTP + WS Gateway |
| Feishu | 38 | 同上一批命令 + 流式编辑 + 10MB 限制 + 消息去重 + 白名单过滤 | Mock Webhook |
| WeChat | 37 | 同上一批命令 + 消息分片 + 10MB 限制 + 去重 + WS 断线重连 | Mock WS Bridge |
| LINE | 28 | 会话管理命令、配置命令、LLM、中断、多用户隔离、消息去重、白名单过滤、媒体消息（Image/Audio/Video/File/Location/Sticker）、@提及群组门控 | Mock Webhook |
| QQ Bot | 29 | 群消息、C2C 私聊、会话管理命令、配置命令、LLM、中断、多用户隔离、消息去重、白名单过滤、C2C 会话/配置命令、消息分片、WS 断线重连 | Mock WS Gateway |
| WhatsApp | 28 | 基础命令 + 多用户隔离 + 去重 + 白名单过滤 + WS 断线重连 | Mock WS Bridge |
| Twilio | 24 | SMS 消息、会话管理命令、配置命令、LLM、中断、多用户隔离、消息去重、白名单过滤、消息分片 | Mock Webhook |
| WeCom Bot | 20 | WS 连接、认证、消息收发、会话管理命令、配置命令、LLM、流式回复、多用户隔离、去重、白名单过滤、WS 断线重连 | Mock WS |
| WeCom | 16 | URL 验证、加密回调、消息发送、会话管理命令、配置命令、LLM、多用户隔离、去重、白名单过滤 | Mock REST + Webhook |
| Email | 3 | SMTP 发邮件 → IMAP 收回复（真实邮箱） | 真实 IMAP/SMTP |
| **API** | **19** | WS 连接/hello、session/list、session/open+turn/start、session/delete、session/snapshot、session/messages_page、session/status.get、session/title.set、content/list、turn/interrupt、system/status.get、/health、/api/version、/metrics、认证、Dashboard | WS JSON-RPC + REST |

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

---

## 三、现状分析与规划思路

### 3.1 各 Channel 测试充分度评估

根据代码量、用户覆盖、功能复杂度综合打分：

| 层级 | Channel | 当前用例数 | 评估 | 说明 |
|:----:|---------|:----------:|:----:|------|
| S | Telegram | 54 | **过剩** | 测试数量已远超实际需要，包含大量边缘/高级特性测试，回报递减 |
| A | Slack / Matrix / Discord | 40-51 | **充分** | 核心路径全覆盖，剩余可测功能价值不高 |
| B | Feishu / WeChat / WhatsApp | 28-38 | **较充分** | 基本功能齐全，已补充 WS 重连 |
| C | QQ Bot / Twilio / LINE | 24-29 | **基本覆盖** | 核心命令全，已补充 C2C、分片、媒体、WS 重连 |
| D | WeCom Bot / WeCom | 16-20 | **较充分** | P1 补充去重+白名单后覆盖度提升 |
| E | Email | 3 | **严重不足且部分失效** | 仅 3 个用例，且 LLM context 膨胀/QQ 邮箱问题导致不稳定 |
| F | API | 19 | **测试方式不同** | 非消息 channel，已有 CLI/WS JSON-RPC 测试，SSE 已废弃由 WS RPC 替代 |

### 3.2 关键问题识别

1. **Email 测试处于半瘫痪状态**：LLM context 膨胀导致后续邮件 bot 不回复；QQ 邮箱自发自收 UNSEEN 失效。这种"用真实邮箱实测"的方式不可靠。
2. ~~**WeCom / WeCom Bot 覆盖率低**~~（P1 已补齐去重+白名单）
3. ~~**API Channel POST /chat SSE 已废弃**~~（架构变更后由 WS RPC 替代，`8.10` 已覆盖）
4. ~~**WebSocket 断线重连零覆盖**~~（P2 已覆盖 Discord/WeChat/WhatsApp/WeCom Bot/QQ Bot）
5. **高级特性测试价值有限**：Telegram 已有 54 个用例，再增加按钮/键盘交互等场景，投入产出比很低。

### 3.3 优先级原则

排序依据：**测试缺口带来的风险 × 用户受影响的概率**

- **高优先级**：功能可能有缺陷、影响实际用户体验、当前完全无覆盖或严重不足
- **中优先级**：有基本覆盖但缺少平台特有场景验证
- **低优先级**：已有充分覆盖，或仅影响小众功能

---

## 四、待办清单（按优先级排序）

### P0 — 修复已知问题（当前阻塞测试可靠性）

| # | 事项 | 涉及 Channel | 说明 |
|---|------|-------------|------|
| 1 | **Email LLM context 膨胀** | Email | 同一发件人后续邮件 bot 不再回复（LLM 400 错误），分析根本原因并修复 |
| 2 | **Mock Server 间歇崩溃** | 所有 WS 通道 | health check 连续失败 → pytest.skip，分析 mock server 不稳定性（见 `TEST_SKIP_ANALYSIS.md`） |

### P1 ✅ 已完成
| # | 事项 | 涉及 Channel | 说明 |
|---|------|-------------|:----:|
| ~~3~~ | **WeCom Bot 补齐去重+白名单** ✅ | ~~WeCom Bot~~ | |
| ~~4~~ | **WeCom 补齐去重+白名单** ✅ | ~~WeCom~~ | |
| ~~5~~ | **QQ Bot C2C 会话管理命令** ✅ | ~~QQ Bot~~ | |
| ~~6~~ | **Twilio 分片消息测试** ✅ | ~~Twilio~~ | |

### P2 ✅ 已完成
| # | 事项 | 涉及 Channel | 说明 |
|---|------|-------------|:----:|
| ~~7~~ | **WebSocket 断线重连** ✅ | ~~跨通道~~ | |
| ~~8~~ | **LINE 补齐媒体/提及测试** ✅ | ~~LINE~~ | |
| ~~9~~ | **API Channel POST /chat SSE** N/A | ~~API~~ | |

### P3 — 中优先级（当前待办）

| # | 事项 | 涉及 Channel | 预估工作量 |
|---|------|-------------|:----------:|
| 10 | **Email IMAP/SMTP Mock 轻量化** | 构建简化的 Mock IMAP 服务器，避免依赖真实邮箱；至少覆盖收件→回复路径 | Email | 2 天 |
| 11 | **跨 channel 并发** | 同一用户从 telegram+discord 同时发消息，验证 session 隔离 | 跨通道 | 1 天 |
| 12 | **API Channel 扩展 task/approval** | task/list、task/cancel、approval/list、approval/respond | API | 2 天 |
| 13 | **WhatsApp 媒体类型扩展** | 视频消息、文档消息、location 消息的注入和回复验证 | WhatsApp | 1 天 |

### P4 — 低优先级（可有可无）

| # | 事项 | 说明 | 预估工作量 |
|---|------|------|:----------:|
| 14 | **Telegram Inline Keyboard 发送** | 当前已有 callback query 测试，补充 bot 发送 keyboard 的验证 | 0.5 天 |
| 15 | **Discord Embed + Reaction** | Embed 消息格式验证 + Emoji Reaction 事件处理 | 1 天 |
| 16 | **Feishu Webhook 模式测试** | Feishu 支持 WS 和 Webhook 两种模式，现有测试只测了 WS | 1-2 天 |
| 17 | **各 channel 媒体发送** | Telegram 发图片/音频/文档（已有 send_photo 测试）、Discord 发附件等 | 1-2 天 |
| 18 | **gateway 重启后会话恢复** | `test_run.py` 支持中途重启 gateway → 验证历史会话仍可读 | 需框架改造 |

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

### 5.2 Slack / Matrix / Discord（40-51 用例 — 较充分）

核心缺口：
- Discord：Embed 消息、Emoji Reaction（P4）
- Slack：Thread Reply、Bot 自消息过滤（P4）
- Matrix：Typing Indicator、健康检查（P4）
- ~~**所有 WS 通道：断线重连测试（P2）**~~ ✅ 已覆盖

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

### 5.6 QQ Bot（22 用例 — 命令齐全，C2C 缺命令测试）

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
| ✅ | 消息分片（4000 字符） | 已测（QQ Bot v2 限制） |
| ⬜ | WS 断线重连 | **未测** → P2 |

### 5.7 Twilio（21 用例 — 命令齐全，缺分片测试）

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
| ⬜ | MMS 媒体消息 | 价值低 |

### 5.8 WhatsApp（28 用例 — 较充分，重连已补）

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

### 5.9 API Channel（19 用例 — WS RPC 全覆盖，SSE 已废弃）

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

### 5.10 Email（3 用例 — 处于半瘫痪状态）

Email 是唯一使用**真实邮箱**测试的 channel，当前问题：
1. **LLM context 膨胀**：同一发件人持续交互 → context 超限 → bot 400 错误无法回复
2. **QQ 邮箱自发自收 UNSEEN 失效**：QQ 邮箱将自发邮件自动标记已读，无法检测新邮件
3. **无 Mock 替代方案**：所有其他 channel 都有 Mock Server，Email 没有

→ 建议方向：修复 LLM context 膨胀问题（属于 octos 的 bug），同时保留真实邮箱测试方式。

---

## 六、建议执行顺序

### P0 待处理
1. Email LLM context 膨胀根因分析
2. Mock Server 间歇崩溃分析

### P1 ✅ 已完成（所有 4 项）
3. ✅ ~~WeCom Bot 补齐去重+白名单~~
4. ✅ ~~WeCom 补齐去重+白名单~~
5. ✅ ~~QQ Bot C2C 补充命令测试~~
6. ✅ ~~Twilio 消息分片测试~~

### P2 ✅ 已完成（所有 3 项）
7. ✅ ~~WS 断线重连框架设计 + 通用辅助函数~~
8. ✅ ~~LINE 媒体/提及/贴图测试~~
9. ~~API Channel POST /chat SSE~~ N/A

### 当前待办（P3 + P4）
10. **Email Mock 轻量化**
11. **跨 channel 并发测试**
12. **API Channel task/approval 扩展**
13. **WhatsApp 媒体类型扩展**
14-18. 各 channel 高级特性按需补充（P4 项）

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
| Telegram `test_soul_per_profile` / `test_queue_mode_per_profile` 被 skip | 不同 chat_id 消息被路由到同一 profile，会话未隔离 | **octos 功能缺陷**，测试正确 skip，等待修复后启用 |
| Email 上下文膨胀 | 同一发件人后续邮件 bot 不再回复（LLM 400 错误） | **octos 功能缺陷**，见 `docs/email_context_issue.md` |
| Mock Server 间歇崩溃导致后半段 skip | health check 连续失败 → pytest.skip | **测试框架稳定性问题**，见 `TEST_SKIP_ANALYSIS.md` |
| Email QQ 邮箱自发自收 IMAP UNSEEN 失效 | QQ 邮箱将自发自收邮件自动标记已读 | **QQ 邮箱行为限制**，非 octos 问题，建议换双邮箱测试 |
