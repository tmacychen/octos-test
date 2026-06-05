# test_soul_per_profile 失败分析

## 📋 问题现象

```
2026-04-28T07:35:07.578461Z  INFO user soul updated profile_id=_main soul_len=29
2026-04-28T07:35:08.181773Z  INFO user soul updated profile_id=_main soul_len=26
FAILED [ 62%] bot_mock_test/test_telegram.py::TestTelegramProfileMode::test_soul_per_profile
```

两个 soul 更新都使用了 `profile_id=_main`，而不是预期的 `profile-a` 和 `profile-b`。

## 🔍 根本原因

### 1. Soul 隔离代码是正确的 ✅

在 `/Volumes/AppleData/octos/crates/octos-cli/src/gateway_dispatcher.rs` 中：

```rust
pub async fn handle_soul_command(
    &self,
    cmd: &str,
    reply_channel: &str,
    reply_chat_id: &str,
    session_key: &SessionKey,
) -> Option<DispatchResult> {
    // Resolve profile-specific data directory
    let profile_id = session_key.profile_id().unwrap_or(MAIN_PROFILE_ID);
    let data_dir = match self.resolve_data_dir_for_profile(profile_id) {
        Some(d) => d,
        None => { /* error handling */ }
    };
    // ... write/read soul from data_dir
}
```

这段代码**正确地从 SessionKey 中提取 profile_id 并使用对应的数据目录**。

### 2. 但 SessionKey 中的 profile_id 始终是 `_main` ❌

从日志可以看到：
```
session=_main:telegram:301#profile-a-topic
session=_main:telegram:302#profile-b-topic
```

SessionKey 的格式是 `{profile_id}:{channel}:{chat_id}#{topic}`，这里 profile_id 是 `_main`。

### 3. Profile 路由缺失 ❌

**关键问题：Octos 没有实现基于 chat_id 的自动 profile 路由。**

对比不同 channel 的实现：

#### Matrix Channel（有完整的路由）
```rust
// crates/octos-bus/src/matrix_channel.rs
pub struct BotRouter {
    routes: Arc<RwLock<HashMap<String, BotEntry>>>, // matrix_user_id -> metadata
    room_bots: Arc<RwLock<HashMap<String, HashSet<String>>>>, // room_id -> profile_ids
}

// 路由逻辑：
// 1. 检查消息中的显式目标用户 ID
// 2. 检查 @mention
// 3. 检查 DM 房间映射
if let Some(profile_id) = route_by_explicit_target(&state.bot_router, content).await {
    metadata[METADATA_TARGET_PROFILE_ID] = json!(profile_id);
} else if let Some(profile_id) = route_by_matrix_mention(...).await {
    metadata[METADATA_TARGET_PROFILE_ID] = json!(profile_id);
} else if let Some(profile_id) = state.bot_router.route_by_room(room_id).await {
    metadata[METADATA_TARGET_PROFILE_ID] = json!(profile_id);
}
```

#### Telegram Channel（没有路由）
```rust
// crates/octos-bus/src/telegram_channel.rs
// ❌ 没有任何 profile 路由逻辑
// 所有消息都使用默认的 _main profile
```

### 4. 测试设计假设错误 ❌

`test_soul_per_profile` 期望：
```python
# Profile A (chat_id=301) 设置 soul
inject_and_get_reply(runner, "/soul You are a professional coder.", chat_id=301)

# Profile B (chat_id=302) 设置不同的 soul  
inject_and_get_reply(runner, "/soul You are a creative writer.", chat_id=302)

# 验证隔离
soul_a = inject_and_get_reply(runner, "/soul", chat_id=301)
assert "writer" not in soul_a.lower()  # ← 期望 A 的 soul 不包含 B 的内容
```

**但这个假设是错误的：** 因为 Telegram 没有 profile 路由，chat_id 301 和 302 的消息都被路由到 `_main` profile，导致 soul 相互覆盖。

## 💡 解决方案

### 方案 1：实现 Telegram Profile 路由（长期方案）

类似于 Matrix 的 `BotRouter`，为 Telegram 添加基于 sender_id 或 chat_id 的路由：

