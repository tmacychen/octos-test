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

### 6. LINE webhook 集成断裂 ❌ 阻塞 (待排查 mock/路由)

**实测 (2026-07-12)**: `TestLineLLMMessages` 3/3 FAIL（每个等满 90s 无回复）；`TestLineSessionCommands::test_new_default` FAIL（"Bot 未在 30s 内回复 '/new'"）。bot 对**任何**注入消息完全无回复。

**根因定位**: octos LINE gateway 日志**无任何 LLM 调用 / process_inbound 记录**，说明 mock 注入的消息根本未到达 octos。
- `mock_line.py` `/_inject` 对事件签名后转发到 `http://127.0.0.1:{webhook_port}/line/webhook`；`runner_line.py` 用 `webhook_port=8647`；gateway 日志 `LINE webhook server listening port=8647` → **端口匹配**
- 疑点（需查 octos 侧）：① `X-Line-Signature` 校验（`channel_secret=test_secret` 是否与 octos 侧一致）② webhook path `/line/webhook` 是否匹配 ③ octos LINE webhook 路由是否实际挂载
- **对照**: Matrix（appservice 推送模式）`TestMatrixLLMMessages` 2/2 PASS（39s），证明 70b + octos LLM 管线本身可用 → Line 问题是 **webhook 转发/集成链路**，与模型无关
**结论**: Line channel 在测试环境完全不可用，属 blocker。需排查 `mock_line.py` 转发与 octos LINE webhook 配置/路由。

### 7. QQ WebSocket + access_token 集成断裂 ❌ 阻塞

**实测 (2026-07-12)**: `TestQqBotSessionCommands::test_new_default` FAIL（"Bot 未在 30s 内回复 '/new'"）。

**根因定位**: octos QQ gateway 日志反复 `QQBot: connection lost, reconnecting error=QQBot: missing access_token in response`（attempt 1/2/3，delay 5s→10s→20s）。QQ 用 **WebSocket + access_token 认证**连接官方服务器，mock 环境无法提供真实 `access_token` → 连接层反复重连失败 → 入站消息永远处理不了。
- 与 Line 同属**认证/连接层断裂**，非 70b 模型问题
- 疑点（需查 octos/mock）：`mock_qq.py` 是否模拟了 token 获取端点；octos QQ bot 在 mock 模式下是否应跳过真实 token 校验

### 8. Twilio 出站 401（入站通、出站断）✅ 已修复 (2026-07-12)

**实测 (2026-07-12)**: `TestTwilioSessionCommands::test_new_default` FAIL（"Bot 未在 30s 内回复 '/new'"）。

**根因定位**: Twilio 与 Line/QQ 不同——**入站 webhook 是通的**（gateway 日志 `Twilio webhook server listening port=8649`，无连接错误，命令被处理）。但**出站回复报 401**：
- 日志 `Twilio API error status=401 Unauthorized {"code":20003,"message":"Authentication Error - invalid username"...}`
- `mock_twilio.py` 的 `/Messages.json` 仅校验 `auth.startswith("Basic ")`，**不校验具体用户名/密码**，且不会返回 Twilio 风格的 `code:20003` 错误体
- 因此该 401 **不是 mock 返回**，而是 octos 出站**打到了真实 `api.twilio.com`**（而非 mock `http://127.0.0.1:5011`）—— 缺少 `TWILIO_API_URL` 指向 mock 的配置，octos 用 dummy `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN` 命中真实 Twilio → 401
- 出站失败 → bot 回复发不出 → 测试超时
**结论**: Twilio 入站链路可用，坏在**出站 API 基地址配置缺失**（未指向 mock）。属测试环境配置问题，非模型问题。

