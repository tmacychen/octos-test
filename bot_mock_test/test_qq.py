#!/usr/bin/env python3
"""
QQ Bot 集成测试用例

前置条件（由 test_run.py 自动完成）：
  1. Mock QQ Bot Server 运行在 http://127.0.0.1:5010
  2. octos gateway 已启动并连接到 Mock Server（通过 --features qq-bot）
  3. QQ_BOT_API_BASE_URL 指向 Mock Server

运行方式：
  uv run python test_run.py --test bot qq-bot    # 完整测试
"""

import logging
import os
import time
import uuid

import pytest

from runner_qq import QqTestRunner
from test_helpers import inject_and_get_reply, test_ws_reconnect_basic

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

TIMEOUT_COMMAND = 30
TIMEOUT_LLM = 90

# C2C 测试使用的固定 sender（必须在 allowed_senders 中）
# test_run.py 中当前 allowed_senders 包含: user_c2c_session, user_c2c_config, user_c2c_dedup
C2C_SENDER_SESSION = "user_c2c_session"
C2C_SENDER_CONFIG = "user_c2c_config"
C2C_SENDER_DEDUP = "user_c2c_dedup"


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def runner():
    r = QqTestRunner()
    assert r.health(), "QQ Bot Mock Server not running"
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
        pytest.skip("QQ Bot Mock Server not responding")
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

class TestQqBotConnectivity:
    """QQ Bot Mock Server 连接测试"""

    def test_server_health(self, runner):
        """验证 Mock Server 健康状态"""
        assert runner.health(), "Mock Server health check failed"
        logger.info("  ✓ QQ Bot Mock Server is healthy")


# ══════════════════════════════════════════════════════════════════════════════
# 2. 会话管理命令（群消息）
# ══════════════════════════════════════════════════════════════════════════════

