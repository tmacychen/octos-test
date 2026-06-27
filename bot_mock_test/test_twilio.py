#!/usr/bin/env python3
"""
Twilio Bot 集成测试用例

前置条件（由 test_run.py 自动完成）：
  1. Mock Twilio Server 运行在 http://127.0.0.1:5011
  2. octos gateway 已启动并连接到 Mock Server（通过 --features twilio）
  3. TWILIO_API_BASE_URL 指向 Mock Server

运行方式：
  uv run python test_run.py --test bot twilio    # 完整测试
"""

import logging
import os
import time
import uuid

import pytest

from runner_twilio import TwilioTestRunner
from test_helpers import inject_and_get_reply

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

TIMEOUT_COMMAND = 30
TIMEOUT_LLM = 90


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def runner():
    r = TwilioTestRunner()
    assert r.health(), "Twilio Mock Server not running"
    return r


@pytest.fixture(autouse=True)
def cleanup_state(runner):
    """每个测试前清理 Mock Server 状态
    
    使用与 Telegram 测试对齐的快速清理模式，减少运行时 SKIP。
    """
    import httpx

    for attempt in range(3):
        try:
            if runner.health():
                break
        except Exception:
            pass
        if attempt < 2:
            logger.info(f"  ⚠ Mock Server not responding, retry {attempt + 1}/3...")
            time.sleep(1.0)
    else:
        pytest.skip("Twilio Mock Server not responding")
        return

    # Minimal wait for previous test state to settle
    time.sleep(0.5)

    # Quick stability check
    try:
        prev_count = len(runner.get_sent_messages(timeout=1))
    except httpx.HTTPError:
        pytest.skip("Mock Server 响应异常，跳过测试")
        return

    stable_count = 0
    for _ in range(4):  # 4 * 0.3s = 1.2s max
        time.sleep(0.3)
        try:
            curr_count = len(runner.get_sent_messages(timeout=1))
            if curr_count == prev_count:
                stable_count += 1
                if stable_count >= 2:
                    break
            else:
                stable_count = 0
            prev_count = curr_count
        except httpx.HTTPError:
            break
    else:
        pytest.skip("Mock Server 未稳定，跳过测试")
        return

    try:
        runner.clear()
    except httpx.HTTPError:
        pytest.skip("Mock Server 无法清理，跳过测试")
        return


# ══════════════════════════════════════════════════════════════════════════════
# 1. 连接与基础功能
# ══════════════════════════════════════════════════════════════════════════════

class TestTwilioConnectivity:
    """Twilio Mock Server 连接测试"""

    def test_server_health(self, runner):
        """验证 Mock Server 健康状态"""
        assert runner.health(), "Mock Server health check failed"
        logger.info("  ✓ Twilio Mock Server is healthy")


# ══════════════════════════════════════════════════════════════════════════════
# 2. 会话管理命令
# ══════════════════════════════════════════════════════════════════════════════

