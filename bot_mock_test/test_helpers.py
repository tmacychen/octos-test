#!/usr/bin/env python3
"""
Bot Mock 测试共享工具函数。
"""

import time
from typing import Optional


def inject_and_get_reply(runner, text: str, timeout: int = 15, **inject_kwargs) -> str:
    """注入消息，记录注入前的消息数，等待新回复。

    inject_kwargs 会透传给 runner.inject()，各平台参数不同：
      - Telegram: chat_id=100, username="testuser"
      - Discord:  channel_id="1039178386623557754"
      - Matrix:   room_id="!test:localhost"
    默认值由各 runner.inject() 方法定义。
    """
    count_before = len(runner.get_sent_messages(timeout=5))
    runner.inject(text, **inject_kwargs)

    # Determine filter_id for wait_for_reply.
    # Priority: explicit routing keys > sender.
    # chatid (WeCom Bot), chat_id (Telegram), channel_id (Discord), room_id (Matrix),
    # group_openid (QQ Bot), from_number (Twilio)
    filter_id = (
        inject_kwargs.get("chatid")
        or inject_kwargs.get("chat_id")
        or inject_kwargs.get("channel_id")
        or inject_kwargs.get("room_id")
        or inject_kwargs.get("group_openid")
        or inject_kwargs.get("from_number")
        or inject_kwargs.get("sender")
    )
    msg = runner.wait_for_reply(count_before=count_before, timeout=timeout, chat_id=filter_id)
    
    # Truncate long messages in error output to avoid cluttering logs
    text_preview = text[:100] + "..." if len(text) > 100 else text
    assert msg is not None, f"Bot 未在 {timeout}s 内回复 '{text_preview}'"
    return msg["text"]


def wait_for_abort_reply(runner, count_before: int, timeout: int = 15, 
                         chat_id=None, cancel_keywords=None) -> dict:
    """等待 abort/cancel 响应，自动跳过流式状态消息和无关消息。
    
    Args:
        runner: Test runner instance
        count_before: 注入 abort 命令前的消息数量
        timeout: 最长等待时间（秒）
        chat_id: 频道/聊天 ID（用于过滤）
        cancel_keywords: 取消响应的关键词列表，默认为英文和中文
    
    Returns:
        匹配的消息字典
    
    Raises:
        AssertionError: 如果超时未收到取消响应
    """
    if cancel_keywords is None:
        cancel_keywords = [
            "🛑", "cancel", "cancelled", "取消", "已取消",
            "キャンセル", "Отменено"  # 日文和俄文
        ]
    
    # Skip streaming status messages
    streaming_status = [
        "Processing", "Deliberating", "Evaluating", "Connecting", 
        "Thinking", "Considering", "Analyzing", "Working"
    ]
    
    import time
    start_time = time.time()
    poll_interval = 0.5
    
    while time.time() - start_time < timeout:
        # Get all messages sent after count_before
        msgs = runner.get_sent_messages()
        new_msgs = msgs[count_before:]
        
        # Check each new message from oldest to newest
        for msg in new_msgs:
            text = msg["text"]
            
            # Skip streaming status messages
            if text in streaming_status:
                continue
            
            # Check if this is a cancel response
            text_lower = text.lower()
            has_cancel_keyword = any(kw.lower() in text_lower for kw in cancel_keywords if not kw.startswith("🛑"))
            has_emoji = "🛑" in text
            
            if has_cancel_keyword or has_emoji:
                return msg
        
        # No cancel response found yet, wait and retry
        time.sleep(poll_interval)
    
    # Timeout reached
    assert False, f"Timeout waiting for cancel response after {timeout}s. Last messages: {[m['text'][:50] for m in msgs[count_before:][-3:]]}"


def test_ws_reconnect_basic(runner, timeout_cmd: int = 30, **inject_kwargs) -> str:
    """通用的 WS 断线重连测试流程。

    步骤:
      1. 发送 /new 验证连接正常
      2. 断开 WS 连接
      3. 等待 bot 重连（15s 检测窗口）
      4. 再发 /new 验证重连成功

    注意: Discord mock 模式下（DISCORD_API_BASE_URL 已设），serenity 的
    ShardManager 重连时不使用 proxy Http，无法重连到 mock server。
    该情况下直接 pytest.skip。
    """
    import os

    # Discord mock mode: serenity reconnect doesn't honor proxy
    if os.environ.get("DISCORD_API_BASE_URL"):
        import pytest
        pytest.skip("Discord mock mode: serenity reconnect does not use proxy (mock)")

    import logging
    logger = logging.getLogger(__name__)

    # Step 1: Baseline — verify connection works
    text = inject_and_get_reply(runner, "/new", timeout=timeout_cmd, **inject_kwargs)
    assert "cleared" in text.lower() or "session" in text.lower() or "new" in text.lower(), \
        f"Baseline /new failed: {text[:80]}"
    logger.info(f"  Step 1 ✓ Baseline /new OK")

    # Step 2: Disconnect WS connections
    result = runner.disconnect_ws()
    logger.info(f"  Step 2 ✓ WS disconnect: {result}")

    # Step 3: Wait for bot to detect and reconnect
    import time
    logger.info("  Step 3 Waiting 15s for bot to reconnect...")
    time.sleep(15)

    # Step 4: Verify reconnection works
    reconnect_text = inject_and_get_reply(
        runner, "/new reconnect-test", timeout=timeout_cmd, **inject_kwargs,
    )
    assert "cleared" in reconnect_text.lower() or "session" in reconnect_text.lower() \
        or "new" in reconnect_text.lower(), \
        f"Expected bot to reply after reconnect, got: {reconnect_text[:80]}"
    logger.info(f"  Step 4 ✓ Reconnect verified: {reconnect_text[:60]}")
    return reconnect_text
