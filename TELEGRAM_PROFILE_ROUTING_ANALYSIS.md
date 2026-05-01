# Telegram Profile Routing 缺失分析

## 📋 结论

**确认：** `test_queue_mode_per_profile` 和 `test_soul_per_profile` 被 skip 的原因是 **正确的**。

octos 的 Telegram channel **确实没有实现**从 `chat_id` 到 `profile_id` 的路由功能。

---

## 🔍 技术分析

### 1. Matrix Channel 的实现（参考）

Matrix channel **完整实现了** profile routing，通过 `BotRouter` 组件：

```rust
// crates/octos-bus/src/matrix_channel.rs:1143-1153
// Route to bot profile: explicit target first, then @mention, then DM room mapping
let mut metadata = json!({});
if let Some(profile_id) = route_by_explicit_target(&state.bot_router, content).await {
    metadata[METADATA_TARGET_PROFILE_ID] = json!(profile_id);
} else if let Some(profile_id) =
    route_by_matrix_mention(&state.bot_router, content, body_text).await
{
    metadata[METADATA_TARGET_PROFILE_ID] = json!(profile_id);
} else if let Some(profile_id) = state.bot_router.route_by_room(room_id).await {
    metadata[METADATA_TARGET_PROFILE_ID] = json!(profile_id);
}
```

**三种路由策略：**
1. **Explicit target** - 消息中明确指定目标 profile
2. **@Mention** - 通过 @bot_username 提及
3. **Room mapping** - 通过房间 ID 映射（DM 场景）

---

### 2. Telegram Channel 的实现（缺失）

Telegram channel **完全没有** profile routing 逻辑：

```rust
// crates/octos-bus/src/telegram_channel.rs:442-451
let inbound = InboundMessage {
    channel: "telegram".into(),
    sender_id,
    chat_id: msg.chat.id.0.to_string(),
    content: text,
    timestamp: Utc::now(),
    media,
    metadata: serde_json::json!({}),  // ⚠️ 空的 metadata！
    message_id: Some(msg.id.0.to_string()),
};
```

**关键问题：**
- ❌ `metadata` 是空的 JSON 对象 `{}`
- ❌ 没有 `target_profile_id` 字段
- ❌ 没有根据 `chat_id` 查找 profile 的逻辑
- ❌ 没有类似 Matrix 的 `BotRouter` 组件

---

### 3. Gateway Dispatch 逻辑

Gateway 依赖 `metadata.target_profile_id` 来路由消息到正确的 profile：

```rust
// crates/octos-cli/src/commands/gateway/gateway_runtime.rs:1515-1524
let target_profile = inbound
    .metadata
    .get("target_profile_id")  // ← 期望从这里获取
    .and_then(|v| v.as_str())
    .map(|s| s.to_string());

let mut dispatch_profile_id = resolve_dispatch_profile_id(
    self.profile_id.as_deref(),
    target_profile.as_deref(),
    self.profile_store.as_deref(),
)?;
```

**工作流程：**
1. 从 `inbound.metadata.target_profile_id` 读取目标 profile
2. 如果存在且有效，使用该 profile
3. 否则回退到 gateway 的主 profile

**问题：** Telegram channel 从不设置 `target_profile_id`，所以所有消息都路由到主 profile。

---

## 🎯 测试失败原因

### test_soul_per_profile

```python
# bot_mock_test/test_telegram.py:467-486
def test_soul_per_profile(self, runner):
    # Profile A (chat_id=201) 设置 soul
    text_a = inject_and_get_reply(runner, "/soul You are a Python coder", 
                                  timeout=TIMEOUT_COMMAND, chat_id=201)
    
    # Profile B (chat_id=202) 检查 soul
    text_b = inject_and_get_reply(runner, "/soul", 
                                  timeout=TIMEOUT_COMMAND, chat_id=202)
    
    # 期望：Profile B 不应该有 Profile A 的 soul
    assert "coder" not in soul_b.lower()
```

**为什么会失败：**
1. 两个请求都使用不同的 `chat_id`（201 vs 202）
2. 但 Telegram channel 不根据 `chat_id` 路由到不同 profile
3. 两个请求都被路由到**同一个主 profile**
4. Profile B 会看到 Profile A 设置的 soul
5. 断言失败：`"coder"` 出现在 `soul_b` 中

---

### test_queue_mode_per_profile

```python
# bot_mock_test/test_telegram.py:489-507
def test_queue_mode_per_profile(self, runner):
    # Profile A (chat_id=301) 设置为 followup
    text_a = inject_and_get_reply(runner, "/queue followup",
                                  timeout=TIMEOUT_COMMAND, chat_id=301)
    assert "Followup" in text_a
    
    # Profile B (chat_id=302) 保持默认 collect
    text_b = inject_and_get_reply(runner, "/queue",
                                  timeout=TIMEOUT_COMMAND, chat_id=302)
    assert "Collect" in text_b or "collect" in text_b.lower()
    
    # 验证 A 仍然是 followup
    text_a_check = inject_and_get_reply(runner, "/queue",
                                        timeout=TIMEOUT_COMMAND, chat_id=301)
    assert "Followup" in text_a_check
```

