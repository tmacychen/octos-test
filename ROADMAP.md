# Octos Channel 测试 Roadmap

> 黑盒测试视角：仅通过外部消息输入 / Bot 回复输出验证 octos 功能。

---

## 一、当前完成情况

通过 `Mock Server ↔ octos gateway ↔ 断言回复` 的黑盒方式，**12 个 channel 已有测试文件**，**2 个完全空白**。

| Channel | 用例数 | 黑盒覆盖的外部功能 | 测试方式 |
|---------|:------:|------------------|----------|
| Telegram | 54 | `/new`, `/s`, `/back`, `/delete`, `/soul`, `/queue`, `/status`, `/reset`, `/adaptive`, `/abort`, `/clear`, LLM 消息、多用户隔离、白名单过滤 | Mock HTTP API |
| Slack | 48 | 同上一批命令 + 并发限制 | Mock HTTP + WS |
| Matrix | 42 | 同上一批命令 + profile 路由 | Mock HTTP |
| Discord | 38 | 同上一批命令 + 多频道隔离 | Mock HTTP + WS Gateway |
| Feishu | 36 | 同上一批命令 + 流式编辑 + 10MB 限制 + 消息去重 | Mock Webhook |
| WeChat | 36 | 同上一批命令 + 消息分片 + 10MB 限制 + 去重 | Mock WS Bridge |
| WhatsApp | 27 | 基础命令 + 多用户隔离 + 去重 + 白名单过滤 | Mock WS Bridge |
| WeCom Bot | 17 | WS 连接、认证、消息收发、会话管理命令、配置命令、LLM、流式回复、多用户隔离、去重 | Mock WS |
| LINE | 21 | 会话管理命令、配置命令、LLM、中断、多用户隔离、消息去重、白名单过滤 | Mock Webhook |
| WeCom | 14 | URL 验证、加密回调、消息发送、会话管理命令、配置命令、LLM、多用户隔离、去重 | Mock REST + Webhook |
| Email | 3 | SMTP 发邮件 → IMAP 收回复（真实邮箱） | 真实 IMAP/SMTP |
| **API** | **19** | WS 连接/hello、session/list、session/open+turn/start、session/delete、session/snapshot、session/messages_page、session/status.get、session/title.set、content/list、turn/interrupt、system/status.get、/health、/api/version、/metrics、认证、Dashboard | WS JSON-RPC + REST |
| **QQ Bot** | **0** | **完全无测试** | — |
| **Twilio** | **0** | **完全无测试** | — |

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
- **消息去重**：相同 message_id 只处理一次（Feishu, LINE）
- **白名单过滤**：allowed_senders 非空时，非白名单用户消息被忽略（Telegram, LINE）
- **API Channel**：WS 连接/hello、session/list、session/open+turn/start、session/delete、session/snapshot、session/messages_page、session/status.get、session/title.set、content/list、turn/interrupt、system/status.get（API）

---

## 三、待办清单（黑盒可验证）

### P0 — 高价值、工作量小

| # | 事项 | 黑盒验证方式 | 涉及 Channel | 状态 | 预估工作量 |
|---|------|-------------|-------------|:----:|:----------:|
| 1 | **`/clear` 命令** | 发送 `/clear` → 断言回复 == "Session cleared." | Telegram, Slack, Feishu, WeChat, WhatsApp, LINE, Discord, Matrix | ✅ 完成 | 0.5 天 |
| 2 | **`allowed_senders` 过滤** | 配置白名单后，非白名单用户发送消息 → 断言 bot **无回复** | Telegram ✅, LINE ✅ | ✅ 完成 | 0.5 天 |
| 3 | **消息去重 (`MessageDedup`)** | 同一 message_id 重复发送两次 → 断言 bot 只回复一次 | Feishu ✅, LINE ✅ | ✅ 完成 | 0.5 天 |
| 4 | **未知命令帮助** | octos 将未知 slash 命令发给 LLM 而非返回帮助文本，不属于黑盒测试范畴 | — | ❌ 不适用 | 0 |
| 5 | **API Channel 黑盒测试** | WS 连接 + client/hello、session/list、session/open + turn/start、session/delete、system/status.get | API ✅ | ✅ 基础完成 | 2 天 |

### P1 — 中等优先级