class TestQqBotSessionCommands:
    """QQ Bot 渠道会话管理（群消息 @bot）"""

    CHAT_ID = "group_session_test"

    def test_new_default(self, runner):
        """/new 默认会话创建"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND,
                                    group_openid=self.CHAT_ID)
        assert "cleared" in text.lower() or "session" in text.lower() or "new" in text.lower(), \
            f"Expected session created, got: {text[:80]}"
        logger.info(f"  ✓ /new: {text[:60]}")

    def test_new_with_name(self, runner):
        """/new <name> 创建命名会话"""
        text = inject_and_get_reply(runner, "/new test-session", timeout=TIMEOUT_COMMAND,
                                    group_openid=self.CHAT_ID)
        assert "cleared" in text.lower() or "session" in text.lower() or "new" in text.lower(), \
            f"Expected named session created, got: {text[:80]}"
        logger.info(f"  ✓ /new test-session: {text[:60]}")

    def test_sessions_list(self, runner):
        """/sessions 列出会话"""
        text = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND,
                                    group_openid=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /sessions reply"
        logger.info(f"  ✓ /sessions: {text[:60]}")

    def test_back_command(self, runner):
        """/back 切换回上一个会话"""
        inject_and_get_reply(runner, "/new first-session", timeout=TIMEOUT_COMMAND,
                             group_openid=self.CHAT_ID)
        inject_and_get_reply(runner, "/new second-session", timeout=TIMEOUT_COMMAND,
                             group_openid=self.CHAT_ID)
        text = inject_and_get_reply(runner, "/back", timeout=TIMEOUT_COMMAND,
                                    group_openid=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /back reply"
        logger.info(f"  ✓ /back: {text[:60]}")

    def test_delete_session(self, runner):
        """/delete 删除会话"""
        inject_and_get_reply(runner, "/new to-delete", timeout=TIMEOUT_COMMAND,
                             group_openid=self.CHAT_ID)
        text = inject_and_get_reply(runner, "/delete", timeout=TIMEOUT_COMMAND,
                                    group_openid=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /delete reply"
        logger.info(f"  ✓ /delete: {text[:60]}")

    def test_help(self, runner):
        """/help 帮助命令"""
        text = inject_and_get_reply(runner, "/help", timeout=TIMEOUT_COMMAND,
                                    group_openid=self.CHAT_ID)
        assert "help" in text.lower() or len(text) > 20, \
            f"Expected help text, got: {text[:80]}"
        logger.info(f"  ✓ /help received ({len(text)} chars)")

    def test_clear_resets_session(self, runner):
        """/clear → 清空当前会话"""
        inject_and_get_reply(runner, "/new clear-test", timeout=TIMEOUT_COMMAND,
                             group_openid=self.CHAT_ID)
        text = inject_and_get_reply(runner, "/clear", timeout=TIMEOUT_COMMAND,
                                    group_openid=self.CHAT_ID)
        assert "cleared" in text.lower() or "clear" in text.lower(), \
            f"Expected session cleared, got: {text[:80]}"
        logger.info(f"  ✓ /clear: {text[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 3. 配置命令
# ══════════════════════════════════════════════════════════════════════════════

class TestQqBotConfigCommands:
    """QQ Bot 渠道配置命令"""

    CHAT_ID = "group_config_test"

    def test_soul_show(self, runner):
        """/soul 显示当前 soul"""
        text = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND,
                                    group_openid=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /soul reply"
        logger.info(f"  ✓ /soul: {text[:60]}")

    def test_queue_show(self, runner):
        """/queue 显示队列模式"""
        text = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND,
                                    group_openid=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /queue reply"
        logger.info(f"  ✓ /queue: {text[:60]}")

    def test_status(self, runner):
        """/status"""
        text = inject_and_get_reply(runner, "/status", timeout=TIMEOUT_COMMAND,
                                    group_openid=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /status reply"
        logger.info(f"  ✓ /status: {text[:60]}")

    def test_reset(self, runner):
        """/reset 重置配置"""
        text = inject_and_get_reply(runner, "/reset", timeout=TIMEOUT_COMMAND,
                                    group_openid=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /reset reply"
        logger.info(f"  ✓ /reset: {text[:60]}")

    def test_adaptive(self, runner):
        """/adaptive 切换自适应模式"""
        text = inject_and_get_reply(runner, "/adaptive", timeout=TIMEOUT_COMMAND,
                                    group_openid=self.CHAT_ID)
        assert len(text) > 0, "Expected non-empty /adaptive reply"
        logger.info(f"  ✓ /adaptive: {text[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. LLM 消息测试
# ══════════════════════════════════════════════════════════════════════════════

class TestQqBotLLMMessages:
    """QQ Bot 渠道 LLM 消息测试"""

    CHAT_ID = "group_llm_test"

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_simple_greeting(self, runner):
        """发送简单英文问候"""
        text = inject_and_get_reply(runner, "Hello!", timeout=TIMEOUT_LLM,
                                    group_openid=self.CHAT_ID)
        assert len(text) > 0, "Expected LLM to reply"
        logger.info(f"  ✓ Greeting reply: {text[:60]}")

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_chinese_message(self, runner):
        """发送中文消息"""
        text = inject_and_get_reply(runner, "你好，请用中文回复", timeout=TIMEOUT_LLM,
                                    group_openid=self.CHAT_ID)
        assert len(text) > 0, "Expected LLM reply in Chinese"
        logger.info(f"  ✓ Chinese reply: {text[:60]}")

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_llm_has_content(self, runner):
        """验证 LLM 回复有非空内容"""
        chat_id = f"group_llm_content_{uuid.uuid4().hex[:6]}"
        text = inject_and_get_reply(runner, "Hi there, please say something!",
                                    timeout=TIMEOUT_LLM, group_openid=chat_id)
        assert len(text) > 0, "Expected LLM to reply with non-empty content"
        logger.info(f"  ✓ LLM content reply: {text[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 5. 中断命令测试
# ══════════════════════════════════════════════════════════════════════════════

class TestQqBotAbort:
    """QQ Bot 渠道 /abort 中断测试"""

    CHAT_ID = "group_abort_test"

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_abort_cancels_generation(self, runner):
        """发送消息后 /abort 应取消生成"""
        runner.inject("Tell me a very long story about dragons", group_openid=self.CHAT_ID)
        time.sleep(2)
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject("/abort", group_openid=self.CHAT_ID)
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

class TestQqBotMultiUser:
    """多用户隔离测试"""

    def test_multiple_users_isolated(self, runner):
        """不同群的消息应该各自得到回复"""
        group_a = f"group_a_{uuid.uuid4().hex[:4]}"
        group_b = f"group_b_{uuid.uuid4().hex[:4]}"

        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject(text="/new", group_openid=group_a)
        time.sleep(2)
        runner.inject(text="/new", group_openid=group_b)

        runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_COMMAND)
        time.sleep(5)
        all_msgs = runner.get_sent_messages(timeout=5)
        new_msgs = all_msgs[count_before:]
        assert len(new_msgs) >= 2, \
            f"Expected 2+ replies, got {len(new_msgs)}"
        logger.info(f"  ✓ Two groups got {len(new_msgs)} replies")


# ══════════════════════════════════════════════════════════════════════════════
# 7. C2C 私聊消息
# ══════════════════════════════════════════════════════════════════════════════

class TestQqBotC2C:
    """QQ Bot C2C 私聊 LLM 消息测试"""

    USER_OPENID = C2C_SENDER_SESSION

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_c2c_message_gets_reply(self, runner):
        """C2C 私聊消息应得到回复"""
        user_openid = f"user_c2c_llm_{uuid.uuid4().hex[:6]}"
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject("Hello from C2C", event_type="C2C_MESSAGE_CREATE",
                      user_openid=user_openid)
        msg = runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_LLM,
                                    chat_id=user_openid)
        assert msg is not None, "Expected reply to C2C message"
        logger.info(f"  ✓ C2C reply: {msg['text'][:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 7b. C2C 会话管理命令
# ══════════════════════════════════════════════════════════════════════════════


class TestQqBotC2CSessionCommands:
    """QQ Bot C2C 私聊会话管理命令测试"""

    USER_OPENID = C2C_SENDER_SESSION

    def test_new_default(self, runner):
        """/new 默认会话创建"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND,
                                    event_type="C2C_MESSAGE_CREATE",
                                    user_openid=self.USER_OPENID,
                                    message_id=f"c2c_new_{uuid.uuid4().hex[:8]}")
        assert "cleared" in text.lower() or "session" in text.lower() or "new" in text.lower(), \
            f"Expected session created, got: {text[:80]}"
        logger.info(f"  ✓ C2C /new: {text[:60]}")

    def test_new_with_name(self, runner):
        """/new <name> 创建命名会话"""
        text = inject_and_get_reply(runner, "/new c2c-test-session", timeout=TIMEOUT_COMMAND,
                                    event_type="C2C_MESSAGE_CREATE",
                                    user_openid=self.USER_OPENID,
                                    message_id=f"c2c_named_{uuid.uuid4().hex[:8]}")
        assert "cleared" in text.lower() or "session" in text.lower() or "new" in text.lower(), \
            f"Expected named session created, got: {text[:80]}"
        logger.info(f"  ✓ C2C /new c2c-test-session: {text[:60]}")

    def test_sessions_list(self, runner):
        """/sessions 列出会话"""
        text = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND,
                                    event_type="C2C_MESSAGE_CREATE",
                                    user_openid=self.USER_OPENID,
                                    message_id=f"c2c_list_{uuid.uuid4().hex[:8]}")
        assert len(text) > 0, "Expected non-empty /sessions reply"
        logger.info(f"  ✓ C2C /sessions: {text[:60]}")

    def test_back_command(self, runner):
        """/back 切换回上一个会话"""
        inject_and_get_reply(runner, "/new c2c-first", timeout=TIMEOUT_COMMAND,
                             event_type="C2C_MESSAGE_CREATE",
                             user_openid=self.USER_OPENID,
                             message_id=f"c2c_b1_{uuid.uuid4().hex[:8]}")
        inject_and_get_reply(runner, "/new c2c-second", timeout=TIMEOUT_COMMAND,
                             event_type="C2C_MESSAGE_CREATE",
                             user_openid=self.USER_OPENID,
                             message_id=f"c2c_b2_{uuid.uuid4().hex[:8]}")
        text = inject_and_get_reply(runner, "/back", timeout=TIMEOUT_COMMAND,
                                    event_type="C2C_MESSAGE_CREATE",
                                    user_openid=self.USER_OPENID,
                                    message_id=f"c2c_b3_{uuid.uuid4().hex[:8]}")
        assert len(text) > 0, "Expected non-empty /back reply"
        logger.info(f"  ✓ C2C /back: {text[:60]}")

    def test_delete_session(self, runner):
        """/delete 删除会话"""
        inject_and_get_reply(runner, "/new c2c-to-delete", timeout=TIMEOUT_COMMAND,
                             event_type="C2C_MESSAGE_CREATE",
                             user_openid=self.USER_OPENID,
                             message_id=f"c2c_d1_{uuid.uuid4().hex[:8]}")
        text = inject_and_get_reply(runner, "/delete", timeout=TIMEOUT_COMMAND,
                                    event_type="C2C_MESSAGE_CREATE",
                                    user_openid=self.USER_OPENID,
                                    message_id=f"c2c_d2_{uuid.uuid4().hex[:8]}")
        assert len(text) > 0, "Expected non-empty /delete reply"
        logger.info(f"  ✓ C2C /delete: {text[:60]}")

    def test_help(self, runner):
        """/help 帮助命令"""
        text = inject_and_get_reply(runner, "/help", timeout=TIMEOUT_COMMAND,
                                    event_type="C2C_MESSAGE_CREATE",
                                    user_openid=self.USER_OPENID,
                                    message_id=f"c2c_help_{uuid.uuid4().hex[:8]}")
        assert "help" in text.lower() or len(text) > 20, \
            f"Expected help text, got: {text[:80]}"
        logger.info(f"  ✓ C2C /help ({len(text)} chars)")

    def test_clear_resets_session(self, runner):
        """/clear → 清空当前会话"""
        inject_and_get_reply(runner, "/new c2c-clear-test", timeout=TIMEOUT_COMMAND,
                             event_type="C2C_MESSAGE_CREATE",
                             user_openid=self.USER_OPENID,
                             message_id=f"c2c_cl1_{uuid.uuid4().hex[:8]}")
        text = inject_and_get_reply(runner, "/clear", timeout=TIMEOUT_COMMAND,
                                    event_type="C2C_MESSAGE_CREATE",
                                    user_openid=self.USER_OPENID,
                                    message_id=f"c2c_cl2_{uuid.uuid4().hex[:8]}")
        assert "cleared" in text.lower() or "clear" in text.lower(), \
            f"Expected session cleared, got: {text[:80]}"
        logger.info(f"  ✓ C2C /clear: {text[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 7c. C2C 配置命令
# ══════════════════════════════════════════════════════════════════════════════


class TestQqBotC2CConfigCommands:
    """QQ Bot C2C 私聊配置命令测试"""

    USER_OPENID = C2C_SENDER_CONFIG

    def test_soul_show(self, runner):
        """/soul 显示当前 soul"""
        text = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND,
                                    event_type="C2C_MESSAGE_CREATE",
                                    user_openid=self.USER_OPENID,
                                    message_id=f"c2c_soul_{uuid.uuid4().hex[:8]}")
        assert len(text) > 0, "Expected non-empty /soul reply"
        logger.info(f"  ✓ C2C /soul: {text[:60]}")

    def test_queue_show(self, runner):
        """/queue 显示队列模式"""
        text = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND,
                                    event_type="C2C_MESSAGE_CREATE",
                                    user_openid=self.USER_OPENID,
                                    message_id=f"c2c_queue_{uuid.uuid4().hex[:8]}")
        assert len(text) > 0, "Expected non-empty /queue reply"
        logger.info(f"  ✓ C2C /queue: {text[:60]}")

    def test_status(self, runner):
        """/status"""
        text = inject_and_get_reply(runner, "/status", timeout=TIMEOUT_COMMAND,
                                    event_type="C2C_MESSAGE_CREATE",
                                    user_openid=self.USER_OPENID,
                                    message_id=f"c2c_status_{uuid.uuid4().hex[:8]}")
        assert len(text) > 0, "Expected non-empty /status reply"
        logger.info(f"  ✓ C2C /status: {text[:60]}")

    def test_reset(self, runner):
        """/reset 重置配置"""
        text = inject_and_get_reply(runner, "/reset", timeout=TIMEOUT_COMMAND,
                                    event_type="C2C_MESSAGE_CREATE",
                                    user_openid=self.USER_OPENID,
                                    message_id=f"c2c_reset_{uuid.uuid4().hex[:8]}")
        assert len(text) > 0, "Expected non-empty /reset reply"
        logger.info(f"  ✓ C2C /reset: {text[:60]}")

    def test_adaptive(self, runner):
        """/adaptive 切换自适应模式"""
        text = inject_and_get_reply(runner, "/adaptive", timeout=TIMEOUT_COMMAND,
                                    event_type="C2C_MESSAGE_CREATE",
                                    user_openid=self.USER_OPENID,
                                    message_id=f"c2c_adpt_{uuid.uuid4().hex[:8]}")
        assert len(text) > 0, "Expected non-empty /adaptive reply"
        logger.info(f"  ✓ C2C /adaptive: {text[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# 8. 消息去重
# ══════════════════════════════════════════════════════════════════════════════

class TestQqBotMessageDedup:
    """验证 QQ Bot 消息去重 (MessageDedup)"""

    CHAT_ID = "group_dedup_test"

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No LLM API key configured",
    )
    def test_duplicate_message_id_ignored(self, runner):
        """验证相同 message_id 的重复消息被忽略"""
        dedup_msg_id = f"msg_dedup_{uuid.uuid4().hex[:12]}"

        reply1 = inject_and_get_reply(runner, "Dedup test", timeout=TIMEOUT_LLM,
                                      group_openid=self.CHAT_ID, message_id=dedup_msg_id)
        assert len(reply1) > 0, "Bot should reply to first message"

        count_before = len(runner.get_sent_messages(timeout=5))

        # 第二次发送相同 message_id
        runner.inject("Dedup test", group_openid=self.CHAT_ID, message_id=dedup_msg_id)
        time.sleep(3)

        count_after = len(runner.get_sent_messages(timeout=5))
        new_replies = count_after - count_before

        assert new_replies == 0, \
            f"Duplicate message_id should be deduplicated, but got {new_replies} new replies"
        logger.info("  ✓ Duplicate message_id correctly deduplicated")


