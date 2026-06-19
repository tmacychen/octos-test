# Octos Channel 测试 Roadmap

> 黑盒测试视角：仅通过外部消息输入 / Bot 回复输出验证 octos 功能。

---

## 一、当前完成情况

通过 `Mock Server ↔ octos gateway ↔ 断言回复` 的黑盒方式，**全部 15 个 channel 已有测试文件**（对应 octos 所有 channel 实现）。

| Channel | 用例数 | 黑盒覆盖的外部功能 | 测试方式 |
|---------|:------:|------------------|----------|
| Telegram | 54 | `/new`, `/s`, `/back`, `/delete`, `/soul`, `/queue`, `/status`, `/reset`, `/adaptive`, `/abort`, `/clear`, LLM 消息、多用户隔离、白名单过滤、流式编辑、消息分片、10MB 限制、Inline Keyboard、Typing Indicator、Mention Gating、HTML Fallback、图片发送、消息去重 | Mock HTTP API |
| Slack | 56 | 会话管理命令、配置命令、LLM、中断、多用户隔离、并发限制、去重、白名单过滤 | Mock HTTP + WS |
| Matrix | 50 | 会话管理命令、配置命令、LLM、中断、多用户隔离、profile 路由、去重、白名单过滤 | Mock HTTP + Appservice |
| Discord | 41 | 会话管理命令、配置命令、LLM、中断、多频道隔离、并发限制、去重、白名单过滤、WS 断线重连、消息分片 | Mock HTTP + WS Gateway |
| Feishu | 38 | 会话管理命令、配置命令、LLM、中断、多用户隔离、流式编辑、10MB 限制、消息去重、白名单过滤 | Mock WS |
| WeChat | 41 | 会话管理命令、配置命令、LLM、中断、多用户隔离、并发限制、消息分片、10MB 限制、去重、WS 断线重连 | Mock WS Bridge |
| WhatsApp | 33 | 会话管理命令、配置命令、LLM、中断、多用户隔离、去重、白名单过滤、WS 断线重连 | Mock WS Bridge |
| LINE | 29 | 会话管理命令、配置命令、LLM、中断、多用户隔离、消息去重、白名单过滤、媒体消息（Image/Audio/Video/File/Location/Sticker）、@提及群组门控、Typing Indicator | Mock Webhook |
| QQ Bot | 36 | 群消息、C2C 私聊、会话管理命令、配置命令、LLM、中断、多用户隔离、消息去重、白名单过滤、消息分片、WS 断线重连、健康检查 | Mock WS Gateway |
| Twilio | 24 | SMS 消息、会话管理命令、配置命令、LLM、中断、多用户隔离、消息去重、白名单过滤、消息分片、健康检查 | Mock Webhook |
| WeCom Bot | 20 | WS 连接、认证、消息收发、会话管理命令、配置命令、LLM、流式编辑、多用户隔离、去重、白名单过滤、WS 断线重连、消息分片 | Mock WS |
| WeCom | 16 | URL 验证、加密回调、消息发送、会话管理命令、配置命令、LLM、多用户隔离、去重、白名单过滤、健康检查 | Mock REST + Webhook |
| Email | 3 | SMTP 发邮件 → IMAP 收回复（真实邮箱） | 真实 IMAP/SMTP |
| **Serve / API** | **92** | WS RPC 45/51 methods 覆盖：client_hello、capabilities、session CRUD、turn、profile、auth、tool/content、notification、错误路径 + REST（health/version/metrics/Dashboard/认证） | WS JSON-RPC + REST |
| **octos-tui** | **1** | PTY smoke：--mode mock 启动后捕获渲染文字，断言 M8 + prototype | PTY 黑盒 |

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
- **跨 channel 会话隔离**：同一 gateway 上 telegram + discord 同时发消息，各 channel session 独立隔离，互不干扰
- **Serve WS RPC**：45/51 个 command methods 测试覆盖（新增 73 个测试），包括 approval/permission/diff/task/agent/loop/review/router/content/auth 等
- **octos-tui PTY smoke**：binary 启动 → ratatui 渲染 → 断言 mock snapshot 预填文字

---

## 三、现状分析与规划思路

### 3.1 各 Channel 测试充分度评估

**所有 15 个 octos channel 均已覆盖**，按充分度分层：

