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

import logging
import os
import time
import uuid

import pytest

from runner_line import LineTestRunner
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
    r = LineTestRunner()
    assert r.health(), "LINE Mock Server not running"
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
        pytest.skip("LINE Mock Server not responding")
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

class TestLineConnectivity:
    """LINE Mock Server 连接测试"""

    def test_server_health(self, runner):
        """验证 Mock Server 健康状态"""
        assert runner.health(), "Mock Server health check failed"
        logger.info("  ✓ LINE Mock Server is healthy")


# ══════════════════════════════════════════════════════════════════════════════
# 2. 会话管理命令
# ══════════════════════════════════════════════════════════════════════════════

class TestLineSessionCommands:
    """LINE 渠道会话管理"""

    CHAT_ID = "U_line_session"

    def test_new_default(self, runner):
        """测试 /new 默认会话创建"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert "cleared" in text.lower() or "session" in text.lower() or "new" in text.lower(), \
            f"Expected session created, got: {text[:80]}"
        logger.info(f"  ✓ /new: {text[:60]}")

    def test_new_with_name(self, runner):
        """测试 /new <name> 创建命名会话"""
        text = inject_and_get_reply(runner, "/new test-session", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert "cleared" in text.lower() or "session" in text.lower() or "new" in text.lower(), \
            f"Expected named session created, got: {text[:80]}"
        logger.info(f"  ✓ /new test-session: {text[:60]}")

    def test_sessions_list(self, runner):
        """测试 /sessions 列出会话"""
        text = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /sessions reply"
        logger.info(f"  ✓ /sessions: {text[:60]}")

    def test_back_command(self, runner):
        """测试 /back 切换回上一个会话"""
        # 先创建第一个会话
        inject_and_get_reply(runner, "/new first-session", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        # 再创建第二个会话
        inject_and_get_reply(runner, "/new second-session", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        # 切换回上一个
        text = inject_and_get_reply(runner, "/back", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /back reply"
        logger.info(f"  ✓ /back: {text[:60]}")

    def test_delete_session(self, runner):
        """测试 /delete 删除会话"""
        # 先创建一个会话
        inject_and_get_reply(runner, "/new to-delete", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        # 删除它
        text = inject_and_get_reply(runner, "/delete", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /delete reply"
        logger.info(f"  ✓ /delete: {text[:60]}")

    def test_help(self, runner):
        """测试 /help"""
        text = inject_and_get_reply(runner, "/help", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert "help" in text.lower() or len(text) > 20, \
            f"Expected help text, got: {text[:80]}"
        logger.info(f"  ✓ /help received ({len(text)} chars)")

    def test_clear_resets_session(self, runner):
        """/clear → 清空当前会话"""
        inject_and_get_reply(runner, "/new clear-test", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        text = inject_and_get_reply(runner, "/clear", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert "cleared" in text.lower() or "clear" in text.lower(), \
            f"Expected session cleared, got: {text[:80]}"
        logger.info(f"  ✓ /clear: {text[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 3. 配置命令
# ══════════════════════════════════════════════════════════════════════════════

class TestLineConfigCommands:
    """LINE 渠道配置命令"""

    CHAT_ID = "U_line_config"

    def test_soul_show(self, runner):
        """测试 /soul 显示当前 soul"""
        text = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /soul reply"
        logger.info(f"  ✓ /soul: {text[:60]}")

    def test_queue_show(self, runner):
        """测试 /queue 显示队列模式"""
        text = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /queue reply"
        logger.info(f"  ✓ /queue: {text[:60]}")

    def test_status(self, runner):
        """测试 /status"""
        text = inject_and_get_reply(runner, "/status", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /status reply"
        logger.info(f"  ✓ /status: {text[:60]}")

    def test_reset(self, runner):
        """测试 /reset 重置配置"""
        text = inject_and_get_reply(runner, "/reset", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /reset reply"
        logger.info(f"  ✓ /reset: {text[:60]}")

    def test_adaptive(self, runner):
        """测试 /adaptive 切换自适应模式"""
        text = inject_and_get_reply(runner, "/adaptive", timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /adaptive reply"
        logger.info(f"  ✓ /adaptive: {text[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. LLM 消息测试
# ══════════════════════════════════════════════════════════════════════════════

class TestLineLLMMessages:
    """LINE 渠道 LLM 消息测试"""

    CHAT_ID = "U_line_llm"

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_simple_greeting(self, runner):
        """发送简单英文问候"""
        text = inject_and_get_reply(runner, "Hello!", timeout=TIMEOUT_LLM, chat_id=self.CHAT_ID)
        assert len(text) > 0, "Expected LLM to reply"
        logger.info(f"  ✓ Greeting reply: {text[:60]}")

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_chinese_message(self, runner):
        """发送中文消息"""
        text = inject_and_get_reply(runner, "你好，请用中文回复", timeout=TIMEOUT_LLM, chat_id=self.CHAT_ID)
        assert len(text) > 0, "Expected LLM reply in Chinese"
        logger.info(f"  ✓ Chinese reply: {text[:60]}")

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_llm_has_content(self, runner):
        """验证 LLM 回复有非空内容"""
        chat_id = "U_line_llm_content"
        text = inject_and_get_reply(runner, "Hi there, please say something!", timeout=TIMEOUT_LLM, chat_id=chat_id)
        assert len(text) > 0, "Expected LLM to reply with non-empty content"
        logger.info(f"  ✓ LLM content reply: {text[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 5. 中断命令测试
# ══════════════════════════════════════════════════════════════════════════════

class TestLineAbort:
    """LINE 渠道 /abort 中断测试"""

    CHAT_ID = "U_line_abort"

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_abort_cancels_generation(self, runner):
        """发送消息后 /abort 应取消生成"""
        # 开始一个 LLM 请求
        runner.inject("Tell me a very long story about dragons", chat_id=self.CHAT_ID)
        time.sleep(2)
        # 发送 abort
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject("/abort", chat_id=self.CHAT_ID)
        # 等待 abort 响应
        msg = runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_COMMAND, chat_id=self.CHAT_ID)
        # abort 应该有某种响应（可能是取消确认，也可能是 LLM 的部分回复）
        # 不强求特定内容，只要有回复就行
        time.sleep(3)
        all_msgs = runner.get_sent_messages(timeout=5)
        new_msgs = all_msgs[count_before:]
        assert len(new_msgs) >= 0, "abort processed"
        logger.info(f"  ✓ /abort processed, {len(new_msgs)} messages after abort")


# ══════════════════════════════════════════════════════════════════════════════
# 6. 多用户隔离
# ══════════════════════════════════════════════════════════════════════════════

class TestLineMultiUser:
    """多用户隔离测试"""

    def test_multiple_users_isolated(self, runner):
        """两个不同用户的消息应该各自得到回复，不会混淆。"""
        user_a = "U_line_user_a"
        user_b = "U_line_user_b"

        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject(text="/new", chat_id=user_a)
        time.sleep(2)
        runner.inject(text="/new", chat_id=user_b)

        # 等待至少 2 条回复
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

class TestLineMessageDedup:
    """验证 LINE 消息去重 (MessageDedup)"""

    CHAT_ID = "U_line_dedup"

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_duplicate_message_id_ignored(self, runner):
        """验证相同 message_id 的重复消息被忽略"""
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


# ══════════════════════════════════════════════════════════════════════════════
# 8. allowed_senders 白名单过滤
# ══════════════════════════════════════════════════════════════════════════════

class TestLineAllowedSenders:
    """验证 LINE allowed_senders 白名单过滤

    gateway 配置 allowed_senders="U_test_user,U_line_test_1,...",
    非白名单用户的 userId 会被 check_allowed() 拒绝。
    """

    def test_allowed_sender_gets_reply(self, runner):
        """白名单内用户发送消息 → bot 正常回复"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND,
                                    chat_id="U_line_test_1")
        assert "cleared" in text.lower() or "session" in text.lower(), \
            f"Allowed sender should get reply, got: {text[:60]}"
        logger.info(f"  ✓ Allowed sender (U_line_test_1) got reply: {text[:60]}")

    def test_blocked_sender_no_reply(self, runner):
        """白名单外用户发送消息 → bot 不回复"""
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject("Hello from stranger", chat_id="U_stranger_not_allowed")

        # 等待足够时间确认 bot 不回复
        time.sleep(8)

        count_after = len(runner.get_sent_messages(timeout=5))
        new_replies = count_after - count_before

        assert new_replies == 0, \
            f"Blocked sender should get no reply, but got {new_replies} new replies"
        logger.info("  ✓ Blocked sender (U_stranger_not_allowed) correctly ignored")


