# Discord 测试 Skip 问题 - 根本原因分析

## 📋 问题现象

所有 Discord bot 测试被跳过（45/45 skipped），没有任何测试实际执行。

## 🔍 根本原因

### 核心问题：Serenity SDK 不支持自定义 Gateway URL

**技术限制：**
- Octos 使用 `serenity` crate 作为 Discord SDK
- Serenity 硬编码连接到真实的 Discord Gateway：`wss://gateway.discord.gg/?v=10&encoding=json`
- Serenity **不提供**配置自定义 Gateway URL 的 API
- `DISCORD_API_BASE_URL` 环境变量只影响 REST API，不影响 WebSocket Gateway

### 证据链

#### 1. 日志分析

```
Gateway 日志 (02_gateway_dc_*.log):
  Line 26: "Starting Discord channel (gateway)"
  Line 27: "persona service started"
  → ❌ 缺少 "Discord bot connected" 日志
  
  预期日志（如果连接成功）：
  INFO Discord bot connected user=TestBot#1234
```

#### 2. 代码分析

**discord_channel.rs (Line 42, 180):**
```rust
let http = Arc::new(Http::new(token));  // ← 没有配置 base_url
// ...
let mut client = Client::builder(&self.token, intents)  // ← 使用默认配置
```

**Serenity SDK 默认行为:**
- REST API → `https://discord.com/api/v10`
- Gateway WS → `wss://gateway.discord.gg/?v=10&encoding=json`

#### 3. Mock Server 架构

```
Mock Discord Server (mock_discord.py):
  REST API:  http://127.0.0.1:5001/api/v10/*
  Gateway:   ws://127.0.0.1:5001/  ← Bot 应该连接这里
  
Bot (Serenity):
  REST API:  https://discord.com/api/v10/*  ← ❌ 错误的地址
  Gateway:   wss://gateway.discord.gg/      ← ❌ 错误的地址
```

**结果：** Bot 尝试连接真实的 Discord，而不是 Mock Server。

### 为什么 Telegram 可以工作？

Telegram 使用 `teloxide` crate，它支持通过 `TELEGRAM_API_URL` 环境变量配置自定义 API base URL：

```rust
// teloxide 支持自定义 API URL
let bot = Bot::from_env().set_api_url(Url::parse(&api_url).unwrap());
```

而 Serenity **没有**类似的 API。

## 💡 可能的解决方案

### 方案 1：使用 HTTP 代理拦截（推荐用于测试）

创建一个透明代理，将所有发往 `discord.com` 和 `gateway.discord.gg` 的请求重定向到 Mock Server：

```python
# proxy_server.py
import mitmproxy.http
from mitmproxy import ctx

def request(flow: mitmproxy.http.HTTPFlow):
    if flow.request.host in ["discord.com", "gateway.discord.gg"]:
        flow.request.host = "127.0.0.1"
        flow.request.port = 5001
```

然后设置环境变量：
```bash
export HTTPS_PROXY=http://127.0.0.1:8080
export HTTP_PROXY=http://127.0.0.1:8080
```

**优点：** 不需要修改 Serenity 或 Bot 代码
**缺点：** 需要额外的代理服务，增加复杂度

### 方案 2：修改 /etc/hosts（简单但不灵活）

```bash
# /etc/hosts
127.0.0.1 discord.com
127.0.0.1 gateway.discord.gg
```

**优点：** 简单直接
**缺点：** 
- 需要 root 权限
- 影响系统全局
- 无法区分端口（Mock Server 在 5001，真实 Discord 在 443）

### 方案 3：Fork Serenity 并添加自定义 Gateway URL 支持（长期方案）

修改 Serenity 源码，添加 `ClientBuilder::gateway_url()` 方法：

```rust
// 伪代码
let client = Client::builder(&token, intents)
    .gateway_url("ws://127.0.0.1:5001")  // ← 新增 API
    .event_handler(handler)
    .await?;
```

**优点：** 最干净的解决方案
**缺点：** 需要维护 fork 版本，等待上游合并

