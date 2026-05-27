# Email Channel: Outbound Reply Never Delivered

## Symptoms

When running `octos gateway` with the email channel, the gateway successfully polls the IMAP inbox (logs show `processed emails count=N`), but the sender never receives a "Re:" reply email. Specifically:

1. **No "Re:" reply arrives in the sender's inbox** (or in the bot's own inbox when sending to self)
2. **Gateway logs show NO SMTP send activity** — no `smtp_send`, `lettre`, or any outgoing mail-related logs appear
3. **IMAP polling works correctly** — `processed emails count=N` is logged, confirming the inbound email was fetched and forwarded
4. **No agent errors logged** — no `error!`, `warn!`, or panic messages related to the email channel or agent processing appear

## Root Cause

The root cause was identified as a bug in the gateway main loop's `tokio::select!` combined with the `Notify` future lifecycle.

### Primary Cause: Stalled Main Loop `tokio::select!`

In `gateway_runtime.rs`, the main message loop used this pattern:

```rust
let shutdown_notified = shutdown_notify.notified();
tokio::pin!(shutdown_notified);

let inbound = tokio::select! {
    biased;
    _ = &mut shutdown_notified => {
        if self.shutdown.load(Ordering::Acquire) { break; }
        continue;
    }
    msg = self.agent_handle.recv_inbound() => { ... }
};
```

`Notify::notified()` returns a **one-shot future**. After its first successful `poll`, it remains permanently in a "ready" state. Combined with `biased;` (which polls branches in declaration order), every subsequent loop iteration would immediately hit the always-ready `shutdown_notified` branch and `continue`, **never reaching the `recv_inbound()` branch**.

As a result, `InboundMessage`s sent by the email channel (via `tx.send(inbound).await`) were never received by the main loop, the agent was never triggered, and no `OutboundMessage` was ever generated — so `email_channel::send()` and `smtp_send()` were never called.

**Fix**: Create a fresh `Notified` future on each loop iteration instead of reusing a pinned one:

```rust
tokio::select! {
    _ = shutdown_notify.notified() => { ... }  // fresh each iteration
    msg = self.agent_handle.recv_inbound() => { ... }
}
```

### Secondary Cause: Self-Send Reply Loop

When the SMTP reply was eventually sent (to the same QQ email account), QQ mail marks the self-sent message as UNSEEN after approximately 30 seconds. The IMAP poll would then re-discover the reply as a new inbound email, causing the bot to repeatedly reply to its own replies — creating an infinite loop.

**Fix**: Added a filter in `email_channel.rs` to skip emails from the bot's own address with subjects starting with "Re:":

```rust
if is_bot_sender && subject.trim().to_lowercase().starts_with("re:") {
    continue;
}
```

### Minor Issue: Silently Swallowed IMAP STORE Error

`session.store(&seq_set, "+FLAGS (\\Seen)").await.ok();` used `.ok()` which silently dropped all errors, making it impossible to diagnose IMAP flag failures.

**Fix**: Changed `.ok()` to `if let Err(e) = ... { warn!(...) }`.

## Files Modified

| File | Change |
|------|--------|
| `crates/octos-cli/src/commands/gateway/gateway_runtime.rs` | Fix main loop `select!` — create fresh `Notified` each iteration, avoid pinned future |
| `crates/octos-bus/src/email_channel.rs` | Filter self-sent "Re:" replies to prevent infinite loop |
| `crates/octos-bus/src/email_channel.rs` | Log IMAP `STORE` errors instead of silently swallowing |

## Environment

build time :   Wed May 27 23:22:37 2026