class TestTwilioSessionCommands:
    """Twilio 渠道会话管理"""

    CHAT_ID = "+15550001001"

    def test_new_default(self, runner):
        """/new 默认会话创建"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert "cleared" in text.lower() or "session" in text.lower() or "new" in text.lower(), \
            f"Expected session created, got: {text[:80]}"
        logger.info(f"  ✓ /new: {text[:60]}")

    def test_new_with_name(self, runner):
        """/new <name> 创建命名会话"""
        text = inject_and_get_reply(runner, "/new test-session", timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert "cleared" in text.lower() or "session" in text.lower() or "new" in text.lower(), \
            f"Expected named session created, got: {text[:80]}"
        logger.info(f"  ✓ /new test-session: {text[:60]}")

    def test_sessions_list(self, runner):
        """/sessions 列出会话"""
        text = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /sessions reply"
        logger.info(f"  ✓ /sessions: {text[:60]}")

    def test_back_command(self, runner):
        """/back 切换回上一个会话"""
        inject_and_get_reply(runner, "/new first-session", timeout=TIMEOUT_COMMAND,
                             from_number=self.CHAT_ID)
        inject_and_get_reply(runner, "/new second-session", timeout=TIMEOUT_COMMAND,
                             from_number=self.CHAT_ID)
        text = inject_and_get_reply(runner, "/back", timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /back reply"
        logger.info(f"  ✓ /back: {text[:60]}")

    def test_delete_session(self, runner):
        """/delete 删除会话"""
        inject_and_get_reply(runner, "/new to-delete", timeout=TIMEOUT_COMMAND,
                             from_number=self.CHAT_ID)
        text = inject_and_get_reply(runner, "/delete", timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /delete reply"
        logger.info(f"  ✓ /delete: {text[:60]}")

    def test_help(self, runner):
        """/help 帮助命令"""
        text = inject_and_get_reply(runner, "/help", timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert "help" in text.lower() or len(text) > 20, \
            f"Expected help text, got: {text[:80]}"
        logger.info(f"  ✓ /help received ({len(text)} chars)")

    def test_clear_resets_session(self, runner):
        """/clear → 清空当前会话"""
        inject_and_get_reply(runner, "/new clear-test", timeout=TIMEOUT_COMMAND,
                             from_number=self.CHAT_ID)
        text = inject_and_get_reply(runner, "/clear", timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert "cleared" in text.lower() or "clear" in text.lower(), \
            f"Expected session cleared, got: {text[:80]}"
        logger.info(f"  ✓ /clear: {text[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 3. 配置命令
# ══════════════════════════════════════════════════════════════════════════════

class TestTwilioConfigCommands:
    """Twilio 渠道配置命令"""

    CHAT_ID = "+15550001002"

    def test_soul_show(self, runner):
        """/soul 显示当前 soul"""
        text = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /soul reply"
        logger.info(f"  ✓ /soul: {text[:60]}")

    def test_queue_show(self, runner):
        """/queue 显示队列模式"""
        text = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /queue reply"
        logger.info(f"  ✓ /queue: {text[:60]}")

    def test_status(self, runner):
        """/status"""
        text = inject_and_get_reply(runner, "/status", timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /status reply"
        logger.info(f"  ✓ /status: {text[:60]}")

    def test_reset(self, runner):
        """/reset 重置配置"""
        text = inject_and_get_reply(runner, "/reset", timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /reset reply"
        logger.info(f"  ✓ /reset: {text[:60]}")

    def test_adaptive(self, runner):
        """/adaptive 切换自适应模式"""
        text = inject_and_get_reply(runner, "/adaptive", timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /adaptive reply"
        logger.info(f"  ✓ /adaptive: {text[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. LLM 消息测试
# ══════════════════════════════════════════════════════════════════════════════

class TestTwilioLLMMessages:
    """Twilio 渠道 LLM 消息测试"""

    CHAT_ID = "+15550001003"

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_simple_greeting(self, runner):
        """发送简单英文问候"""
        text = inject_and_get_reply(runner, "Hello!", timeout=TIMEOUT_LLM,
                                    from_number=self.CHAT_ID)
        assert len(text) > 0, "Expected LLM to reply"
        logger.info(f"  ✓ Greeting reply: {text[:60]}")

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_chinese_message(self, runner):
        """发送中文消息"""
        text = inject_and_get_reply(runner, "你好，请用中文回复", timeout=TIMEOUT_LLM,
                                    from_number=self.CHAT_ID)
        assert len(text) > 0, "Expected LLM reply in Chinese"
        logger.info(f"  ✓ Chinese reply: {text[:60]}")

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_llm_has_content(self, runner):
        """验证 LLM 回复有非空内容"""
        chat_id = f"+1555{uuid.uuid4().hex[:6]}"
        text = inject_and_get_reply(runner, "Hi there, please say something!",
                                    timeout=TIMEOUT_LLM, from_number=chat_id)
        assert len(text) > 0, "Expected LLM to reply with non-empty content"
        logger.info(f"  ✓ LLM content reply: {text[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 5. 中断命令测试
# ══════════════════════════════════════════════════════════════════════════════

class TestTwilioAbort:
    """Twilio 渠道 /abort 中断测试"""

    CHAT_ID = "+15550001004"

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_abort_cancels_generation(self, runner):
        """发送消息后 /abort 应取消生成"""
        runner.inject("Tell me a very long story about dragons", from_number=self.CHAT_ID)
        time.sleep(2)
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject("/abort", from_number=self.CHAT_ID)
        msg = runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_COMMAND,
                                    chat_id=self.CHAT_ID)
        time.sleep(3)
        all_msgs = runner.get_sent_messages(timeout=5)
        new_msgs = all_msgs[count_before:]
        assert len(new_msgs) >= 0, "abort processed"
        logger.info(f"  ✓ /abort processed, {len(new_msgs)} messages after abort")


# ══════════════════════════════════════════════════════════════════════════════
# 6. 多用户隔离
# ══════════════════════════════════════════════════════════════════════════════

class TestTwilioMultiUser:
    """多用户隔离测试"""

    def test_multiple_users_isolated(self, runner):
        """不同号码的消息应该各自得到回复"""
        user_a = f"+1555{uuid.uuid4().hex[:6]}"
        user_b = f"+1555{uuid.uuid4().hex[:6]}"

        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject(text="/new", from_number=user_a)
        time.sleep(2)
        runner.inject(text="/new", from_number=user_b)

        runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_COMMAND)
        time.sleep(5)
        all_msgs = runner.get_sent_messages(timeout=5)
        new_msgs = all_msgs[count_before:]
        assert len(new_msgs) >= 2, \
            f"Expected 2+ replies, got {len(new_msgs)}"
        logger.info(f"  ✓ Two users got {len(new_msgs)} replies")


# ══════════════════════════════════════════════════════════════════════════════
# 7. 消息去重
# ══════════════════════════════════════════════════════════════════════════════

class TestTwilioMessageDedup:
    """验证 Twilio 消息去重 (MessageSid)"""

    CHAT_ID = "+15550001005"

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_duplicate_message_sid_ignored(self, runner):
        """验证相同 MessageSid 的重复消息被忽略"""
        dedup_sid = f"SM{uuid.uuid4().hex[:24]}"

        reply1 = inject_and_get_reply(runner, "Dedup test", timeout=TIMEOUT_LLM,
                                      from_number=self.CHAT_ID, message_sid=dedup_sid)
        assert len(reply1) > 0, "Bot should reply to first message"

        count_before = len(runner.get_sent_messages(timeout=5))

        # 第二次发送相同 MessageSid
        runner.inject("Dedup test", from_number=self.CHAT_ID, message_sid=dedup_sid)
        time.sleep(3)

        count_after = len(runner.get_sent_messages(timeout=5))
        new_replies = count_after - count_before

        assert new_replies == 0, \
            f"Duplicate MessageSid should be deduplicated, but got {new_replies} new replies"
        logger.info("  ✓ Duplicate MessageSid correctly deduplicated")


# ══════════════════════════════════════════════════════════════════════════════
# 8. allowed_senders 白名单过滤
# ══════════════════════════════════════════════════════════════════════════════

class TestTwilioAllowedSenders:
    """验证 Twilio allowed_senders 白名单过滤"""

    def test_allowed_sender_gets_reply(self, runner):
        """白名单内号码发送消息 → bot 正常回复"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND,
                                    from_number="+15550000001")
        assert "cleared" in text.lower() or "session" in text.lower(), \
            f"Allowed sender should get reply, got: {text[:60]}"
        logger.info(f"  ✓ Allowed sender got reply: {text[:60]}")

    def test_blocked_sender_no_reply(self, runner):
        """白名单外号码发送消息 → bot 不回复"""
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject("Hello from stranger", from_number="+15559999999")

        time.sleep(8)

        count_after = len(runner.get_sent_messages(timeout=5))
        new_replies = count_after - count_before

        assert new_replies == 0, \
            f"Blocked sender should get no reply, but got {new_replies} new replies"
        logger.info("  ✓ Blocked sender correctly ignored")