| # | 事项 | 黑盒验证方式 | 涉及 Channel | 预估工作量 |
|---|------|-------------|-------------|:----------:|
| 6 | **LINE 测试扩展** | 补齐标准命令集到 ~25 个用例 | LINE ✅ | ✅ 完成 |
| 7 | **WeCom / WeCom Bot 测试扩展** | 补齐标准命令集 | WeCom ✅, WeCom Bot ✅ | ✅ 完成 | 1–2 天 |
| 8 | **Email Mock 化** | 构建 Mock IMAP/SMTP Server，替代真实邮箱测试 | Email | 2–3 天 |
| 9 | **Telegram 按钮/键盘交互** | 发送 Inline Keyboard → 注入 Callback Query → 断言 bot 响应 | Telegram | 1 天 |
| 10 | **Discord 反应/编辑** | 注入 Reaction 事件 → 断言 bot 响应编辑后的消息 | Discord | 1 天 |

### P2 — 基础设施 / 长期

| # | 事项 | 说明 | 预估工作量 |
|---|------|------|:----------:|
| 11 | **QQ Bot / Twilio 黑盒测试** | 从零构建 Mock + 基础命令测试 | 各 1–2 天 |
| 12 | **跨 channel 并发** | 同一用户从多个 channel 发消息，验证 session 隔离 | 1–2 天 |
| 13 | **断线重连黑盒验证** | Mock Server 断开 WS → 恢复 → 断言消息仍能正常收发 | 1–2 天 |
| 14 | **gateway 重启后会话恢复** | `test_run.py` 支持中途重启 gateway → 验证历史会话仍可读 | 需框架改造 |

---

## 四、黑盒边界说明

以下属于**内部实现细节**，无法通过"发消息 → 看回复"验证，**不列入本 roadmap**：

- AES-256-CBC 加解密过程、HMAC-SHA256 签名验证
- Token TTL 刷新逻辑、签名有效期计算
- WebSocket 帧协议细节、心跳包格式

这些应归属于 octos 自身的单元测试 / 集成测试范畴。

---

## 五、已知阻塞（黑盒视角）

| 问题 | 外部可见行为 | 状态 |
|------|-------------|:----:|
| Telegram `test_soul_per_profile` / `test_queue_mode_per_profile` 被 skip | 不同 chat_id 消息被路由到同一 profile，会话未隔离 | **octos 功能缺陷**，测试正确 skip，等待修复后启用 |
| Email 上下文膨胀 | 同一发件人后续邮件 bot 不再回复（LLM 400 错误） | **octos 功能缺陷**，见 `docs/email_context_issue.md` |
| Mock Server 间歇崩溃导致后半段 skip | health check 连续失败 → pytest.skip | **测试框架稳定性问题**，见 `TEST_SKIP_ANALYSIS.md` |
| Email QQ 邮箱自发自收 IMAP UNSEEN 失效 | QQ 邮箱将自发自收邮件自动标记已读 | **QQ 邮箱行为限制**，非 octos 问题，建议换双邮箱测试 |

---

## 六、建议执行顺序

### 本周（立即可做）
1. ~~`/clear` 命令测试 — 全部已测 channel 各补 1 个用例~~ ✅
2. ~~`allowed_senders` 过滤测试 — 挑 2–3 个 channel 验证~~ ✅ (Telegram, LINE)
3. ~~`MessageDedup` 去重测试 — 飞书/Line 各补 1 个用例~~ ✅
4. 未知命令帮助 — ❌ 不适用（octos 将未知命令发给 LLM）
5. ~~API Channel 黑盒测试 — 最大缺口~~ ✅ 基础完成 (6 个 WS 测试 + 7 个 REST/基础测试)

### 2–3 周
5. ~~API Channel 测试框架设计 — 最大缺口~~ ✅ 基础完成
6. API Channel 扩展 — ~~turn/interrupt、session/snapshot、content/list~~ ✅ 已完成 (6→19 用例), 继续扩展 session/files.list、task/list、task/cancel、approval/*
7. ~~LINE / WeCom / WeCom Bot 测试扩展到 20+ 用例~~ ✅ (LINE 25, WeCom 14, WeCom Bot 17)

### 长期
7. Email Mock Server（IMAP/SMTP Mock）
8. Telegram 按钮/键盘、Discord 反应/编辑 等高级交互
9. 跨 channel 并发、断线重连、gateway 重启恢复