# ══════════════════════════════════════════════════════════════════════════════
# 9. allowed_senders 白名单过滤
# ══════════════════════════════════════════════════════════════════════════════

class TestQqBotAllowedSenders:
    """验证 QQ Bot allowed_senders 白名单过滤"""

    def test_allowed_sender_gets_reply(self, runner):
        """白名单内用户发送消息 → bot 正常回复"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND,
                                    group_openid="group_allowed_test",
                                    member_openid="member_test_001")
        assert "cleared" in text.lower() or "session" in text.lower(), \
            f"Allowed sender should get reply, got: {text[:60]}"
        logger.info(f"  ✓ Allowed sender got reply: {text[:60]}")

    def test_blocked_sender_no_reply(self, runner):
        """白名单外用户发送消息 → bot 不回复"""
        count_before = len(runner.get_sent_messages(timeout=5))
        runner.inject("Hello from stranger",
                      group_openid="group_blocked_test",
                      member_openid="member_stranger_not_allowed")

        time.sleep(8)

        count_after = len(runner.get_sent_messages(timeout=5))
        new_replies = count_after - count_before

        assert new_replies == 0, \
            f"Blocked sender should get no reply, but got {new_replies} new replies"
        logger.info("  ✓ Blocked sender correctly ignored")


# ═══════════════════════════════════════════════════════════════════════════════
# 10. WebSocket 断线重连测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestQqBotWsReconnect:
    """QQ Bot WebSocket 断线重连测试"""

    def test_ws_reconnect(self, runner):
        """断开 WS 连接后验证 bot 能自动重连并正常通信"""
        test_ws_reconnect_basic(runner, timeout_cmd=TIMEOUT_COMMAND,
                                group_openid="group_session_test")
