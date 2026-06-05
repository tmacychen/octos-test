# Octos Channel 测试覆盖分析

> 生成时间: 2026-06-05
> 状态：11 个 channel 已有测试文件，4 个完全空白（API、QQ Bot、Twilio、CLI 无 bot 测试）

## 一、Channel 架构概览

octos 通过 `octos-bus` crate 的 `Channel` trait 定义了统一接口，`ChannelManager` 管理生命周期。
目前支持 **15 个 channel**（11 个已有测试文件，4 个完全空白），通过 Cargo feature flags 条件编译。

| Channel | Feature Flag | 测试状态 | 用例数 | 测试充分度 |
|---------|-------------|----------|:------:|-----------|
| CLI | 内置 | ✅ CLI 独立测试 | — | ⚠️ 仅基本命令 |
| API | `api` | ❌ **无测试** | 0 | — |
| Telegram | `telegram` | ✅ `test_telegram.py` | 51 | 较充分 |
| Discord | `discord` | ✅ `test_discord.py` | 37 | 较充分 |
| Matrix | `matrix` | ✅ `test_matrix.py` | 41 | 较充分 |
| Slack | `slack` | ✅ `test_slack.py` | 47 | 中等 |
| Feishu | `feishu` | ✅ `test_feishu.py` | 34 | 中等 |
| WeChat | `wechat` | ✅ `test_wechat.py` | 34 | 中等 |
| WhatsApp | `whatsapp` | ✅ `test_whatsapp.py` | 23 | 基础 |
| Email | `email` | ⚠️ `test_email.py`（真实邮箱手动测试） | 3 | 仅手动 |
| LINE | `line` | ⚠️ `test_line.py` | 9 | 较少 |
| WeCom | `wecom` | ⚠️ `test_wecom.py` | 7 | 较少 |
| WeCom Bot | `wecom-bot` | ⚠️ `test_wecom_bot.py` | 14 | 较少 |
| QQ Bot | `qq-bot` | ❌ **无测试** | 0 | — |
| Twilio | `twilio` | ❌ **无测试** | 0 | — |

## 二、现有测试覆盖范围

### 已测功能（跨 Channel 通用）

| 测试类别 | 测试的 Channel |
|---------|---------------|
| Session 管理 (`/new`, `/s`, `/sessions`, `/back`, `/delete`) | Telegram, Discord, Matrix, Slack, Feishu, WeChat, WhatsApp, LINE, WeCom, WeCom Bot |
| 配置命令 (`/soul`, `/queue`, `/status`, `/reset`, `/adaptive`, `/help`) | Telegram, Discord, Matrix, Slack, Feishu, WeChat, WhatsApp, LINE, WeCom, WeCom Bot |
| 别名命令 (`/b`, `/d`) | Telegram, Slack, Discord, Matrix |
| LLM 消息（英文/中文/身份） | Telegram, Discord, Matrix, Slack, Feishu, WeChat, WhatsApp, LINE, WeCom, WeCom Bot |
| 多用户隔离 | Telegram, Discord, Matrix, Slack, Feishu, WeChat, WhatsApp, LINE, WeCom, WeCom Bot |
| Profile 会话隔离 | Matrix 正常；Telegram 部分 skip（profile routing 未实现） |
| 中断命令（多语言） | Telegram, Discord, Matrix, Slack, Feishu, WeChat, WhatsApp |
| 消息分片 | Telegram, WeChat, Discord, Matrix, Slack, Feishu |
| 并发限制（10线程） | Telegram, Slack, Feishu, WeChat, WhatsApp |
| 文件大小上限（10MB） | Telegram, Discord, Feishu, WeChat, WhatsApp |
| Stream 编辑 | Telegram, Feishu, Discord |
| **`/clear` 命令** | ❌ **全部已测 channel 缺失** |
| **`allowed_senders` 过滤** | ❌ **全部已测 channel 缺失** |
| **消息去重 (`MessageDedup`)** | ❌ **全部已测 channel 缺失** |

## 三、各 Channel 未测的高级特性

### 3.1 Telegram — 大量高级特性未覆盖

