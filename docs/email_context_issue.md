# Email Channel Context Bloat / Email 渠道上下文膨胀

### 中文

**问题：** Email 渠道用发件人地址作为 chat_id，同一人的多封邮件累积到同一个 session。没有上下文压缩（compaction），token 数持续增长直到超过模型限制（131K），后续 LLM 请求全部 400 失败。

测试中 token 增长趋势：220K → 437K → 873K → 1.7M

**影响：** 所有邮箱均受影响（QQ / Gmail 等），是 octos session 管理问题，与提供商无关。163 邮箱因 Coremail IMAP 拦截 `SELECT INBOX` 完全无法使用（"Unsafe Login"），但这是独立问题。

**建议修复：**
1. Email 渠道启用 session compaction
2. 或按邮件 Message-ID / 主题隔离 session
3. 或超限后自动截断早期历史

---

### English

**Problem:** The Email channel uses the sender's address as the chat_id, so all emails from the same person go into a single session. Without context compaction, the token count keeps growing until it exceeds the model's limit (131K), causing all subsequent LLM requests to fail with 400 errors.

Observed growth: 220K → 437K → 873K → 1.7M tokens

**Impact:** Affects all email providers (QQ, Gmail, etc.) — this is an octos session management issue, not provider-specific. 163 mail is additionally broken due to Coremail IMAP blocking `SELECT INBOX` ("Unsafe Login"), but that's a separate issue.

**Suggested fixes:**
1. Enable session compaction for the Email channel
2. Isolate sessions by Message-ID or subject
3. Auto-truncate early history when exceeding the token limit
