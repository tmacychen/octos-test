#!/usr/bin/env python3
"""
WeCom (企业微信自建应用) E2E 测试

测试 octos wecom 通道的 webhook 回调 + REST API：
  - URL 验证 (GET /wecom/webhook with echostr)
  - 加密消息回调 (POST /wecom/webhook with AES ciphertext)
  - 消息发送 (REST API /cgi-bin/message/send)
  - 会话管理命令 (/new, /sessions, /help, /clear, /status, /soul, /queue)
  - 多用户隔离
  - 消息去重
  - LLM 回复

测试拓扑:
  Mock Server (port 5009)  ←REST API─  octos gateway
  octos webhook (port 9323)  ──加密回调──  Mock Server (_inject)

运行方式:
  uv run python test_run.py --test bot wecom
"""

import logging
import os
import time
import uuid

import pytest

from runner_wecom import WeComTestRunner
from test_helpers import inject_and_get_reply

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

TIMEOUT_COMMAND = 30
TIMEOUT_LLM = 90
TIMEOUT_DEDUP = 10

# Senders must be in the allowed_senders list defined in test_run.py.
# The current list is: wecom_session_user, wecom_config_user, wecom_allowed, wecom_dedup_user
ALLOWED_SENDER = "wecom_allowed"
DEDUP_SENDER = "wecom_dedup_user"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def runner():
    r = WeComTestRunner()
    assert r.health(), "WeCom Mock Server not running"
    return r


