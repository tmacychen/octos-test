#!/usr/bin/env python3
"""
LINE Bot 集成测试用例

前置条件（由 test_run.py 自动完成）：
  1. Mock LINE Server 运行在 http://127.0.0.1:5007
  2. octos gateway 已启动并连接到 Mock Server（通过 --features line）
  3. LINE_API_BASE_URL 指向 Mock Server

运行方式：
  uv run python test_run.py --test bot line    # 完整测试
"""

import pytest
import time
import logging
import httpx
from runner_line import LineTestRunner
from test_helpers import inject_and_get_reply

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

TIMEOUT_COMMAND = 30
TIMEOUT_LLM = 90


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def runner():
    r = LineTestRunner()
    assert r.health(), "LINE Mock Server not running"
    return r


@pytest.fixture(autouse=True)
def cleanup_state(runner):
    """每个测试前清理 Mock Server 状态"""
    import time
    for attempt in range(3):
        try:
            if runner.health():
                break
        except Exception:
            pass
        time.sleep(1.0)
    else:
        pytest.skip("LINE Mock Server not responding")

    time.sleep(2.0)
    runner.clear()


# ══════════════════════════════════════════════════════════════════════════════
# 配置 & 连接测试
# ══════════════════════════════════════════════════════════════════════════════

class TestLineConnectivity:
    """LINE Mock Server 连接测试"""

    def test_server_health(self, runner):
        """验证 Mock Server 健康状态"""
        assert runner.health(), "Mock Server health check failed"
        logger.info("  ✓ LINE Mock Server is healthy")


# ══════════════════════════════════════════════════════════════════════════════
# 会话管理命令测试
# ══════════════════════════════════════════════════════════════════════════════

class TestLineSessionCommands:
    """LINE 渠道会话管理"""

    CHAT_ID = "U_line_test_1"

    def test_new_default(self, runner):
        """测试 /new 默认会话创建"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert "cleared" in text.lower(), f"Expected session cleared, got: {text[:60]}"
        logger.info(f"  ✓ /new: {text[:60]}")

    def test_sessions_list(self, runner):
        """测试 /sessions 列出会话"""
        text = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert len(text) > 0
        logger.info(f"  ✓ /sessions: {text[:60]}")

    def test_help(self, runner):
        """测试 /help"""
        text = inject_and_get_reply(runner, "/help", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert "help" in text.lower() or len(text) > 20
        logger.info(f"  ✓ /help received ({len(text)} chars)")

    def test_clear_resets_session(self, runner):
        """/clear → 'Session cleared.' 清空当前会话"""
        inject_and_get_reply(runner, "/new clear-test", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        text = inject_and_get_reply(runner, "/clear", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert text == "Session cleared.", f"实际回复: {text}"
        logger.info(f"  ✓ /clear: {text}")


# ══════════════════════════════════════════════════════════════════════════════
# 配置命令测试
# ══════════════════════════════════════════════════════════════════════════════

class TestLineConfigCommands:
    """LINE 渠道配置命令"""

    CHAT_ID = "U_line_test_2"

    def test_soul_show(self, runner):
        """测试 /soul 显示当前 soul"""
        text = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert len(text) > 0
        logger.info(f"  ✓ /soul: {text[:60]}")

    def test_queue_show(self, runner):
        """测试 /queue 显示队列模式"""
        text = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert len(text) > 0
        logger.info(f"  ✓ /queue: {text[:60]}")

    def test_status(self, runner):
        """测试 /status"""
        text = inject_and_get_reply(runner, "/status", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert len(text) > 0
        logger.info(f"  ✓ /status: {text[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# LLM 基本消息测试
# ══════════════════════════════════════════════════════════════════════════════

class TestLineLLMMessages:
    """LINE 渠道 LLM 消息测试"""

    CHAT_ID = "U_line_test_3"

    @pytest.mark.llm
    def test_simple_greeting(self, runner):
        """发送简单英文问候"""
        text = inject_and_get_reply(runner, "Hello!", timeout=TIMEOUT_LLM, chat_id=self.CHAT_ID)
        assert len(text) > 0
        logger.info(f"  ✓ Greeting reply: {text[:60]}")

    @pytest.mark.llm
    def test_chinese_message(self, runner):
        """发送中文消息"""
        text = inject_and_get_reply(runner, "你好，请用中文回复", timeout=TIMEOUT_LLM, chat_id=self.CHAT_ID)
        assert len(text) > 0
        logger.info(f"  ✓ Chinese reply: {text[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 消息去重测试
# ══════════════════════════════════════════════════════════════════════════════

class TestLineMessageDedup:
    """验证 LINE 消息去重 (MessageDedup)"""

    CHAT_ID = "U_line_dedup"

    @pytest.mark.llm
    def test_duplicate_message_id_ignored(self, runner):
        """验证相同 message_id 的重复消息被忽略"""
        import uuid
        import time

        dedup_msg_id = f"msg_dedup_{uuid.uuid4().hex[:12]}"

        # 第一次发送，应收到回复
        reply1 = inject_and_get_reply(runner, "Dedup test", timeout=TIMEOUT_LLM,
                                       chat_id=self.CHAT_ID, message_id=dedup_msg_id)
        assert len(reply1) > 0, "Bot should reply to first message"

        # 记录当前消息数
        count_before = len(runner.get_sent_messages(timeout=5))

        # 第二次发送相同 message_id
        runner.inject("Dedup test", chat_id=self.CHAT_ID, message_id=dedup_msg_id)

        # 等待确保去重生效
        time.sleep(3)

        count_after = len(runner.get_sent_messages(timeout=5))
        new_replies = count_after - count_before

        assert new_replies == 0, \
            f"Duplicate message_id should be deduplicated, but got {new_replies} new replies"
        logger.info(f"  ✓ Duplicate message_id correctly deduplicated")