**修复 (2026-07-12)**:
1. **octos** `crates/octos-bus/src/twilio_channel.rs`：新增 `twilio_api_base()` 读取 `TWILIO_API_BASE_URL`（兼容旧 `TWILIO_API_URL`），将出站 URL 由硬编码 `https://api.twilio.com` 改为 `format!("{}/2010-04-01/Accounts/{}/Messages.json", twilio_api_base(), sid)`。与 WeCom/Line/Discord/Slack 的 `XXX_API_BASE_URL` 惯例一致。`test_run.py` 已设 `TWILIO_API_BASE_URL=http://127.0.0.1:5011`，出站现指向 mock。
2. **octos-test** `bot_mock_test/.venv` 缺失 `python-multipart`：mock `send_message` 用 `await request.form()` 解析 octos 发来的 form 必需此包。已 `uv pip install --python bot_mock_test/.venv/bin/python python-multipart`，并在根 `pyproject.toml` 加入 `python-multipart`（依赖持久化）。注意 test_run.py 用的 mock/pytest venv 是 `bot_mock_test/.venv`，非根 `octos-test/.venv`。
3. **验证**：`TestTwilioSessionCommands` 7/7 PASS（9.06s，命令本地短路）；`test_simple_greeting` PASS（28s，日志 `calling LLM model=meta/llama-3.1-70b-instruct` 端到端通）。Twilio 在 70b 下完全可用。
**待办**：octos 的 `twilio_channel.rs` 改动需提交到 octos 仓库（当前仅本地修改未 commit）。

### 9. Matrix 可用但命令走 LLM 高延迟 ⚠️ 非阻塞（已知）

**实测 (2026-07-12)**: `TestMatrixLLMMessages` 2/2 PASS（39s）；`TestMatrixSessionCommands` 4/7 FAIL（命令走 LLM 慢，50-108s 临界 `TIMEOUT_COMMAND=50`）。详见 P2 后续表。

### 10. WeCom 完全可用 ✅（webhook 模式端到端）

**实测 (2026-07-12)**: `TestWeComSessionCommands::test_new_default` PASS（1.34s，命令本地短路）；`TestWeComLLM` 3/3 PASS（70b 端到端，日志 `calling LLM model=meta/llama-3.1-70b-instruct` 正常返回）。
- 关键：`mock_wecom.py` 完整模拟了 WeCom 服务器（含 `/cgi-bin/gettoken` 提供 `access_token` + AES 加密回调 `encrypt_wecom_message` + `verify_wecom_signature`），webhook 入站/出站全打通
- **对照价值**: 证明 webhook 模式下 70b 端到端完全可用，与 Matrix（appservice 推送）一致 → 所有失败 channel 的问题都在**集成/认证层**，不是模型

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
| P2 | **Matrix/Line/QQ/WeCom/Twilio 回归诊断** | ✅ 已完成（2026-07-12）：WeCom 完全可用；Matrix 命令走 LLM 慢(功能OK)；Line/QQ 集成断裂；Twilio 入站通出站 401。详见 P0 #6-#10 |
| P2 | **Matrix 命令走 LLM 高延迟** | ⚠️ 已知问题：octos Matrix 把每条入站(含 /new 命令)都交 LLM agent（日志 `agent returned in 108371ms`），70b 下 50-108s；`TIMEOUT_COMMAND=50` 临界超时（SessionCommands 4/7 FAIL）。命令功能正确(agent ok=true)，建议提高超时或 octos 让 Matrix 命令本地短路 |
| P2 | **Line webhook 集成断裂** | ❌ 阻塞：见 P0 #6，所有 Line 测试 bot 无回复 |
| P2 | **QQ WebSocket token 断裂** | ❌ 阻塞：见 P0 #7，QQ bot `missing access_token`，连接层反复重连失败 |
| P2 | **Twilio 出站 401** | ✅ 已修复：见 P0 #8，octos 加 `TWILIO_API_BASE_URL` 支持 + mock 装 `python-multipart`，`TestTwilioSessionCommands` 7/7 PASS、`test_simple_greeting` PASS |
| P2 | **WeCom 完全可用** | ✅ 见 P0 #10，`TestWeComLLM` 3/3 PASS + 命令秒回，webhook 模式 70b 端到端通 |
| P2 | **Slack app_mention 测试** | mock 已支持，需补测试用例 |
| P3 | **全 channel 全量测试** | 所有 15 channel 回归 |
| — | **Telegram/Discord profile routing** | 阻塞 — 等待 octos 实现 |
| — | **LLM context 溢出** | 阻塞 — 70B 模型 131K 限制 |
