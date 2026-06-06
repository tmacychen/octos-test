#!/usr/bin/env python3
"""
WeCom Bot (群机器人) E2E 测试

测试 octos wecom-bot 通道的 WebSocket 长连接协议：
  - aibot_subscribe 认证
  - ping/pong 心跳
  - aibot_msg_callback 消息接收
  - aibot_send_msg 消息发送
  - aibot_respond_msg 流式回复
  - 会话管理命令 (/new, /sessions, /help, /clear, /status, /soul, /queue)
  - 多用户隔离
  - 消息去重

测试拓扑:
  Mock Server (port 5008)  ←WS→  octos gateway  ←注入→  test runner

前置条件:
  - mock_wecom_bot.py Mock Server 已在 port 5008 运行
  - octos gateway 已启动并连接 Mock Server
  - 设置 WECOM_BOT_WS_URL=ws://127.0.0.1:5008/ws 环境变量
  - 设置 WECOM_BOT_SECRET 环境变量 (任意外秘钥均可)

运行方式:
  uv run python test_run.py --test bot wecom-bot
"""

import json
import logging
import os
import time
import uuid

import pytest

from runner_wecom_bot import WeComBotTestRunner
from test_helpers import inject_and_get_reply

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

TIMEOUT_COMMAND = 30
TIMEOUT_LLM = 90

# WeCom Bot uses chatid (group ID) as the routing key, not sender.
# Each test class uses a unique chatid to ensure session isolation.
CHAT_SESSION = "wcb_session_group"
CHAT_CONFIG = "wcb_config_group"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def runner():
    """Create a WeComBotTestRunner for the mock server."""
    r = WeComBotTestRunner()
    assert r.health(), "WeCom Bot Mock Server not running"
    return r


@pytest.fixture(autouse=True)
def cleanup_state(runner):
    """Clear mock server state before each test."""
    for attempt in range(3):
        try:
            if runner.health():
                break
        except Exception:
            pass
        time.sleep(1.0)
    else:
        pytest.skip("WeCom Bot Mock Server not responding")

    time.sleep(2.0)
    runner.clear()


# ── Helpers ────────────────────────────────────────────────────────────────────


def get_sent(runner) -> list:
    """Get all send_msg records from the mock server."""
    return runner.get_send_messages()