**为什么会失败：**
1. 同样因为所有消息路由到同一个 profile
2. Profile A 设置 `/queue followup` 后，主 profile 变为 followup 模式
3. Profile B 查询 `/queue` 时，看到的也是 followup（而不是默认的 collect）
4. 断言失败：期望 `"Collect"` 但实际得到 `"Followup"`

---

## 💡 解决方案

要实现 per-profile 隔离，需要在 Telegram channel 中添加 profile routing 逻辑。有以下选项：

### 方案 1：Chat ID → Profile ID 映射表（推荐）

在 `TelegramChannel` 中添加一个简单的映射：

```rust
pub struct TelegramChannel {
    bot: Bot,
    allowed_senders: HashSet<String>,
    shutdown: Arc<AtomicBool>,
    media_dir: PathBuf,
    http: Client,
    bot_username: Option<String>,
    require_mention: bool,
    // ✅ 新增：chat_id 到 profile_id 的映射
    chat_to_profile: Arc<RwLock<HashMap<String, String>>>,
}

impl TelegramChannel {
    /// Register a chat_id -> profile_id mapping
    pub fn register_chat_profile(&self, chat_id: &str, profile_id: &str) {
        let mut map = self.chat_to_profile.write().unwrap();
        map.insert(chat_id.to_string(), profile_id.to_string());
    }
    
    /// Get profile_id for a chat_id
    fn get_profile_for_chat(&self, chat_id: &str) -> Option<String> {
        let map = self.chat_to_profile.read().unwrap();
        map.get(chat_id).cloned()
    }
}
```

在创建 `InboundMessage` 时使用：

```rust
let mut metadata = serde_json::json!({});
if let Some(profile_id) = self.get_profile_for_chat(&msg.chat.id.0.to_string()) {
    metadata["target_profile_id"] = json!(profile_id);
}

let inbound = InboundMessage {
    channel: "telegram".into(),
    sender_id,
    chat_id: msg.chat.id.0.to_string(),
    content: text,
    timestamp: Utc::now(),
    media,
    metadata,  // ✅ 现在包含 target_profile_id
    message_id: Some(msg.id.0.to_string()),
};
```

---

### 方案 2：从配置文件加载映射

在 profile 配置中添加 `allowed_senders` 时同时指定 profile_id：

```json
{
  "channels": [
    {
      "type": "telegram",
      "token_env": "TELEGRAM_BOT_TOKEN",
      "allowed_senders": ["12345:user1:profile-a", "67890:user2:profile-b"]
    }
  ]
}
```

解析格式：`chat_id:username:profile_id`

---

### 方案 3：使用环境变量（最简单，适合测试）

添加 `TELEGRAM_CHAT_TO_PROFILE` 环境变量：

```bash
export TELEGRAM_CHAT_TO_PROFILE="201:profile-a,202:profile-b,301:profile-c"
```

在 `TelegramChannel::new()` 中解析：

```rust
let mut chat_to_profile = HashMap::new();
if let Ok(mapping) = std::env::var("TELEGRAM_CHAT_TO_PROFILE") {
    for pair in mapping.split(',') {
        if let Some((chat_id, profile_id)) = pair.split_once(':') {
            chat_to_profile.insert(chat_id.to_string(), profile_id.to_string());
        }
    }
}
```

---

## 📊 对比总结

| 特性 | Matrix Channel | Telegram Channel |
|------|---------------|------------------|
| Profile Router | ✅ `BotRouter` | ❌ 无 |
| Metadata Injection | ✅ `target_profile_id` | ❌ 空 `{}` |
| @Mention Routing | ✅ 支持 | ❌ 不支持 |
| Room/Chat Mapping | ✅ 支持 | ❌ 不支持 |
| Per-Profile Isolation | ✅ 工作正常 | ❌ 无法隔离 |

---

## 🎯 当前状态

- **Skip 原因正确** ✅
- **文档准确** ✅ ([TEST_SOUL_PER_PROFILE_FAILURE.md](file:///Volumes/AppleData/octos-test/TEST_SOUL_PER_PROFILE_FAILURE.md))
- **测试设计合理** ✅（等待功能实现后可直接启用）
- **需要实现的功能**：Telegram channel 的 profile routing

---

## 📝 建议

1. **短期**：保持测试为 skip 状态，文档清晰说明原因
2. **中期**：实现方案 3（环境变量），快速支持测试
3. **长期**：实现方案 1（映射表），提供完整的 profile routing 功能
4. **最终**：考虑实现方案 2（配置文件），提供更灵活的配置方式

---

**生成时间：** 2026-04-28  
**分析基于：** octos commit 5e6641ee..HEAD (squashed to 3 commits)
