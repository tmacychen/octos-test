# TODO

---

## P0 — 阻塞问题排查状态

### 1. session_delete_rx 阻塞 (issue #1407) ✅ 已修复

**验证时间**: 2026-06-12 (本会话中完成)

**octos 代码确认**:
- `crates/octos-cli/src/session_actor.rs` line 5607, 5702: `self.inbox.try_recv()` — 非阻塞
- `crates/octos-cli/src/gateway_dispatcher.rs` line 773+: `rx.try_recv()` — 非阻塞
- 所有 `session_delete_rx` 已改为 `UnboundedReceiver` + `try_recv()`

**运行验证**:
- 重编 14 features binary 后, 多个 channel 无 `--api-port` 跑通过:
  - Matrix: 11 PASSED (之前 0)
  - Slack: 11 PASSED (之前 0)
  - Feishu: 4 PASSED
  - gateway log 显示 `dispatching message to session actor` → 消息正常分发到 LLM

**结论：issue #1407 在当前 octos commit `2afff187` 中已修复, 无需进一步操作。**

### 2. Telegram profile routing ❌ 阻塞 (等待 octos 实现)

**文件**: `bot_mock_test/test_telegram.py`
- `test_soul_per_profile`: 正确 SKIPPED (docstring: "requires automatic profile routing based on chat_id")
- `test_queue_mode_per_profile`: 正确 SKIPPED (same reason)

**原因**: octos 当前不同 chat_id 消息路由到同一 profile, 未实现 chat_id → profile_id 路由
**状态**: 测试正确跳过, 非测试 bug。等待 octos 功能实现后取消 skip 即可

### 3. Email LLM context 膨胀 ❌ 阻塞 (等待 octos session compaction)

**问题**: 同一发件人持续交互 → context 不断增长 → LLM 400 (超过 131K tokens) → bot 无法回复
**状态**: 需要 octos 实现 session compaction / context 限制机制。非测试侧可解决

### 4. Mock Server WS 间歇崩溃

**排查**:
- 浏览了最近全部日志文件 (65+ 个), 无 "Mock Server 崩溃" 记录
- 之前的崩溃发生在本会话早期阶段 (binary 缺 features、mock 协议不匹配时)
- 各测试文件都有 3-5 次 health check retry 保护机制
- 重编 binary + 修复 mock 协议后未再复现

**结论：当前 binary + mock 协议修复后, mock 崩溃问题未再复现。保留 health check guard 作为安全机制即可。**

### 5. Slack thread_ts 出站传播缺口 ❌ 阻塞 (等待 octos 修复)

**文件**: `bot_mock_test/test_slack.py` → `TestSlackThreadReplies::test_channel_thread_reply_same_thread`
- 状态: 已 `pytest.skip`（2026-07-12 实测确认），其余 2 个 thread 测试通过

**现象**: 在 Slack 频道 thread 中发消息，bot 回复落到频道根（`thread_ts=None`），而非同一 thread。
**根因 (octos)**: `octos-bus/src/slack_channel.rs:330-396`
- 入站事件 thread_ts 已正确写入 `InboundMessage.metadata.slack.thread_ts`
- 但出站 `OutboundMessage` 的 metadata 重建时**丢失 thread_ts**（channel_type 仍被正确保留 → DM 正确抑制 thread）
- `send()` 读 `msg.metadata.slack.thread_ts` 为 None → `use_thread=false` → 不带 thread_ts 回覆
**结论**: 测试正确 skip，非测试 bug。等待 octos 修复 thread_ts 出站传播后取消 skip。

---

## P1 — 功能缺口

| # | 事项 | 涉及 | 预估 |
|---|------|------|:----:|
| 5 | serve 6 个需 LLM/active turn 的 method 升真实调用 | serve | 1 天 |
| 6 | serve --stdio 传输黑盒测试 | serve | 1 天 |
| 7 | serve 36 个 notification 类型验证 | serve | 1-2 天 |
| 8 | octos-tui --mode protocol 黑盒 | tui | 1 天 |

## P2 — 中优先级

| # | 事项 | 涉及 | 预估 | 状态 |
|---|------|------|:----:|:----:|
| 9 | Feishu Webhook 模式 | Feishu | 1-2 天 | ✅ 已在测 (14/14 PASS) |
| 10 | WhatsApp reconnect + 媒体 | WhatsApp | 1 天 | ✅ 已完成 |
| 11 | LINE 消息分片 | LINE | 0.5 天 | ✅ 已完成 |
| 12 | `test_run.py all` 扩到 tui + 完整 serve | 框架 | 0 天 | ✅ 已完成 |
| 13 | Email 补充测试用例回归验证 | Email | 0.5 天 | ✅ 已完成 |

## P3 — 低优先级

| # | 事项 | 涉及 | 预估 | 状态 |
|---|------|------|:----:|:----:|
| 14 | gateway 重启后会话恢复 | 框架 | 需框架改造 | ❌ |
| 15 | 各 channel 媒体发送 | Telegram/Discord | 1-2 天 | ❌ |
| 16 | Slack Thread Reply / Bot 自消息过滤 | Slack | 0.5 天 | ✅ 已完成 |
| 17 | ~~serve 并发测试~~ | serve | 1 天 | ✅ 已完成 |
| 18 | serve SSE 废弃端点说明更新 | serve | 0.5 天 | ❌ |

## 后续安排

| 优先级 | 事项 | 说明 |
|:------:|------|------|
| P1 | **Slack LLM 测试验证** | ✅ 已完成：QueueModeSteerNonAbort(2)/LLMMessages(3)/AbortCommands(3) 全 PASS；ThreadReplies 中频道 thread 回覆因 octos thread_ts 出站传播缺口 skip（另 2 个 PASS）|
| P1 | **WhatsApp typing 状态泄漏** | ✅ 已完成：clear_before 已缓解；Typing 测试注入前加固强断言，跨类(MultiUser→Typing)验证残留 typing=0 |
| P2 | **Matrix / Line / QQ / WeCom / Twilio 回归验证** | 新 binary + 新模型后全量跑 |
| P2 | **Slack app_mention 测试** | mock 已支持，需补测试用例 |
| P3 | **全 channel 全量测试** | 所有 15 channel 回归 |
| — | **Telegram/Discord profile routing** | 阻塞 — 等待 octos 实现 |
| — | **LLM context 溢出** | 阻塞 — 70B 模型 131K 限制 |
