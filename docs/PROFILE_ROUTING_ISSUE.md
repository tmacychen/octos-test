# Feature Request: Profile Routing for Telegram and Discord Channels

## Summary

Telegram and Discord channels lack profile routing — all messages route to `_main` profile.
Matrix and API channels already implement this.

## Current Behavior

**telegram_channel.rs** (~L442): `InboundMessage.metadata` is empty `{}`
**discord_channel.rs** (~L159): metadata only has `message_id`/`guild_id`

Both lack `target_profile_id`, so `resolve_dispatch_profile_id()` always gets `None`.

## Reference: Matrix BotRouter

`matrix_channel.rs` has `BotRouter` with:
- `user_id` → `profile_id` mapping
- @mention routing
- room-based routing
- `target_profile_id` injected into metadata

## Expected

- Chat-based routing: `chat_id`/`channel_id` → profile_id
- `target_profile_id` in `InboundMessage.metadata`
- Configurable mapping

## Blocked Tests

- `test_soul_per_profile` (Telegram, Discord)
- `test_queue_mode_per_profile` (Telegram)

## Note

Gateway routing pipeline already handles `target_profile_id` from metadata
(`gateway_runtime.rs` ~L1766). Only channel-level injection is missing.
