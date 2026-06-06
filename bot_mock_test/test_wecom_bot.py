#!/usr/bin/env python3
"""
WeCom Bot (群机器人) E2E 测试

测试 octos wecom-bot 通道的 WebSocket 长连接协议：
  - aibot_subscribe 认证
  - ping/pong 心跳
  - aibot_msg_callback 消息接收
  - aibot_send_msg 消息发送
  - aibot_respond_msg 流式回复

测试拓扑:
  Mock Server (port 5008)  ←WS→  octos gateway  ←注入→  test runner

前置条件:
  - mock_wecom_bot.py Mock Server 已在 port 5008 运行
  - octos gateway 已启动并连接 Mock Server
  - 设置 WECOM_BOT_WS_URL=ws://127.0.0.1:5008/ws 环境变量
  - 设置 WECOM_BOT_SECRET 环境变量 (任意外秘钥均可)
"""

import json
import logging
import os
import time
import uuid

import pytest

from runner_wecom_bot import WeComBotTestRunner

logger = logging.getLogger(__name__)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def runner():
    """Create a WeComBotTestRunner for the mock server."""
    base_url = os.environ.get("MOCK_BASE_URL", "http://127.0.0.1:5008")
    return WeComBotTestRunner(base_url)


@pytest.fixture(autouse=True)
def clear_state(runner):
    """Clear mock server state before each test."""
    runner.clear()
    yield


# ── Helpers ────────────────────────────────────────────────────────────────────