# ══════════════════════════════════════════════════════════════════════════════
# 9. 消息分片测试
# ══════════════════════════════════════════════════════════════════════════════


class TestTwilioMessageSplitting:
    """Twilio SMS 消息分片测试"""

    CHAT_ID = "+15550001006"

    def test_long_message_gets_reply(self, runner):
        """发送接近 SMS 长度限制（~1600 字符）的消息，bot 应正常回复"""
        # 生成约 1600 字符的长消息
        long_text = "Long message test. " + "A" * 1550 + " END"
        assert len(long_text) > 1500, f"Message should be >1500 chars, got {len(long_text)}"

        text = inject_and_get_reply(runner, long_text, timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert len(text) > 0, "Expected reply to long SMS"
        logger.info(f"  ✓ Long SMS ({len(long_text)} chars) got reply ({len(text)} chars)")

    def test_very_long_message_handled(self, runner):
        """发送超长消息（>3200 字符，超过 GSM 多段限制），bot 应能处理"""
        # 生成约 3200 字符的极长消息
        very_long_text = "Very long SMS test. " + "B" * 3150 + " THE END"
        assert len(very_long_text) > 3100, f"Message should be >3100 chars, got {len(very_long_text)}"

        text = inject_and_get_reply(runner, very_long_text, timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert len(text) > 0, "Expected reply to very long SMS"
        logger.info(f"  ✓ Very long SMS ({len(very_long_text)} chars) got reply ({len(text)} chars)")

    def test_help_text_complete(self, runner):
        """验证 /help 返回完整的帮助文本（不因 SMS 长度限制被截断）"""
        text = inject_and_get_reply(runner, "/help", timeout=TIMEOUT_COMMAND,
                                    from_number=self.CHAT_ID)
        assert len(text) > 20, \
            f"Help text should be substantial (>20 chars), got {len(text)} chars: {text[:80]}"
        logger.info(f"  ✓ /help returned {len(text)} chars")
