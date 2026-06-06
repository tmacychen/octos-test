#!/usr/bin/env python3
"""
WhatsApp Bot 集成测试

测试 octos WhatsApp Bot 的核心功能：
  - 会话管理（/new, /switch, /sessions, /back, /delete）
  - 配置命令（/queue, /soul, /status, /adaptive, /reset, /help）
  - 基本 LLM 消息
  - 多用户隔离
"""

import logging
import os
import uuid
import pytest
import time
import httpx
from test_helpers import inject_and_get_reply
from runner_whatsapp import WhatsAppTestRunner

logger = logging.getLogger(__name__)

# ── 超时配置 ──────────────────────────────────────────────────────────────────
TIMEOUT_COMMAND = 50
TIMEOUT_LLM     = 90

# ── 测试用户 ──────────────────────────────────────────────────────────────────
USER_A = "12025550101@s.whatsapp.net"
USER_B = "12025550102@s.whatsapp.net"

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def runner():
    """创建 WhatsApp 测试运行器（session 级，一次创建供所有测试复用）。"""
    r = WhatsAppTestRunner()
    assert r.health(), "Mock Server 未运行"
    return r


@pytest.fixture(autouse=True)
def clear_before(runner):
    """每个测试前清理 Mock Server 状态。"""
    # Health check
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if runner.health():
                break
        except Exception:
            pass
        if attempt < max_retries - 1:
            logger.info(f"  ⚠ Mock Server not responding, retry {attempt + 1}/{max_retries}...")
            time.sleep(1.0)
    else:
        pytest.skip("Mock Server 崩溃，无法恢复")

    # Wait for stable state
    try:
        prev_count = len(runner.get_sent_messages(timeout=2))
    except httpx.HTTPError:
        pytest.skip("Mock Server 响应异常，跳过测试")
        return

    for _ in range(5):
        time.sleep(0.3)
        try:
            curr_count = len(runner.get_sent_messages(timeout=2))
            if curr_count == prev_count:
                break
            prev_count = curr_count
        except httpx.HTTPError:
            break

    # Clean state
    try:
        runner.clear()
    except httpx.HTTPError:
        pytest.skip("Mock Server 无法清理，跳过测试")
        return

    # Reset session
    try:
        inject_and_get_reply(runner, "/reset", timeout=3, sender=f"reset_cleanup@im.whatsapp")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# 会话管理测试