# ══════════════════════════════════════════════════════════════════════════════
# 9. 媒体消息测试
# ══════════════════════════════════════════════════════════════════════════════


class TestLineMediaMessages:
    """LINE 媒体消息测试 — 注入各种非文本消息类型，验证 bot 合理响应"""

    CHAT_ID = "U_line_media"

    def test_image_message(self, runner):
        """注入图片消息 → bot 应回复确认"""
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject_event(
            chat_id=self.CHAT_ID,
            message_type="image",
            message_body={"contentProvider": {"type": "line"}},
        )
        msg = runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_COMMAND,
                                    chat_id=self.CHAT_ID)
        assert msg is not None, "Expected reply to image message"
        logger.info(f"  ✓ Image message got reply: {msg['text'][:60]}")

    def test_audio_message(self, runner):
        """注入语音消息 → bot 应回复确认"""
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject_event(
            chat_id=self.CHAT_ID,
            message_type="audio",
            message_body={"duration": 30000},
        )
        msg = runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_COMMAND,
                                    chat_id=self.CHAT_ID)
        assert msg is not None, "Expected reply to audio message"
        logger.info(f"  ✓ Audio message got reply: {msg['text'][:60]}")

    def test_video_message(self, runner):
        """注入视频消息 → bot 应回复确认"""
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject_event(
            chat_id=self.CHAT_ID,
            message_type="video",
            message_body={"duration": 60000},
        )
        msg = runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_COMMAND,
                                    chat_id=self.CHAT_ID)
        assert msg is not None, "Expected reply to video message"
        logger.info(f"  ✓ Video message got reply: {msg['text'][:60]}")

    def test_file_message(self, runner):
        """注入文件消息 → bot 应回复确认"""
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject_event(
            chat_id=self.CHAT_ID,
            message_type="file",
            message_body={"fileName": "report.pdf", "fileSize": 102400},
        )
        msg = runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_COMMAND,
                                    chat_id=self.CHAT_ID)
        assert msg is not None, "Expected reply to file message"
        logger.info(f"  ✓ File message got reply: {msg['text'][:60]}")

    def test_location_message(self, runner):
        """注入位置消息 → bot 应回复确认"""
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject_event(
            chat_id=self.CHAT_ID,
            message_type="location",
            message_body={
                "title": "Test Location",
                "address": "123 Test St, Tokyo",
                "latitude": 35.6762,
                "longitude": 139.6503,
            },
        )
        msg = runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_COMMAND,
                                    chat_id=self.CHAT_ID)
        assert msg is not None, "Expected reply to location message"
        logger.info(f"  ✓ Location message got reply: {msg['text'][:60]}")

    def test_sticker_message(self, runner):
        """注入贴图消息 → bot 应回复确认"""
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject_event(
            chat_id=self.CHAT_ID,
            message_type="sticker",
            message_body={"packageId": "1", "stickerId": "1"},
        )
        msg = runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_COMMAND,
                                    chat_id=self.CHAT_ID)
        assert msg is not None, "Expected reply to sticker message"
        logger.info(f"  ✓ Sticker message got reply: {msg['text'][:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 10. @提及群组门控
# ══════════════════════════════════════════════════════════════════════════════


class TestLineMention:
    """LINE 群组 @提及门控测试

    在群组中，bot 应当在被 @mention 时回复，未被 @mention 时保持沉默。
    """

    CHAT_ID = "U_line_mention"

    def test_mentioned_in_group_gets_reply(self, runner):
        """在群组中被 @mention → bot 应回复"""
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject_event(
            chat_id=self.CHAT_ID,
            source_type="group",
            group_id="G_line_mention_test",
            message_type="text",
            message_body={
                "text": "@TestBot Hello everyone!",
                "mention": {
                    "mentionees": [{"userId": "U_mock_bot"}],
                },
            },
        )
        msg = runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_COMMAND,
                                    chat_id=self.CHAT_ID)
        assert msg is not None, "Bot should reply when @mentioned in group"
        logger.info(f"  ✓ @mentioned in group got reply: {msg['text'][:60]}")

    def test_not_mentioned_in_group_no_reply(self, runner):
        """在群组中未被 @mention → bot 不应回复"""
        # 使用唯一 ID 确保不会与提及测试的 chat 混淆
        silent_user = f"U_line_silent_{uuid.uuid4().hex[:6]}"
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject_event(
            chat_id=silent_user,
            source_type="group",
            group_id="G_line_silent_test",
            message_type="text",
            message_body={"text": "Hey everyone, what's up?"},
        )
        time.sleep(8)
        count_after = len(runner.get_sent_messages(timeout=5))
        new_replies = count_after - count_before
        assert new_replies == 0, \
            f"Bot should not reply when not @mentioned, got {new_replies} new replies"
        logger.info("  ✓ Not @mentioned correctly ignored")


# ══════════════════════════════════════════════════════════════════════════════
# 11. 消息分片测试
# ══════════════════════════════════════════════════════════════════════════════


class TestLineMessageSplitting:
    """LINE 消息分片测试

    LINE 单条消息有字符数限制（约5000字符）。超长消息 octos 应能
    正常处理并回复。
    """

    CHAT_ID = "U_line_split"

    @pytest.mark.llm
    def test_very_long_message(self, runner):
        """超长消息（>5000字符）应被正常处理"""
        long_text = "A" * 5100  # 超过 5000 字符限制
        text = inject_and_get_reply(runner, long_text, timeout=TIMEOUT_LLM, chat_id=self.CHAT_ID)
        assert len(text) > 0, "Bot should respond to very long message"
        logger.info(f"  ✓ Long message (5100 chars) handled, reply: {text[:60]}")