| 特性 | 代码位置 | 说明 |
|------|---------|------|
| 媒体消息（Photo/Audio/Video/Document） | `send_photo`, `send_voice`, `send_audio`, `send_document` | 仅测文本回复 |
| Inline Keyboard | `send_message_with_inline_keyboard` | metadata `inline_keyboard` 字段 |
| Callback Query | `UpdateKind::CallbackQuery` | 按钮点击回调 |
| Mention Gating | 群组 @bot / 回复 / /command 才响应 | 群组场景 |
| 命令注册 | `/new`, `/s` 等 | 命令菜单可见性 |
| HTML fallback | `send_html_with_fallback` | HTML 解析失败降级 |
| 编辑/删除 | `edit_message`, `delete_message` | Stream 编辑仅部分覆盖 |
| Typing/Listening | `send_chat_action` | 完全未测 |
| 指数退避重连 | 5s→60s reconnection | 完全未测 |
| Dedup | `update_id` 去重 | 完全未测 |
| 健康检查 | `get_me` | 完全未测 |
| Caption 截断 | 1024 字符上限 | 未覆盖边界值 |

### 3.2 Discord — 中等特性未覆盖

| 特性 | 说明 |
|------|------|
| Embed 消息 | `send_embed` (title/description/fields/color) |
| Reaction | `react_to_message`, `remove_reaction` |
| 媒体附件下载 | attachment.url |
| Guild ID 追踪 | metadata `guild_id` |
| 消息编辑/删除 | `edit_message`, `delete_message` |

### 3.3 Email — 完全无 Mock 测试（仅真实邮箱手动模式）

| 特性 | 说明 |
|------|------|
| IMAP 轮询 | 需要 IMAP mock |
| SMTP 发送 | 需要 SMTP mock |
| HTML 邮件解析 | 多部分邮件体结构 |
| TLS 加密 | 465/587 端口 |
| 标记已读 | `\Seen` flag |
| 附件 | 邮件附件下载/发送 |
| 多用户隔离 | 不同发件人独立 session |
| 配置组合 | `imap_server`, `port`, `email`, `password`, `max_body_chars` 等 |

### 3.4 API Channel — 完全无测试（代码量最大 ~6800 行）

| 特性 | 说明 |
|------|------|
| POST /chat | SSE 流式响应 |
| Session CRUD | 多个 REST 端点 |
| Task 管理 | 取消、重启 |
| Watcher 模式 | 事件流 + topic 过滤 |
| 文件处理 | `file_handle` 编解码 |
| Prometheus /metrics | 监控端点 |
| 会话重放 | `max_replayed_session_seq` |
| Delta 计算 | token 级别增量 |
| 认证 | `auth_token` |
| Profile 多账号 | `profile_id` |

### 3.5 LINE — 基础测试（9 个用例）

已有基础命令测试，以下高级特性未覆盖：

| 特性 | 说明 |
|------|------|
| Webhook 签名验证 | HMAC-SHA256 |
| 媒体消息 | Image/Audio/Video/File |
| Location | title/address/lat/lng |
| Sticker | `[sticker message]` |
| Mention Gating | 群组 @mention |
| UTF-16→UTF-8 偏移转换 | LINE 编码差异 |
| 消息分片 | 5000 字符，最多 5 片/请求 |
| Dedup | `MessageDedup` |
| 内容上传 | LINE CDN 交互 |

### 3.6 WeCom + WeCom Bot — 基础测试（7 / 14 个用例）

已有 URL 验证、加密回调、消息收发等基础测试，以下高级特性未覆盖：

| 特性 | 说明 |
|------|------|
| AES-256-CBC 加密/解密 | PKCS7 |
| 签名验证 | `verify_wecom_signature` |
| Token 管理 | 7000s TTL 自动刷新 |
| 媒体上传/发送 | Image/Voice/Video/Location |
| WebSocket 长连接（Bot） | 心跳/ping/pong |
| 认证帧 | `aibot_subscribe` |

### 3.7 QQ Bot — 完全无测试

| 特性 | 说明 |
|------|------|
| WebSocket 事件流 | 标准 QQ Bot 协议 |
| 连接管理 | 自动重连 |
| 媒体消息 | 图片等 |

### 3.8 Twilio — 完全无测试

| 特性 | 说明 |
|------|------|
| SMS Webhook | 短信处理 |
| WhatsApp Webhook | WhatsApp 消息 |
| 签名验证 | Twilio 请求签名 |