### 方案 4：使用 Mock 网络命名空间（Docker/Container）

在隔离的网络命名空间中运行 Bot，通过 iptables 规则重定向流量：

```bash
# 创建网络命名空间
ip netns add octos-test

# 重定向 Discord 流量到 Mock Server
ip netns exec octos-test iptables -t nat -A OUTPUT -p tcp -d discord.com --dport 443 -j DNAT --to-destination 127.0.0.1:5001
```

**优点：** 完全隔离，不影响主机
**缺点：** 复杂，需要容器化基础设施

### 方案 5：暂时禁用 Discord 测试（临时方案）

在修复之前，skip 所有 Discord 测试：

```python
@pytest.mark.skip(reason="Serenity SDK does not support custom Gateway URL")
def test_something():
    ...
```

**优点：** 立即可用
**缺点：** 无法测试 Discord 功能

## 🎯 推荐行动方案

### 短期（立即执行）

1. **采用方案 5**：暂时 skip Discord 测试，避免 CI/CD 失败
2. **记录 Issue**：在 GitHub 创建 issue 跟踪此问题
3. **文档化**：在 README 中说明 Discord 测试的限制

### 中期（1-2 周）

1. **实现方案 1**：创建简单的 HTTP 代理用于测试
2. **验证可行性**：确保代理能正确拦截并重定向 Discord 流量
3. **集成到测试框架**：自动启动/停止代理

### 长期（1-2 月）

1. **贡献上游**：向 Serenity 提交 PR 添加自定义 Gateway URL 支持
2. **或者 Fork**：如果上游不接受，维护一个轻量级 fork
3. **完善测试**：恢复所有 Discord 测试

## 📝 相关代码位置

### 需要修改的文件

1. **Octos 主仓库** (`/Volumes/AppleData/octos`):
   - `crates/octos-bus/src/discord_channel.rs` - Discord channel 实现
   - `crates/octos-cli/src/commands/gateway/adapters/discord.rs` - Discord adapter 注册

2. **测试仓库** (`/Volumes/AppleData/octos-test`):
   - `bot_mock_test/mock_discord.py` - Mock Discord Server
   - `test_run.py` - 测试运行器
   - `bot_mock_test/test_discord.py` - Discord 测试用例

### 关键代码片段

**当前实现（有问题）：**
```rust
// crates/octos-bus/src/discord_channel.rs
pub fn new(token: &str, ...) -> Self {
    let http = Arc::new(Http::new(token));  // ← 硬编码使用真实 Discord
    // ...
}

async fn start(&self, ...) -> Result<()> {
    let mut client = Client::builder(&self.token, intents)  // ← 硬编码 Gateway URL
        .event_handler(handler)
        .await?;
    client.start().await?;  // ← 连接到 wss://gateway.discord.gg
    Ok(())
}
```

**理想实现（需要 Serenity 支持）：**
```rust
pub fn with_gateway_url(token: &str, gateway_url: &str, ...) -> Self {
    // ...
}

async fn start(&self, ...) -> Result<()> {
    let mut client = Client::builder(&self.token, intents)
        .gateway_url(&self.gateway_url)  // ← 自定义 Gateway URL
        .event_handler(handler)
        .await?;
    client.start().await?;  // ← 连接到 ws://127.0.0.1:5001
    Ok(())
}
```

## 🔗 参考资料

- [Serenity GitHub](https://github.com/serenity-rs/serenity)
- [Serenity Documentation](https://docs.rs/serenity/)
- [Discord Developer Documentation - Gateway](https://discord.com/developers/docs/topics/gateway)
- [teloxide Custom API URL](https://docs.rs/teloxide/latest/teloxide/struct.Bot.html#method.set_api_url)

## 📊 影响范围

- **测试覆盖率**：Discord channel 功能完全未测试
- **CI/CD**：Discord 测试始终失败/skip
- **开发体验**：无法在本地验证 Discord 功能
- **生产风险**：Discord 相关 bug 可能未被发现

---

**创建时间：** 2026-04-28  
**最后更新：** 2026-04-28  
**状态：** 待解决