def wait_for_condition(condition_fn, timeout=15, interval=0.5, description="condition"):
    """Wait for a condition to be True, polling at the given interval."""
    start = time.time()
    while time.time() - start < timeout:
        result = condition_fn()
        if result:
            return result
        time.sleep(interval)
    raise TimeoutError(f"Timed out waiting for: {description}")


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
        resp = runner.get_subscribe_state()
        assert "subscribed" in resp
        assert "ws_connections" in resp

    def test_subscription_state(self, runner):
        """验证 octos 已经通过 WebSocket 连接并成功订阅。

        一旦 octos 连接，Mock Server 会收到 aibot_subscribe 帧，
        返回 ACK (errcode=0)，subscribed 状态应为 True。
        """
        def check():
            state = runner.get_subscribe_state()
            return state.get("subscribed", False)

        result = wait_for_condition(
            check, timeout=20, description="octos subscribe via WebSocket"
        )
        assert result, "octos should be subscribed to WeCom Bot mock"

    def test_multiple_connections_tracked(self, runner):
        """验证 Mock Server 正确追踪 WebSocket 连接数量。"""
        subscribe_state = runner.get_subscribe_state()
        assert subscribe_state["ws_connections"] >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 消息收发
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComBotSessionCommands:
    """基础消息流程测试"""

    def test_simple_text_message(self, runner):
        """注入一条纯文本消息，验证 octos 回复 aibot_send_msg 帧。"""
        sender = f"user_{uuid.uuid4().hex[:6]}"
        runner.inject(text="Simple ping test", sender=sender)

        def check():
            msgs = get_sent(runner)
            return any(
                "pong" in m.get("content", "").lower()
                or "ping" in m.get("content", "").lower()
                for m in msgs
            ) if msgs else None

        result = wait_for_condition(check, timeout=60, description="bot reply to simple message")
        assert result, "Expected bot to reply to simple text message"

    def test_normal_conversation(self, runner):
        """注入一条普通对话消息，验证 octos 有回复内容。"""
        sender = f"user_{uuid.uuid4().hex[:6]}"
        runner.inject(text="Hello! What is 2+2?", sender=sender)

        def check():
            msgs = get_sent(runner)
            return any(
                len(m.get("content", "")) >= 1
                for m in msgs
            ) if msgs else None

        result = wait_for_condition(check, timeout=60, description="bot reply with content")
        assert result, "Expected bot to reply with non-empty content"

    def test_reply_to_mention(self, runner):
        """注入一条@机器人的消息，验证 octos 回复。"""
        sender = f"user_{uuid.uuid4().hex[:6]}"
        runner.inject(text="@bot what's the weather like?", sender=sender)

        def check():
            msgs = get_sent(runner)
            return bool(msgs)

        result = wait_for_condition(check, timeout=60, description="bot reply to mention")
        assert result, "Expected bot to reply when mentioned"

    def test_multiple_users_isolated(self, runner):
        """两个不同用户的消息应该各自得到回复，不会混淆。"""
        user_a = f"user_a_{uuid.uuid4().hex[:4]}"
        user_b = f"user_b_{uuid.uuid4().hex[:4]}"

        runner.inject(text="Hello for user A", sender=user_a)
        time.sleep(2)
        runner.inject(text="Hello for user B", sender=user_b)

        def check():
            msgs = get_sent(runner)
            return len(msgs) >= 2

        result = wait_for_condition(check, timeout=60, description="two users get replies")
        assert result, f"Expected 2+ replies, got {len(get_sent(runner))}"

    @pytest.mark.skip(reason="WeCom Bot channel 命令回复格式需 mock 适配，待排查")
    def test_clear_resets_session(self, runner):
        """/clear → 'Session cleared.' 清空当前会话"""
        sender = f"user_{uuid.uuid4().hex[:6]}"
        # 先创建会话
        runner.inject(text="/new clear-test", sender=sender)
        # 等待 /new 的回复
        def check_new():
            msgs = get_sent(runner)
            return bool(msgs)
        wait_for_condition(check_new, timeout=30, description="session created")

        # 记录当前消息数
        count_before = len(get_sent(runner))

        # 发送 /clear
        runner.inject(text="/clear", sender=sender)

        def check_clear():
            msgs = get_sent(runner)
            new_msgs = msgs[count_before:] if len(msgs) > count_before else []
            return any("Session cleared" in m.get("content", "") or "cleared" in m.get("content", "").lower()
                       for m in new_msgs) if new_msgs else None

        result = wait_for_condition(check_clear, timeout=30, description="clear response")
        assert result, "Expected 'Session cleared' reply after /clear"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 配置测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComBotConfig:
    """Allowe d_senders 白名单"""

    def test_basic_connectivity_config(self, runner):
        """验证基本连接和消息收发功能正常（连接验证）。"""
        sender = f"cfg_user_{uuid.uuid4().hex[:6]}"
        runner.inject(text="config test", sender=sender)

        def check():
            msgs = get_sent(runner)
            return bool(msgs)

        result = wait_for_condition(check, timeout=60, description="config basic test")
        assert result, "Expected bot to reply in basic config mode"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. LLM 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComBotLLM:
    """LLM 响应内容验证（需要有效的 OPENAI_API_KEY）"""

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_llm_meaningful_reply(self, runner):
        """验证 LLM 对有意义的问题给出回复（不检查具体关键词）。"""
        sender = f"llm_user_{uuid.uuid4().hex[:6]}"
        runner.inject(
            text="What is the capital of France? Please answer in one word.",
            sender=sender,
        )

        def check():
            msgs = get_sent(runner)
            return any(len(m.get("content", "")) > 0 for m in msgs)

        result = wait_for_condition(check, timeout=120, description="LLM reply to question")
        assert result, "Expected LLM to reply to a question"

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_llm_chinese_reply(self, runner):
        """验证 LLM 支持中文问答（不检查具体关键词）。"""
        sender = f"cn_user_{uuid.uuid4().hex[:6]}"
        runner.inject(text="中国的首都是哪里？请用一个词回答。", sender=sender)

        def check():
            msgs = get_sent(runner)
            return any(len(m.get("content", "")) > 0 for m in msgs)

        result = wait_for_condition(check, timeout=120, description="LLM reply in Chinese")
        assert result, "Expected LLM to reply to a Chinese question"

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_llm_reply_has_content(self, runner):
        """验证 LLM 回复有非空内容（不检查具体关键词，仅验证可回复性）。"""
        sender = f"llm_content_{uuid.uuid4().hex[:6]}"
        runner.inject(text="Hi there!", sender=sender)

        def check():
            msgs = get_sent(runner)
            return any(len(m.get("content", "")) > 0 for m in msgs)

        result = wait_for_condition(check, timeout=120, description="LLM reply with content")
        assert result, "Expected LLM to reply with non-empty content"


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
        """验证 LLM 回复以流式片段（aibot_respond_msg）发送。

        流式回复应该包含多个 chunk，最后一个带有 finish=True。
        """
        sender = f"stream_user_{uuid.uuid4().hex[:6]}"
        runner.inject(
            text="Write a short story about a robot, 3 sentences.",
            sender=sender,
        )

        def check():
            chunks = get_streams(runner)
            return any(ch.get("finish") for ch in chunks)

        result = wait_for_condition(check, timeout=90, description="stream chunks with finish")
        assert result, "Expected streaming chunks with finish=True"

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_stream_final_content_nonempty(self, runner):
        """验证流式回复的最终内容非空。"""
        sender = f"stream2_user_{uuid.uuid4().hex[:6]}"
        runner.inject(
            text="Count to 5 in words: one two three four five.",
            sender=sender,
        )

        def check():
            chunks = get_streams(runner)
            # Find the final chunk
            for ch in reversed(chunks):
                if ch.get("finish"):
                    return len(ch.get("content", "")) > 0
            return None

        result = wait_for_condition(check, timeout=90, description="non-empty final stream content")
        assert result, "Expected non-empty content in final stream chunk"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 清理与断开
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComBotDedup:
    """消息去重"""

    def test_duplicate_message_id(self, runner):
        """发送两条不同内容但相同 chatid 的消息，验证两者都获得回复（重复基于 msgid，
        不同的 session 消息会被分别处理）。"""
        sender = f"dedup_user_{uuid.uuid4().hex[:6]}"
        runner.inject(text="First message hello", sender=sender)
        time.sleep(3)
        runner.inject(text="Second message world", sender=sender)

        def check():
            msgs = get_sent(runner)
            return len(msgs) >= 2

        result = wait_for_condition(check, timeout=60, description="two messages from same user")
        assert result, f"Expected 2+ replies for 2 messages, got {len(get_sent(runner))}"