# ══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppSessionCommands:
    """会话管理命令测试"""

    @pytest.mark.llm
    def test_new_creates_session(self, runner):
        """/new → 'Session cleared.'"""
        reply = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "应返回会话确认"
        assert "clear" in reply.lower() or "session" in reply.lower(), \
            f"预期含 session/clear，实际: {reply[:80]}"

    @pytest.mark.llm
    def test_new_with_invalid_name(self, runner):
        """/new (空名) → 提示或创建默认"""
        # 两次 /new 验证会话切换
        reply1 = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND, sender=USER_A)
        reply2 = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply1 and reply2

    @pytest.mark.llm
    def test_switch_session(self, runner):
        """创建命名会话后切换"""
        inject_and_get_reply(runner, "/new research", timeout=TIMEOUT_COMMAND, sender=USER_A)
        reply = inject_and_get_reply(runner, "/s research", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "应返回切换确认"

    @pytest.mark.llm
    def test_sessions_list(self, runner):
        """/sessions → 显示会话列表"""
        inject_and_get_reply(runner, "/new topic-a", timeout=TIMEOUT_COMMAND, sender=USER_A)
        inject_and_get_reply(runner, "/new topic-b", timeout=TIMEOUT_COMMAND, sender=USER_A)
        reply = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "应返回会话列表"

    @pytest.mark.llm
    def test_back_to_previous(self, runner):
        """/back → 回到上一个会话"""
        inject_and_get_reply(runner, "/new first", timeout=TIMEOUT_COMMAND, sender=USER_A)
        inject_and_get_reply(runner, "/new second", timeout=TIMEOUT_COMMAND, sender=USER_A)
        reply = inject_and_get_reply(runner, "/back", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "应返回切换确认"

    @pytest.mark.llm
    def test_delete_session(self, runner):
        """/delete <name> → 'Deleted session: <name>'"""
        inject_and_get_reply(runner, "/new to-delete", timeout=TIMEOUT_COMMAND, sender=USER_A)
        reply = inject_and_get_reply(runner, "/delete to-delete", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "应返回删除确认"

    def test_clear_resets_session(self, runner):
        """/clear → 'Session cleared.' 清空当前会话"""
        inject_and_get_reply(runner, "/new clear-test", timeout=TIMEOUT_COMMAND, sender=USER_A)
        reply = inject_and_get_reply(runner, "/clear", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply == "Session cleared.", f"实际回复: {reply}"


# ══════════════════════════════════════════════════════════════════════════════
# 基本消息测试
# ══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppBasicMessages:
    """基本消息处理测试"""

    @pytest.mark.llm
    def test_empty_message(self, runner):
        """空消息 → 应返回提示"""
        reply = inject_and_get_reply(runner, "   ", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "空消息也应触发回复"

    @pytest.mark.llm
    def test_special_characters(self, runner):
        """特殊字符测试"""
        reply = inject_and_get_reply(runner, "Hello! @#$% ^&*() +-={}[]", timeout=TIMEOUT_LLM, sender=USER_A)
        assert reply, "应正确处理特殊字符"

    @pytest.mark.llm
    def test_unicode_emoji(self, runner):
        """Unicode/表情符号测试"""
        reply = inject_and_get_reply(runner, "Hello 👋 🌍 你好 🎉", timeout=TIMEOUT_LLM, sender=USER_A)
        assert reply, "应正确处理 unicode"


# ══════════════════════════════════════════════════════════════════════════════
# 配置命令测试
# ══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppConfigCommands:
    """配置命令测试"""

    @pytest.mark.llm
    def test_queue_mode_show(self, runner):
        """/queue → 显示当前队列模式"""
        reply = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "应返回队列模式"

    @pytest.mark.llm
    def test_queue_mode_set(self, runner):
        """/queue followup → 'Queue mode set'"""
        reply = inject_and_get_reply(runner, "/queue followup", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "应确认队列模式变更"

    @pytest.mark.llm
    def test_soul_show_empty(self, runner):
        """/soul → 显示当前 soul"""
        reply = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "应返回 soul 内容"

    @pytest.mark.llm
    def test_soul_set(self, runner):
        """/soul <text> → 'Soul updated.'"""
        reply = inject_and_get_reply(runner, "/soul You are a helpful assistant.", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "应确认 soul 更新"

    @pytest.mark.llm
    def test_status_command(self, runner):
        """/status → 显示状态"""
        reply = inject_and_get_reply(runner, "/status", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "应返回状态信息"

    @pytest.mark.llm
    def test_adaptive_command(self, runner):
        """/adaptive → 'Adaptive routing is not enabled.'"""
        reply = inject_and_get_reply(runner, "/adaptive", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "应返回 adaptive 状态"

    @pytest.mark.llm
    def test_reset_command(self, runner):
        """/reset → 重置确认"""
        reply = inject_and_get_reply(runner, "/reset", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "应返回重置确认"

    @pytest.mark.llm
    def test_help_command(self, runner):
        """/help → 帮助信息"""
        reply = inject_and_get_reply(runner, "/help", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert reply, "应返回帮助信息"


# ══════════════════════════════════════════════════════════════════════════════
# LLM 消息测试
# ══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppLLMMessages:
    """LLM 基本消息回复测试"""

    @pytest.mark.llm
    def test_regular_message(self, runner):
        """普通消息"""
        reply = inject_and_get_reply(runner, "Hello!", timeout=TIMEOUT_LLM, sender=USER_A)
        assert reply, "应返回 LLM 回复"
        logger.info(f"  💬 LLM 回复: {reply[:100]}")

    @pytest.mark.llm
    def test_chinese_message(self, runner):
        """中文消息"""
        reply = inject_and_get_reply(runner, "你好，请用中文回复", timeout=TIMEOUT_LLM, sender=USER_A)
        assert reply, "应返回 LLM 回复"
        logger.info(f"  💬 LLM 回复: {reply[:100]}")


# ══════════════════════════════════════════════════════════════════════════════
# 多用户隔离测试
# ══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppMultiUser:
    """多用户 session 隔离测试"""

    @pytest.mark.llm
    def test_two_users_independent_sessions(self, runner):
        """两个用户独立 session，互不干扰"""
        reply_a = inject_and_get_reply(runner, "/new user-a-session", timeout=TIMEOUT_COMMAND, sender=USER_A)
        reply_b = inject_and_get_reply(runner, "/new user-b-session", timeout=TIMEOUT_COMMAND, sender=USER_B)
        assert reply_a and reply_b

        # 各用户在自己的 session 中发消息
        inject_and_get_reply(runner, "/s user-a-session", timeout=TIMEOUT_COMMAND, sender=USER_A)
        reply_a2 = inject_and_get_reply(runner, "This is user A", timeout=TIMEOUT_LLM, sender=USER_A)
        assert reply_a2

        reply_b2 = inject_and_get_reply(runner, "This is user B", timeout=TIMEOUT_LLM, sender=USER_B)
        assert reply_b2


# ══════════════════════════════════════════════════════════════════════════════
# 中断命令测试
# ══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppAbortCommands:
    """中断命令测试"""

    @pytest.mark.llm
    def test_abort_multilanguage(self, runner):
        """中英文中断命令"""
        for cmd in ["/abort", "/abort ", "/stop", "/取消", "/stop "] :
            reply = inject_and_get_reply(runner, cmd, timeout=TIMEOUT_COMMAND, sender=USER_A)
            assert reply, f"命令 '{cmd}' 应被识别为中断"


# ══════════════════════════════════════════════════════════════════════════════
# 媒体消息测试（WhatsApp 特色）
# ══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppMediaMessages:
    """媒体消息处理测试"""

    @pytest.mark.llm
    def test_image_with_caption(self, runner):
        """带说明文字的图片消息"""
        reply = inject_and_get_reply(runner, "What's in this image?", timeout=TIMEOUT_LLM, sender=USER_A, message_type="image")
        assert reply, "图片消息应触发 LLM 回复"

    @pytest.mark.llm
    def test_audio_message(self, runner):
        """语音消息（模拟模式下只验证文本回复）"""
        reply = inject_and_get_reply(runner, "I sent a voice message, what do you think?", timeout=TIMEOUT_LLM, sender=USER_A)
        assert reply, "语音消息相关文本应触发 LLM 回复"


# ══════════════════════════════════════════════════════════════════════════════
# 消息去重测试
# ══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppMessageDedup:
    """消息去重测试"""

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_duplicate_message_id_ignored(self, runner):
        """相同 message_id 的重复消息应被忽略"""
        dedup_msg_id = f"msg_dedup_{uuid.uuid4().hex[:12]}"
        dedup_user = f"dedup_{uuid.uuid4().hex[:6]}@s.whatsapp.net"

        # 第一次发送，应收到回复
        reply1 = inject_and_get_reply(runner, "Dedup test", timeout=TIMEOUT_LLM,
                                       sender=dedup_user, message_id=dedup_msg_id)
        assert len(reply1) > 0, "Bot should reply to first message"

        # 记录当前消息数
        count_before = len(runner.get_sent_messages(timeout=5))

        # 第二次发送相同 message_id
        runner.inject("Dedup test", sender=dedup_user, message_id=dedup_msg_id)

        # 等待确保去重生效
        time.sleep(3)

        count_after = len(runner.get_sent_messages(timeout=5))
        new_replies = count_after - count_before

        assert new_replies == 0, \
            f"Duplicate message_id should be deduplicated, but got {new_replies} new replies"
        logger.info("  ✓ Duplicate message_id correctly deduplicated")


# ══════════════════════════════════════════════════════════════════════════════
# allowed_senders 白名单过滤测试
# ══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppAllowedSenders:
    """allowed_senders 白名单过滤测试"""

    def test_allowed_sender_gets_reply(self, runner):
        """白名单内用户发送消息 → bot 正常回复"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND, sender=USER_A)
        assert "clear" in text.lower() or "session" in text.lower(), \
            f"Allowed sender should get reply, got: {text[:60]}"
        logger.info(f"  ✓ Allowed sender ({USER_A}) got reply: {text[:60]}")

    def test_blocked_sender_no_reply(self, runner):
        """白名单外用户发送消息 → bot 不回复"""
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject("Hello from stranger", sender="stranger_not_allowed@s.whatsapp.net")

        # 等待足够时间确认 bot 不回复
        time.sleep(8)

        count_after = len(runner.get_sent_messages(timeout=5))
        new_replies = count_after - count_before

        assert new_replies == 0, \
            f"Blocked sender should get no reply, but got {new_replies} new replies"
        logger.info("  ✓ Blocked sender correctly ignored")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "llm"])