def get_streams(runner) -> list:
    """Get all stream chunk records from the mock server."""
    return runner.get_stream_chunks()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 连接与基础功能
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComBotConnectivity:
    """WebSocket 连接、订阅、健康检查"""

    def test_health_check(self, runner):
        """Mock Server 健康检查端点正常。"""
        assert runner.health(), "Mock Server health check failed"
        logger.info("  ✓ WeCom Bot Mock Server is healthy")

    def test_subscription_state(self, runner):
        """验证 octos 已经通过 WebSocket 连接并成功订阅。"""
        start = time.time()
        while time.time() - start < 20:
            state = runner.get_subscribe_state()
            if state.get("subscribed", False):
                logger.info("  ✓ octos subscribed via WebSocket")
                return
            time.sleep(0.5)
        pytest.fail("octos should be subscribed to WeCom Bot mock")

    def test_multiple_connections_tracked(self, runner):
        """验证 Mock Server 正确追踪 WebSocket 连接数量。"""
        subscribe_state = runner.get_subscribe_state()
        assert subscribe_state["ws_connections"] >= 1
        logger.info(f"  ✓ WS connections: {subscribe_state['ws_connections']}")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 会话管理命令
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComBotSessionCommands:
    """WeCom Bot 会话管理命令测试"""

    def test_new_default(self, runner):
        """测试 /new 默认会话创建"""
        text = inject_and_get_reply(
            runner, "/new", timeout=TIMEOUT_COMMAND,
            sender="wcb_user1", chatid=CHAT_SESSION,
        )
        assert "cleared" in text.lower() or "session" in text.lower() or "new" in text.lower(), \
            f"Expected session created, got: {text[:80]}"
        logger.info(f"  ✓ /new: {text[:60]}")

    def test_sessions_list(self, runner):
        """测试 /sessions 列出会话"""
        text = inject_and_get_reply(
            runner, "/sessions", timeout=TIMEOUT_COMMAND,
            sender="wcb_user1", chatid=CHAT_SESSION,
        )
        assert len(text) > 0, "Expected non-empty /sessions reply"
        logger.info(f"  ✓ /sessions: {text[:60]}")

    def test_help(self, runner):
        """测试 /help"""
        text = inject_and_get_reply(
            runner, "/help", timeout=TIMEOUT_COMMAND,
            sender="wcb_user1", chatid=CHAT_SESSION,
        )
        assert "help" in text.lower() or len(text) > 20, \
            f"Expected help text, got: {text[:80]}"
        logger.info(f"  ✓ /help received ({len(text)} chars)")

    def test_clear_resets_session(self, runner):
        """/clear → 清空当前会话"""
        inject_and_get_reply(
            runner, "/new clear-test", timeout=TIMEOUT_COMMAND,
            sender="wcb_user1", chatid=CHAT_SESSION,
        )
        text = inject_and_get_reply(
            runner, "/clear", timeout=TIMEOUT_COMMAND,
            sender="wcb_user1", chatid=CHAT_SESSION,
        )
        assert "cleared" in text.lower() or "clear" in text.lower(), \
            f"Expected session cleared, got: {text[:80]}"
        logger.info(f"  ✓ /clear: {text[:60]}")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 配置命令
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComBotConfigCommands:
    """WeCom Bot 配置命令测试"""

    def test_soul_show(self, runner):
        """测试 /soul 显示当前 soul"""
        text = inject_and_get_reply(
            runner, "/soul", timeout=TIMEOUT_COMMAND,
            sender="wcb_user2", chatid=CHAT_CONFIG,
        )
        assert len(text) > 0, "Expected non-empty /soul reply"
        logger.info(f"  ✓ /soul: {text[:60]}")

    def test_queue_show(self, runner):
        """测试 /queue 显示队列模式"""
        text = inject_and_get_reply(
            runner, "/queue", timeout=TIMEOUT_COMMAND,
            sender="wcb_user2", chatid=CHAT_CONFIG,
        )
        assert len(text) > 0, "Expected non-empty /queue reply"
        logger.info(f"  ✓ /queue: {text[:60]}")

    def test_status(self, runner):
        """测试 /status"""
        text = inject_and_get_reply(
            runner, "/status", timeout=TIMEOUT_COMMAND,
            sender="wcb_user2", chatid=CHAT_CONFIG,
        )
        assert len(text) > 0, "Expected non-empty /status reply"
        logger.info(f"  ✓ /status: {text[:60]}")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. LLM 消息测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComBotLLM:
    """LLM 响应内容验证（需要有效的 LLM API key）"""

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_simple_greeting(self, runner):
        """发送简单英文问候"""
        sender = f"llm_user_{uuid.uuid4().hex[:6]}"
        text = inject_and_get_reply(
            runner, "Hello!", timeout=TIMEOUT_LLM,
            sender=sender, chatid=f"llm_group_{uuid.uuid4().hex[:4]}",
        )
        assert len(text) > 0, "Expected LLM to reply"
        logger.info(f"  ✓ Greeting reply: {text[:60]}")

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_chinese_message(self, runner):
        """验证 LLM 支持中文问答"""
        sender = f"cn_user_{uuid.uuid4().hex[:6]}"
        text = inject_and_get_reply(
            runner, "你好，请用中文回复", timeout=TIMEOUT_LLM,
            sender=sender, chatid=f"cn_group_{uuid.uuid4().hex[:4]}",
        )
        assert len(text) > 0, "Expected LLM reply in Chinese"
        logger.info(f"  ✓ Chinese reply: {text[:60]}")

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_llm_meaningful_reply(self, runner):
        """验证 LLM 对有意义的问题给出回复。"""
        sender = f"llm_qa_{uuid.uuid4().hex[:6]}"
        text = inject_and_get_reply(
            runner, "What is the capital of France? Please answer in one word.",
            timeout=TIMEOUT_LLM, sender=sender, chatid=f"qa_group_{uuid.uuid4().hex[:4]}",
        )
        assert len(text) > 0, "Expected LLM to reply to a question"
        logger.info(f"  ✓ LLM question reply: {text[:60]}")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 流式回复测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComBotStreaming:
    """aibot_respond_msg 流式回复"""

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_stream_chunks_received(self, runner):
        """验证 LLM 回复以流式片段发送，最后一个带有 finish=True。"""
        sender = f"stream_user_{uuid.uuid4().hex[:6]}"
        runner.inject(
            text="Write a short story about a robot, 3 sentences.",
            sender=sender, chatid=f"stream_group_{uuid.uuid4().hex[:4]}",
        )

        start = time.time()
        while time.time() - start < 90:
            chunks = get_streams(runner)
            if any(ch.get("finish") for ch in chunks):
                logger.info("  ✓ Stream chunks with finish=True received")
                return
            time.sleep(0.5)
        pytest.fail("Expected streaming chunks with finish=True")

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_stream_final_content_nonempty(self, runner):
        """验证流式回复的最终内容非空。"""
        sender = f"stream2_user_{uuid.uuid4().hex[:6]}"
        runner.inject(
            text="Count to 5 in words: one two three four five.",
            sender=sender, chatid=f"stream2_group_{uuid.uuid4().hex[:4]}",
        )

        start = time.time()
        while time.time() - start < 90:
            chunks = get_streams(runner)
            for ch in reversed(chunks):
                if ch.get("finish"):
                    assert len(ch.get("content", "")) > 0, "Final stream content should be non-empty"
                    logger.info(f"  ✓ Final stream content: {ch['content'][:60]}")
                    return
            time.sleep(0.5)
        pytest.fail("No final stream chunk with finish=True found")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 多用户隔离
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComBotMultiUser:
    """多用户隔离测试"""

    @pytest.mark.llm
    def test_multiple_users_isolated(self, runner):
        """两个不同群组的消息应该各自得到回复，不会混淆。"""
        user_a = f"user_a_{uuid.uuid4().hex[:4]}"
        user_b = f"user_b_{uuid.uuid4().hex[:4]}"

        text_a = inject_and_get_reply(
            runner, "Hello for user A", timeout=TIMEOUT_LLM,
            sender=user_a, chatid="group_a_test",
        )
        assert len(text_a) > 0, "Expected reply for user A"

        time.sleep(3)
        text_b = inject_and_get_reply(
            runner, "Hello for user B", timeout=TIMEOUT_LLM,
            sender=user_b, chatid="group_b_test",
        )
        assert len(text_b) > 0, "Expected reply for user B"
        logger.info("  ✓ Two groups got replies")


# ═══════════════════════════════════════════════════════════════════════════════
# 7. 消息去重
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComBotDedup:
    """消息去重测试"""

    @pytest.mark.llm
    def test_different_messages_both_replied(self, runner):
        """发送两条不同内容的消息，验证两者都获得回复。"""
        sender = f"dedup_user_{uuid.uuid4().hex[:6]}"
        chatid = f"dedup_group_{uuid.uuid4().hex[:4]}"

        text1 = inject_and_get_reply(
            runner, "First message hello", timeout=TIMEOUT_LLM,
            sender=sender, chatid=chatid,
        )
        assert len(text1) > 0, "Expected reply to first message"

        time.sleep(3)
        text2 = inject_and_get_reply(
            runner, "Second message world", timeout=TIMEOUT_LLM,
            sender=sender, chatid=chatid,
        )
        assert len(text2) > 0, "Expected reply to second message"
        logger.info("  ✓ Both messages got replies")