### 3.9 WhatsApp — 仅基础测试

| 特性 | 说明 |
|------|------|
| 媒体消息 | Image/Audio/Video/Document |
| Node bridge 交互 | Baileys WebSocket |
| Multi-device | 多设备配对 |

## 四、跨 Channel 通用未测场景

| 场景 | 说明 |
|------|------|
| 多 Channel 并发 | 同一用户从多个 channel 发消息到同一 session |
| Channel 健康检查 | `health_check()` 返回值 |
| Channel Stop/Restart | `stop()` 后重启 |
| 注册冲突 | 同名 channel 注册 |
| 权限控制 | `allowed_senders` 过滤 |
| 消息去重 | 各 channel dedup 逻辑 |
| Rate Limiting | 各平台限流策略 |
| 断线重连 | 网络中断后重建 |
| 超时处理 | 配置项边界测试 |
| 配置错误 | 无效 Token/URL 等 |

## 五、已知问题

| 问题 | 详情 |
|------|------|
| Telegram / Soul per Profile | `test_soul_per_profile` 测试失败，见 `TELEGRAM_PROFILE_ROUTING_ANALYSIS.md` |
| Email 上下文膨胀 | 同一发件人所有邮件累积到同一 session，token 增长到 1.7M 后 400 失败，见 `docs/email_context_issue.md` |
| **Email 在 QQ 邮箱上 IMAP UNSEEN 失效** | QQ 邮箱将自发自收（From=To）的邮件自动标记为已读（SEEN），导致 octos IMAP `SEARCH UNSEEN` 无法发现新邮件。这是 QQ 邮箱行为限制，非 octos 代码问题。|
| **QQ 邮箱 SMTP 强制 From=AuthUser** | QQ 邮箱 SMTP 要求发件人地址必须等于认证账号（501 error），无法使用其他 From 地址。需要两个不同的 QQ 邮箱或改用其他邮箱提供商。 |
| Matrix 扩展特性 | `MATRIX_EXTENSIONS_IMPLEMENTATION.md` 中记录的未实现扩展 |
| Mock Server 间歇崩溃 | Health check 3 次重试后仍失败 → pytest.skip 后半段测试，见 `TEST_SKIP_ANALYSIS.md` |

## 六、测试优先级建议

| 优先级 | 事项 | 理由 | 预估工作量 |
|--------|------|------|-----------|
| P0 | **`/clear` 命令** | 全部已测 channel 缺失，共享命令，纯黑盒可验证 | 0.5 天 |
| P0 | **`allowed_senders` 过滤** | 全部已测 channel 缺失，外部可见行为（非白名单用户无回复） | 0.5 天 |
| P0 | **消息去重 (`MessageDedup`)** | 部分 channel 已实现，外部可验证（同一 message_id 重复发送只回复一次） | 0.5 天 |
| P0 | **API Channel** | 核心 REST API，无任何测试，代码量最大 | 3-4 天 |
| P0 | **Telegram 高级特性** | 用户量最大，丰富功能完全未测 | 2-3 天 |
| P1 | **LINE 测试扩展** | 已有基础测试，需补齐标准命令集 | 1-2 天 |
| P1 | **Email Mock 化** | 功能复杂（IMAP+SMTP），仅手动 | 2-3 天 |
| P1 | **WeCom/WeCom Bot 测试扩展** | 已有基础测试，需补齐标准命令集 | 1-2 天 |
| P2 | **QQ Bot 测试** | 覆盖中文互联网生态 | 1-2 天 |
| P2 | **Twilio 测试** | SMS/WhatsApp 渠道 | 1 天 |
| P2 | **Discord 高级特性** | Embed/Reaction/Edit | 1 天 |
| P2 | **WhatsApp 增强** | 媒体消息 | 1 天 |

## 七、基础设施建议

1. **统一 Mock Server 模板**：抽象通用的 webhook-based mock 基类，减少重复代码
2. **Channel 不可用标记**：`test_run.py` 中未实现的 channel 明确标记 `SKIP`
3. **Co-located Channel 测试**：`cli_test/` 纳入 `test_run.py --test bot cli`
4. **健康检查集成**：每个 bot test fixture 加入 `health()` 检查