| 层级 | Channel | 当前用例数 | 评估 | 说明 |
|:----:|---------|:----------:|:----:|------|
| S | Telegram | 54 | **充分** | 包含边缘/高级特性测试（Keyboard/Typing/Mention/图片发送等） |
| A | Slack / Matrix / Discord | 41-56 | **充分** | 核心路径全覆盖；DE 高；少量缺口（Slack Thread/媒体） |
| B | Feishu / WeChat / WhatsApp / LINE / QQ Bot | 29-41 | **较充分** | 基本功能齐全；WhatsApp 全 LLM 测试待改善 |
| C | Twilio / WeCom Bot / WeCom | 16-24 | **充分** | 核心命令全，去重+白名单已补 |
| D | Serve / API | 92 | **充分** | 45/51 command methods (88%) 覆盖，需 LLM 的 task/agent 部分未覆盖 |
| E | octos-tui | 1 | **基础** | PTY smoke 验证二进制启动和渲染；protocol mode PTY 有阻塞问题 |
| F | Email | 3 | **较薄弱** | 仅手动测试，可补充更多真实邮箱测试用例 |

### 3.2 关键问题识别

1. **Email 测试较薄弱**：仅 3 个用例，LLM context 膨胀 / QQ 邮箱自发自收 UNSEEN 失效。保留真实邮箱测试，补充更多场景。
2. **session_delete_rx 阻塞（issue #1407）**：✅ **已修复** — 代码已改为 `try_recv()` 非阻塞接收，重编 binary 后实际验证无 `--api-port` 时消息正常分发到 LLM。
3. **Telegram profile routing 缺失**：不同 chat_id 消息被路由到同一 profile，`test_soul_per_profile` 正确 skip。等待 octos 实现。
4. ~~**Discord / Matrix 部分高级特性未覆盖**~~ ✅ 已全覆盖：Embed、Reaction、health_check、Typing Indicator 均已补齐。
5. **LLM 测试大量 false positive** — 8b 模型 context 131K 累积后超限，非 LLM 测试全部通过（约 120 个），LLM 测试约 200 个因回复慢 / 超限失败。需 octos session compaction 或换更大 context 模型。

### 3.3 octos 代码 vs 测试覆盖交叉分析

从 octos main 分支代码中提取各 channel 功能，与测试覆盖交叉比对：

| Channel | octos 已实现 | 测试已覆盖 | 缺口 |
|---------|-------------|-----------|------|
| Discord | `send_embed`, `react_to_message/remove_reaction`, `delete_message` | dedup/白名单/重连/分片/Embed/Reaction/delete | ✅ **已全部覆盖** |
| Matrix | `health_check`, `send_typing`, `finish_stream` | 会话/配置/LLM/abort/profile/dedup/health_check/typing | ✅ **已全部覆盖** |
| WhatsApp | `send_typing` | 基础命令/去重/白名单/重连 | typing ❌ |
| Slack | `media_dir` | 基础命令/去重/白名单 | 媒体处理 ❌ |
| Serve | 51 command methods | 45/51 methods (88%) | task/agent 6 个 ❌（需 LLM turn）|

### 3.4 优先级原则

排序依据：**测试缺口带来的风险 × 用户受影响的概率**

- **高优先级**：功能可能有缺陷、影响实际用户体验、当前完全无覆盖或严重不足
- **中优先级**：有基本覆盖但缺少平台特有场景验证
- **低优先级**：已有充分覆盖，或仅影响小众功能

---

## 四、待办清单（按优先级排序）

### P0 — 阻塞问题跟踪

| # | 事项 | 涉及 | 说明 | 状态 |
|---|------|------|------|:----:|
| 1 | **session_delete_rx 阻塞（issue #1407）** | 所有无 `--api-port` 的 channel | 代码已改为 `try_recv()` 非阻塞；重编 14 features binary 后 matrix/slack/feishu 均正常分发消息到 LLM | ✅ **已修复** |
| 2 | **Email LLM context 膨胀** | Email | 同一发件人后续邮件 bot 不再回复（LLM 400 错误），需 octos 修复 session compaction | ❌ 阻塞 |
| 3 | **Telegram profile routing 缺失** | Telegram | `test_soul_per_profile` 正确 skip，等待 octos 实现 chat_id → profile_id 路由 | ❌ 阻塞 |
| 4 | **LLM 测试 false positive** | 所有 channel | 8b 模型 131K context 累积后超限，~200 个 LLM 测试假性失败。非 LLM 测试全部通过 | ❌ 待 octos 修复 |

### P1 — 功能缺口

