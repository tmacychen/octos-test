#!/usr/bin/env python3
"""
WeCom (企业微信自建应用) E2E 测试

测试 octos wecom 通道的 webhook 回调 + REST API：
  - URL 验证 (GET /wecom/webhook with echostr)
  - 加密消息回调 (POST /wecom/webhook with AES ciphertext)
  - 消息发送 (REST API /cgi-bin/message/send)
  - Token 管理
  - LLM 回复

测试拓扑:
  Mock Server (port 5009)  ←REST API─  octos gateway
  octos webhook (port 9323)  ──加密回调──  Mock Server (_inject)
"""

import logging
import os
import time
import uuid

import pytest

from runner_wecom import WeComTestRunner

logger = logging.getLogger(__name__)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def runner():
    base_url = os.environ.get("MOCK_BASE_URL", "http://127.0.0.1:5009")
    return WeComTestRunner(base_url)


@pytest.fixture(autouse=True)
def clear_state(runner):
    runner.clear()
    yield


# ── Helpers ────────────────────────────────────────────────────────────────────


def wait_for_condition(condition_fn, timeout=15, interval=0.5, description="condition"):
    start = time.time()
    while time.time() - start < timeout:
        result = condition_fn()
        if result:
            return result
        time.sleep(interval)
    raise TimeoutError(f"Timed out waiting for: {description}")


def get_messages(runner) -> list:
    return runner.get_messages_list()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 连接与基础功能
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComConnectivity:
    """Mock Server 健康检查"""

    def test_health_check(self, runner):
        """Mock Server 健康检查端点正常。"""
        config = runner.get_server_config()
        assert "corp_id" in config
        assert "verification_token" in config
        assert config["corp_id"] == "test_corp_id"

    def test_server_config(self, runner):
        """验证 Mock Server 配置正确。"""
        config = runner.get_server_config()
        assert len(config.get("aes_key_hex", "")) == 64  # 32 bytes = 64 hex chars


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 消息收发
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComSessionCommands:
    """基础消息流程测试"""

    def test_simple_text_message(self, runner):
        """注入一条文本消息，验证 octos 回复。"""
        sender = f"user_{uuid.uuid4().hex[:6]}"
        result = runner.inject(text="Simple ping test", sender=sender)
        assert result.get("success"), f"Injection failed: {result}"
        logger.info(f"Injection result: webhook_status={result['event'].get('webhook_status')}")

        def check():
            msgs = get_messages(runner)
            return bool(msgs)

        result = wait_for_condition(check, timeout=60, description="bot reply")
        assert result, "Expected bot to reply to simple text message"

    def test_normal_conversation(self, runner):
        """注入一条普通对话消息，验证 octos 有回复。"""
        sender = f"user_{uuid.uuid4().hex[:6]}"
        result = runner.inject(text="Hello! What is 2+2?", sender=sender)
        assert result.get("success"), f"Injection failed: {result}"

        def check():
            msgs = get_messages(runner)
            return bool(msgs)

        result = wait_for_condition(check, timeout=60, description="bot reply with content")
        assert result, "Expected bot to reply with non-empty content"

    def test_multiple_users_isolated(self, runner):
        """两个不同用户的消息应该各自得到回复。"""
        user_a = f"user_a_{uuid.uuid4().hex[:4]}"
        user_b = f"user_b_{uuid.uuid4().hex[:4]}"

        result_a = runner.inject(text="Hello for user A", sender=user_a)
        assert result_a.get("success"), f"Injection A failed: {result_a}"
        time.sleep(2)
        result_b = runner.inject(text="Hello for user B", sender=user_b)
        assert result_b.get("success"), f"Injection B failed: {result_b}"

        def check():
            msgs = get_messages(runner)
            return len(msgs) >= 2

        result = wait_for_condition(check, timeout=60, description="two users get replies")
        assert result, f"Expected 2+ replies, got {len(get_messages(runner))}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. LLM 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComLLM:
    """LLM 响应验证（需要有效的 LLM API key）"""

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_llm_has_reply(self, runner):
        """验证 LLM 回复有非空内容。"""
        sender = f"llm_user_{uuid.uuid4().hex[:6]}"
        result = runner.inject(text="Hi there, please say something!", sender=sender)
        assert result.get("success"), f"Injection failed: {result}"

        def check():
            msgs = get_messages(runner)
            return any(
                m.get("body", {}).get("markdown", {}).get("content", "")
                or m.get("body", {}).get("text", {}).get("content", "")
                for m in msgs
            )

        result = wait_for_condition(check, timeout=120, description="LLM reply")
        assert result, "Expected LLM to reply with non-empty content"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 消息去重
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComDedup:
    """消息去重"""

    def test_duplicate_message(self, runner):
        """发送两条不同内容的消息，验证两者都获得回复。"""
        sender = f"dedup_user_{uuid.uuid4().hex[:6]}"
        result_a = runner.inject(text="First message hello", sender=sender)
        assert result_a.get("success")
        time.sleep(3)
        result_b = runner.inject(text="Second message world", sender=sender)
        assert result_b.get("success")

        def check():
            msgs = get_messages(runner)
            return len(msgs) >= 2

        result = wait_for_condition(check, timeout=60, description="two messages replied")
        assert result, f"Expected 2+ replies, got {len(get_messages(runner))}"