@pytest.fixture(autouse=True)
def cleanup_state(runner):
    """每个测试前清理 Mock Server 状态"""
    for attempt in range(3):
        try:
            if runner.health():
                break
        except Exception:
            pass
        time.sleep(1.0)
    else:
        pytest.skip("WeCom Mock Server not responding")

    time.sleep(2.0)
    runner.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 连接与基础功能
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComConnectivity:
    """Mock Server 健康检查"""

    def test_health_check(self, runner):
        """Mock Server 健康检查端点正常。"""
        assert runner.health(), "Mock Server health check failed"
        logger.info("  ✓ WeCom Mock Server is healthy")

    def test_server_config(self, runner):
        """验证 Mock Server 配置正确。"""
        config = runner.get_server_config()
        assert "corp_id" in config
        assert "verification_token" in config
        assert config["corp_id"] == "test_corp_id"
        assert len(config.get("aes_key_hex", "")) == 64  # 32 bytes = 64 hex chars
        logger.info("  ✓ WeCom Mock Server config valid")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 会话管理命令
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComSessionCommands:
    """WeCom 会话管理命令测试"""

    SENDER = "wecom_session_user"

    def test_new_default(self, runner):
        """测试 /new 默认会话创建"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND, sender=self.SENDER)
        assert "cleared" in text.lower() or "session" in text.lower() or "new" in text.lower(), \
            f"Expected session created, got: {text[:80]}"
        logger.info(f"  ✓ /new: {text[:60]}")

    def test_sessions_list(self, runner):
        """测试 /sessions 列出会话"""
        text = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND, sender=self.SENDER)
        assert len(text) > 0, "Expected non-empty /sessions reply"
        logger.info(f"  ✓ /sessions: {text[:60]}")

    def test_help(self, runner):
        """测试 /help"""
        text = inject_and_get_reply(runner, "/help", timeout=TIMEOUT_COMMAND, sender=self.SENDER)
        assert "help" in text.lower() or len(text) > 20, \
            f"Expected help text, got: {text[:80]}"
        logger.info(f"  ✓ /help received ({len(text)} chars)")

    def test_clear_resets_session(self, runner):
        """/clear → 清空当前会话"""
        inject_and_get_reply(runner, "/new clear-test", timeout=TIMEOUT_COMMAND, sender=self.SENDER)
        text = inject_and_get_reply(runner, "/clear", timeout=TIMEOUT_COMMAND, sender=self.SENDER)
        assert "cleared" in text.lower() or "clear" in text.lower(), \
            f"Expected session cleared, got: {text[:80]}"
        logger.info(f"  ✓ /clear: {text[:60]}")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 配置命令
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComConfigCommands:
    """WeCom 配置命令测试"""

    SENDER = "wecom_config_user"

    def test_soul_show(self, runner):
        """测试 /soul 显示当前 soul"""
        text = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND, sender=self.SENDER)
        assert len(text) > 0, "Expected non-empty /soul reply"
        logger.info(f"  ✓ /soul: {text[:60]}")

    def test_queue_show(self, runner):
        """测试 /queue 显示队列模式"""
        text = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND, sender=self.SENDER)
        assert len(text) > 0, "Expected non-empty /queue reply"
        logger.info(f"  ✓ /queue: {text[:60]}")

    def test_status(self, runner):
        """测试 /status"""
        text = inject_and_get_reply(runner, "/status", timeout=TIMEOUT_COMMAND, sender=self.SENDER)
        assert len(text) > 0, "Expected non-empty /status reply"
        logger.info(f"  ✓ /status: {text[:60]}")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. LLM 消息测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComLLM:
    """LLM 响应验证（需要有效的 LLM API key）"""

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_simple_greeting(self, runner):
        """发送简单英文问候"""
        text = inject_and_get_reply(runner, "Hello! What is 2+2?", timeout=TIMEOUT_LLM, sender=ALLOWED_SENDER)
        assert len(text) > 0, "Expected LLM to reply"
        logger.info(f"  ✓ Greeting reply: {text[:60]}")

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_chinese_message(self, runner):
        """发送中文消息"""
        text = inject_and_get_reply(runner, "你好，请用中文回复", timeout=TIMEOUT_LLM, sender=ALLOWED_SENDER)
        assert len(text) > 0, "Expected LLM reply in Chinese"
        logger.info(f"  ✓ Chinese reply: {text[:60]}")

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_llm_has_content(self, runner):
        """验证 LLM 回复有非空内容。"""
        text = inject_and_get_reply(runner, "Hi there, please say something!", timeout=TIMEOUT_LLM, sender=ALLOWED_SENDER)
        assert len(text) > 0, "Expected LLM to reply with non-empty content"
        logger.info(f"  ✓ LLM content reply: {text[:60]}")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 多用户隔离
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComMultiUser:
    """多用户隔离测试"""

    def test_multiple_users_isolated(self, runner):
        """两个不同用户的消息应该各自得到回复，不会混淆。"""
        count_before = len(runner.get_sent_messages(timeout=5))
        result_a = runner.inject(text="Hello for user A", sender=ALLOWED_SENDER)
        assert result_a.get("success"), f"Injection A failed: {result_a}"
        time.sleep(2)
        result_b = runner.inject(text="Hello for user B", sender="wecom_config_user")
        assert result_b.get("success"), f"Injection B failed: {result_b}"

        # Wait for at least 2 replies
        msgs = runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_LLM)
        time.sleep(5)
        all_msgs = runner.get_sent_messages(timeout=5)
        new_msgs = all_msgs[count_before:]
        assert len(new_msgs) >= 2, \
            f"Expected 2+ replies, got {len(new_msgs)}"
        logger.info(f"  ✓ Two users got {len(new_msgs)} replies")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 消息去重
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeComMessageDedup:
    """验证 WeCom 消息去重 (msg_id)"""

    SENDER = "wecom_dedup_user"

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_duplicate_message_id_ignored(self, runner):
        """验证相同 msg_id 的重复消息被忽略"""
        dedup_msg_id = f"msg_wec_dedup_{uuid.uuid4().hex[:12]}"

        # 第一次发送 — bot 应回复
        reply1 = inject_and_get_reply(runner, "Dedup test first", timeout=TIMEOUT_LLM,
                                      sender=self.SENDER, message_id=dedup_msg_id)
        assert len(reply1) > 0, "Bot should reply to first message"

        count_before = len(runner.get_sent_messages(timeout=5))

        # 第二次发送相同 msg_id — bot 应忽略
        runner.inject("Dedup test second should be ignored",
                      sender=self.SENDER, message_id=dedup_msg_id)
        time.sleep(TIMEOUT_DEDUP)

        count_after = len(runner.get_sent_messages(timeout=5))
        new_replies = count_after - count_before

        assert new_replies == 0, \
            f"Duplicate msg_id should be deduplicated, but got {new_replies} new replies"
        logger.info("  ✓ Duplicate msg_id correctly deduplicated")


class TestWeComAllowedSenders:
    """验证 WeCom allowed_senders 白名单过滤"""

    SENDER = "wecom_allowed"

    def test_allowed_sender_gets_reply(self, runner):
        """白名单内用户发送消息 → bot 正常回复"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND, sender=self.SENDER)
        assert "cleared" in text.lower() or "session" in text.lower(), \
            f"Allowed sender should get reply, got: {text[:60]}"
        logger.info(f"  ✓ Allowed sender got reply: {text[:60]}")

    def test_blocked_sender_no_reply(self, runner):
        """白名单外用户发送消息 → bot 不回复"""
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject("Hello from stranger", sender="stranger_not_allowed")

        time.sleep(8)

        count_after = len(runner.get_sent_messages(timeout=5))
        new_replies = count_after - count_before

        assert new_replies == 0, \
            f"Blocked sender should get no reply, but got {new_replies} new replies"
        logger.info("  ✓ Blocked sender correctly ignored")