```rust
// 伪代码
pub struct TelegramProfileRouter {
    routes: Arc<RwLock<HashMap<String, String>>>, // chat_id -> profile_id
}

impl TelegramProfileRouter {
    pub async fn resolve_profile(&self, chat_id: &str) -> Option<String> {
        self.routes.read().await.get(chat_id).cloned()
    }
    
    pub async fn register_route(&self, chat_id: &str, profile_id: &str) {
        self.routes.write().await.insert(chat_id.to_string(), profile_id.to_string());
    }
}
```

然后在 `gateway_runtime.rs` 中使用：
```rust
let dispatch_profile_id = telegram_router.resolve_profile(&inbound.chat_id).await;
```

**优点：** 完整的解决方案，支持真正的多用户隔离
**缺点：** 需要大量开发工作，包括 API、配置、持久化等

### 方案 2：修改测试使用显式的 profile 切换命令（中期方案）

如果 Octos 支持通过命令切换 profile（如 `/profile profile-a`），测试可以这样写：

```python
def test_soul_per_profile(self, runner):
    # 切换到 Profile A
    inject_and_get_reply(runner, "/profile profile-a", chat_id=301)
    
    # Profile A 设置 soul
    inject_and_get_reply(runner, "/soul You are a professional coder.", chat_id=301)
    
    # 切换到 Profile B
    inject_and_get_reply(runner, "/profile profile-b", chat_id=302)
    
    # Profile B 设置不同的 soul
    inject_and_get_reply(runner, "/soul You are a creative writer.", chat_id=302)
    
    # 验证...
```

**优点：** 不需要修改核心路由逻辑
**缺点：** 需要先实现 `/profile` 命令

### 方案 3：暂时 Skip 这个测试（短期方案）

在 Telegram profile 路由实现之前，skip 这个测试：

```python
@pytest.mark.skip(reason="Telegram profile routing not implemented yet")
def test_soul_per_profile(self, runner):
    ...
```

**优点：** 立即可用，避免 CI/CD 失败
**缺点：** 无法验证 soul 隔离功能

### 方案 4：创建独立的测试环境（变通方案）

为每个 profile 启动独立的 Bot 实例，使用不同的 `--data-dir`：

```bash
# Terminal 1: Profile A
octos gateway --config config.json --data-dir /tmp/test-profile-a

# Terminal 2: Profile B  
octos gateway --config config.json --data-dir /tmp/test-profile-b
```

然后测试分别连接到两个 Bot。

**优点：** 不需要修改代码
**缺点：** 测试复杂度高，需要管理多个进程

## 🎯 推荐行动方案

### 立即执行
1. **Skip `test_soul_per_profile` 测试**，添加注释说明原因
2. **记录 Issue**，跟踪 Telegram profile 路由功能的实现

### 中期（1-2 周）
1. **实现简单的 profile 路由**：基于配置文件映射 chat_id → profile_id
2. **添加 `/profile` 命令**：允许用户手动切换 profile

### 长期（1-2 月）
1. **完整的 BotRouter**：类似 Matrix 的实现，支持动态注册和路由
2. **Dashboard 配置界面**：可视化管理 profile 路由规则

## 📝 相关代码位置

### 需要修改的文件

1. **Octos 主仓库** (`/Volumes/AppleData/octos`):
   - `crates/octos-bus/src/telegram_channel.rs` - 添加 profile router
   - `crates/octos-cli/src/commands/gateway/gateway_runtime.rs` - 集成 router
   - `crates/octos-core/src/gateway.rs` - 可能需要扩展 InboundMessage

2. **测试仓库** (`/Volumes/AppleData/octos-test`):
   - `bot_mock_test/test_telegram.py` - skip 或修改测试
   - `bot_mock_test/mock_tg.py` - 可能需要支持 profile 相关的 mock

## 🔗 参考资料

- Matrix BotRouter 实现：`crates/octos-bus/src/matrix_channel.rs` Line 92-259
- SessionKey 构建：`crates/octos-cli/src/commands/gateway/mod.rs` Line 144-152
- Profile 数据存储：`crates/octos-cli/src/profiles.rs`

---

**创建时间：** 2026-04-28  
**最后更新：** 2026-04-28  
**状态：** 待解决 - 需要实现 Telegram profile 路由