| # | 事项 | 涉及 | 说明 | 预估 | 状态 |
|---|------|------|------|:----:|:----:|
| 5 | **serve 6 个需 LLM method 升级** | serve | approval/respond、permission/profile.*、task/*、agent — 当前验证 error shape | 1 天 | ✅ 已完成（5 个升真实调用，6 个修正断言）|
| 6 | **serve --stdio 传输** | serve | 当前只测了 WS，补 stdio mode 黑盒 | 1 天 | ✅ 已完成（6 个测试，覆盖连通性/capabilities/system_status/session/session_open/auth）|
| 7 | **serve 通知流验证** | serve | 35 个 notification 类型只有 session/open 被测到 | 1-2 天 | ✅ 已完成（新增 4 个：turn/started/turn/completed/turn/error/agent/updated）|
| 8 | **octos-tui 协议端到端** | tui | --mode protocol PTY 有阻塞问题（TUI bootstrap 阶段不产生渲染输出），需 TUI 侧配合 | — | ❌ 暂不推进 |

### P2 — 中优先级

| # | 事项 | 涉及 | 说明 | 预估 |
|---|------|------|------|:----:|
| 9 | Feishu Webhook 模式 | Feishu | 当前只测了 WS，需 mock 增强 | 1-2 天 |
| 10 | WhatsApp reconnect + 媒体 | WhatsApp | WS reconnect 卡住；媒体类型未测 | 1 天 |
| 11 | LINE 消息分片 | LINE | 5000 字符分片未测 | 0.5 天 |
| 12 | `test_run.py all` 扩到 serve 92 个测试 | 框架 | 当前 all 不包含新 serve 测试 | 0.5 天 |
| 13 | Email 补充测试用例回归 | Email | 命令测试回归验证 | 0.5 天 |

### P3 — 低优先级

| # | 事项 | 涉及 | 说明 | 预估 |
|---|------|------|------|:----:|
| 14 | gateway 重启后会话恢复 | 框架 | 需 test_run.py 框架改造 | 需框架改造 |
| 15 | 各 channel 媒体发送 | Telegram/Discord | 发图片/音频/文档等 | 1-2 天 |
| 16 | Slack Thread Reply / 媒体处理 | Slack | 已测 dedup 和 broadcast，Thread 链路未测 | 0.5 天 |
| 17 | serve 并发测试 | serve | 多 WS 连接同时操作 | 1 天 |
| 18 | serve SSE 废弃端点说明更新 | serve | run_serve_tests.py help 提及旧 REST+SSE | 0.5 天 |

---

## 五、各 Channel 详细缺口分析

（保持不变 — 未测缺口已在 P2/P3 中跟踪）

---

## 六、建议执行顺序

### ✅ 本周已完成（2026-06-12 ~ 2026-06-14）

1. **octos binary 重编 (14 features)** — 修复缺 features 导致 channel 跳过问题
2. **mock_slack.py _inject 缺 broadcast** — 补 `_broadcast_to_websockets`，envelope 推到 octos WS
3. **runner_line.py event_data 缺默认值** — 修 LINE inject 崩溃
4. **test_run.py qq-bot app_id 字段** — 适配新版 octos 配置格式
5. **max_history 50→5 + model 70b→8b** — 控制 LLM context 累积
6. **octos-tui 集成** — PTY smoke 测试，`--test tui` 入口
7. **serve 黑盒扩展 19→92 个测试** — 新增 73 个 WS RPC 合约测试
8. **5 个 method 升真实调用** — permission/profile.list、content delete/bulk_delete、profile/llm/upsert、session/status/read
9. **P0 排查** — session_delete_rx 已修复确认、Mock Server 未复现、profile routing 阻塞确认

### 仅剩待办
- ~~**serve --stdio 传输** — P1~~ ✅ 已完成
- ~~**serve 通知流验证** — P1~~ ✅ 已完成
- **Feishu Webhook 模式** — P2
- **WhatsApp reconnect** — P2
- **LINE 消息分片** — P2
- **Telegram profile routing** — 阻塞，等待 octos 实现

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
| `session_delete_rx` 阻塞（issue #1407） | 无 `--api-port` 时 channel 消息无法分发到 LLM | ✅ **已修复**（代码 `try_recv()` + 实测验证）|
| Telegram `test_soul_per_profile` / `test_queue_mode_per_profile` 被 skip | 不同 chat_id 消息被路由到同一 profile，会话未隔离 | **octos 功能缺陷**，测试正确 skip，等待修复后启用 |
| Email 上下文膨胀 | 同一发件人后续邮件 bot 不再回复（LLM 400 错误） | **octos 功能缺陷**，需 session compaction |
| LLM 测试 false positive | 8b 模型 context 131K 累积后超限，~200 个 LLM 测试假性失败 | **测试框架问题**，非 LLM 测试全部通过 |
| Email QQ 邮箱自发自收 IMAP UNSEEN 失效 | QQ 邮箱将自发自收邮件自动标记已读 | **QQ 邮箱行为限制**，建议换双邮箱测试 |
