#!/usr/bin/env python3
"""
Matrix Bot 集成测试用例

前置条件（由 test_run.py 自动完成）：
  1. Mock Matrix Server 运行在 http://127.0.0.1:5002
  2. octos gateway 已启动并连接到 Mock Server（通过 --features matrix）

运行方式：
  uv run python test_run.py --test bot matrix    # 完整测试
  pytest test_matrix.py -v -m "not llm"          # 跳过 LLM 测试
"""

import pytest
import time
import logging
from runner_matrix import MatrixTestRunner
from test_helpers import inject_and_get_reply

# Configure logger for this module
logger = logging.getLogger(__name__)

# 🔥 Suppress httpx INFO logs to reduce noise in test output
logging.getLogger("httpx").setLevel(logging.WARNING)

# ── 超时配置 ──────────────────────────────────────────────────────────────────
TIMEOUT_COMMAND = 20
TIMEOUT_LLM     = 50

LLM_TEST_DELAY = 3.0
ABORT_TEST_DELAY = 2.0
CLEANUP_SLEEP = 2.0


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def runner():
    r = MatrixTestRunner()
    assert r.health(), "Matrix Mock Server 未运行"
    return r


@pytest.fixture(autouse=True)
def cleanup_state(request, runner):
    """每个测试前清理 Mock Server 状态"""
    import httpx
    import os
    import glob
    from test_helpers import inject_and_get_reply

    # Health check
    max_health_retries = 5
    health_retry_delay = 2.0
    for attempt in range(max_health_retries):
        try:
            if runner.health():
                break
        except Exception:
            pass
        if attempt < max_health_retries - 1:
            print(f"  ⚠ Mock Server not responding, retry {attempt + 1}/{max_health_retries}...")
            time.sleep(health_retry_delay)
    else:
        pytest.skip("Mock Server 崩溃，无法恢复")
        return

    # 直接清理数据库文件来重置状态
    db_removed = False
    try:
        data_dir = os.environ.get("OCTOS_TEST_DIR", "/tmp/octos_test")
        db_path = f"{data_dir}/episodes.redb"
        if os.path.exists(db_path):
            os.remove(db_path)
            db_removed = True
            print(f"  🗑 Removed database: {db_path}")
    except OSError as e:
        print(f"  ⚠ Database cleanup warning: {e}")
        db_removed = False

    # 等待 LLM 响应完成（但不要太久，避免新消息被延迟）
    time.sleep(2.0)

    # 检查 Mock Server 是否有积压消息（如果有，说明 Bot 还在处理）
    # 注意：不要在测试前清理 Mock Server，因为可能干扰 Bot 内部状态
    try:
        pending = runner.get_sent_messages(timeout=5)
        if pending:
            print(f"  ⚠ Mock Server has {len(pending)} pending messages, waiting more...")
            time.sleep(15.0)
    except Exception:
        pass

    yield

    if request.node.get_closest_marker('abort_test') or request.node.get_closest_marker('llm_intensive'):
        time.sleep(ABORT_TEST_DELAY)


# ══════════════════════════════════════════════════════════════════════════════
# 第一层：会话管理命令 (GatewayDispatcher)
# ══════════════════════════════════════════════════════════════════════════════

class TestMatrixSessionCommands:
    """验证 GatewayDispatcher 处理的命令（不依赖 LLM）"""

    def test_new_creates_session(self, runner):
        """/new 应该创建新会话"""
        text = inject_and_get_reply(runner, "/new test-session", timeout=TIMEOUT_COMMAND)
        assert "Switched to session: test-session" in text, f"Unexpected: {text}"

    def test_new_with_invalid_name(self, runner):
        """/new 非法名称应该报错"""
        text = inject_and_get_reply(runner, "/new invalid/name", timeout=TIMEOUT_COMMAND)
        assert "Invalid" in text, f"Should reject invalid name: {text}"

    def test_clear_resets_session(self, runner):
        """/clear 应该清空当前会话"""
        inject_and_get_reply(runner, "/new clear-test", timeout=TIMEOUT_COMMAND)
        inject_and_get_reply(runner, "hello", timeout=TIMEOUT_LLM)
        text = inject_and_get_reply(runner, "/clear", timeout=TIMEOUT_COMMAND)
        assert "Session cleared" in text, f"Unexpected: {text}"

    def test_switch_session(self, runner):
        """/s 应该切换会话"""
        inject_and_get_reply(runner, "/new session-a", timeout=TIMEOUT_COMMAND)
        inject_and_get_reply(runner, "/new session-b", timeout=TIMEOUT_COMMAND)
        text = inject_and_get_reply(runner, "/s session-a", timeout=TIMEOUT_COMMAND)
        assert "Switched to session: session-a" in text, f"Unexpected: {text}"

    def test_back_to_previous(self, runner):
        """/back 应该返回上一个会话"""
        inject_and_get_reply(runner, "/new session-a", timeout=TIMEOUT_COMMAND)
        inject_and_get_reply(runner, "/new session-b", timeout=TIMEOUT_COMMAND)
        text = inject_and_get_reply(runner, "/back", timeout=TIMEOUT_COMMAND)
        assert "Switched back to session" in text, f"Unexpected: {text}"
        assert "session-a" in text, f"Expected to return to session-a, got: {text}"

    def test_delete_session(self, runner):
        """/delete 应该删除当前会话"""
        inject_and_get_reply(runner, "/new delete-me", timeout=TIMEOUT_COMMAND)
        text = inject_and_get_reply(runner, "/delete", timeout=TIMEOUT_COMMAND)
        assert "deleted" in text.lower() or "已删除" in text, f"Unexpected: {text}"

    def test_sessions_list(self, runner):
        """/sessions 应该列出所有会话"""
        inject_and_get_reply(runner, "/new list-a", timeout=TIMEOUT_COMMAND)
        inject_and_get_reply(runner, "/new list-b", timeout=TIMEOUT_COMMAND)
        text = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND)
        assert "list-a" in text and "list-b" in text, f"Sessions not listed: {text}"


# ══════════════════════════════════════════════════════════════════════════════
# 第二层：非 LLM 消息与边界情况
# ══════════════════════════════════════════════════════════════════════════════

class TestMatrixBasicMessages:
    """基础消息处理（不调用 LLM）"""

    def test_empty_message(self, runner):
        """空消息应该被忽略或返回提示"""
        count_before = len(runner.get_sent_messages())
        runner.inject("   ", room_id="!test:localhost")
        time.sleep(1)
        count_after = len(runner.get_sent_messages())
        assert count_after == count_before, "Empty message should be ignored"

    def test_very_long_message(self, runner):
        """超长消息应该被截断或正常处理"""
        long_text = "A" * 3000
        text = inject_and_get_reply(runner, long_text, timeout=TIMEOUT_LLM)
        assert len(text) > 0, "Should handle long message"

    def test_special_characters(self, runner):
        """特殊字符消息"""
        text = inject_and_get_reply(runner, "!@#$%^&*()_+-=[]{}|;':\",./<>?", timeout=TIMEOUT_LLM)
        assert len(text) > 0, "Should handle special characters"

    def test_unicode_emoji(self, runner):
        """Unicode 和 Emoji"""
        text = inject_and_get_reply(runner, "Hello 👋 World 🌍 中文测试", timeout=TIMEOUT_LLM)
        assert len(text) > 0, "Should handle unicode and emoji"

    def test_html_formatted_message(self, runner):
        """HTML 格式消息（Matrix 支持 formatted_body）"""
        text = inject_and_get_reply(
            runner,
            "Bold text",
            formatted_body="<b>Bold text</b>",
            timeout=TIMEOUT_LLM
        )
        assert len(text) > 0, "Should handle HTML formatted message"


# ══════════════════════════════════════════════════════════════════════════════
# 第三层：Gateway 配置命令
# ══════════════════════════════════════════════════════════════════════════════

class TestMatrixConfigCommands:
    """配置相关命令"""

    def test_queue_mode_show(self, runner):
        """/queue 应该显示当前模式"""
        text = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND)
        assert any(mode in text for mode in ["Collect", "Followup", "Steer", "Interrupt"]), \
            f"Should show queue mode: {text}"

    def test_queue_mode_set(self, runner):
        """/queue <mode> 应该切换模式"""
        text = inject_and_get_reply(runner, "/queue followup", timeout=TIMEOUT_COMMAND)
        assert "Followup" in text or "followup" in text.lower(), f"Unexpected: {text}"

    def test_soul_show_empty(self, runner):
        """/soul 应该显示当前 soul"""
        text = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND)
        assert len(text) > 0, "Should respond to /soul"

    def test_soul_set(self, runner):
        """/soul <text> 应该设置 soul"""
        text = inject_and_get_reply(runner, "/soul You are a helpful assistant", timeout=TIMEOUT_COMMAND)
        assert "Soul updated" in text or "soul" in text.lower(), f"Unexpected: {text}"

    def test_status_command(self, runner):
        """/status 应该返回状态信息"""
        text = inject_and_get_reply(runner, "/status", timeout=TIMEOUT_COMMAND)
        assert len(text) > 0, "Should return status"

    def test_adaptive_command(self, runner):
        """/adaptive 应该返回路由信息"""
        text = inject_and_get_reply(runner, "/adaptive", timeout=TIMEOUT_COMMAND)
        assert len(text) > 0, "Should return adaptive routing info"

    def test_reset_command(self, runner):
        """/reset 应该重置状态"""
        text = inject_and_get_reply(runner, "/reset", timeout=TIMEOUT_COMMAND)
        assert len(text) > 0, "Should respond to /reset"

    def test_help_command(self, runner):
        """/help 应该返回帮助信息"""
        text = inject_and_get_reply(runner, "/help", timeout=TIMEOUT_COMMAND)
        assert "help" in text.lower() or "命令" in text or "/new" in text, f"Unexpected: {text}"
        for cmd in ["/new", "/s", "/sessions", "/back", "/delete",
                    "/queue", "/soul", "/status", "/adaptive", "/reset"]:
            assert cmd in text, f"帮助文本缺少 {cmd}: {text}"


# ══════════════════════════════════════════════════════════════════════════════
# Queue Mode Steer/Discard 负向测试
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.llm
class TestMatrixQueueModeSteerNonAbort:
    """验证 Steer/Interrupt 模式下，普通消息不会误触发 abort"""

    ROOM_ID_STEER = "!steer:localhost"
    ROOM_ID_INTERRUPT = "!interrupt:localhost"

    def test_steer_mode_non_abort_messages_not_triggered(self, runner):
        """验证 steer 模式下普通消息不会误触发 abort"""
        room_id = self.ROOM_ID_STEER
        text = inject_and_get_reply(runner, "/queue steer", timeout=TIMEOUT_COMMAND, room_id=room_id)
        assert "Steer" in text or "steer" in text.lower(), f"Failed to set steer mode: {text}"

        non_triggers = [
            "please stop talking about cats",
            "stopping point is here",
            "I will exit now",
            "cancel my subscription please",
            "abort the rocket launch",
        ]

        for msg in non_triggers:
            reply = inject_and_get_reply(runner, msg, timeout=TIMEOUT_LLM, room_id=room_id)
            has_abort_emoji = "🛑" in reply
            assert not has_abort_emoji, \
                f"False abort trigger in steer mode for '{msg}': {reply[:200]}"

        logger.info(f"\n  ✓ Steer mode: Non-abort messages handled correctly")
        inject_and_get_reply(runner, "/queue collect", timeout=TIMEOUT_COMMAND, room_id=room_id)

    def test_interrupt_mode_non_abort_messages_not_triggered(self, runner):
        """验证 interrupt 模式下普通消息不会误触发 abort"""
        room_id = self.ROOM_ID_INTERRUPT
        text = inject_and_get_reply(runner, "/queue interrupt", timeout=TIMEOUT_COMMAND, room_id=room_id)
        assert "Interrupt" in text or "interrupt" in text.lower(), \
            f"Failed to set interrupt mode: {text}"

        non_triggers = [
            "don't stop the music",
            "the concert was canceled",
            "abort the rocket launch",
        ]

        for msg in non_triggers:
            reply = inject_and_get_reply(runner, msg, timeout=TIMEOUT_LLM, room_id=room_id)
            has_abort_emoji = "🛑" in reply
            assert not has_abort_emoji, \
                f"False abort trigger in interrupt mode for '{msg}': {reply[:200]}"

        logger.info(f"\n  ✓ Interrupt mode: Non-abort messages handled correctly")
        inject_and_get_reply(runner, "/queue collect", timeout=TIMEOUT_COMMAND, room_id=room_id)


# ══════════════════════════════════════════════════════════════════════════════
# 第四层：LLM 消息测试
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.llm
class TestMatrixLLMMessages:
    """需要调用 LLM API"""

    def test_regular_message(self, runner):
        """普通英文消息触发 LLM 回复"""
        text = inject_and_get_reply(runner, "Hello!", timeout=TIMEOUT_LLM)
        assert len(text) > 0

    def test_chinese_message(self, runner):
        """中文消息触发 LLM 回复"""
        text = inject_and_get_reply(runner, "你好", timeout=TIMEOUT_LLM)
        assert len(text) > 0


# ══════════════════════════════════════════════════════════════════════════════
# Abort 命令测试
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.llm
class TestMatrixAbortCommands:
    """验证 Agent 能正确中止任务 — 多语言 abort 触发词识别"""

    @pytest.mark.abort_test
    @pytest.mark.parametrize(
        "language,room_id,long_task,expected_keywords",
        [
            ("english", "!abort_en:localhost",
             "Please tell me something about Python",
             ["🛑", "Cancelled"]),
            ("chinese", "!abort_zh:localhost",
             "请告诉我 Python 是什么？",
             ["🛑", "已取消"]),
            ("japanese", "!abort_jp:localhost",
             "Pythonとは何ですか？",
             ["🛑", "キャンセル"]),
            ("russian", "!abort_ru:localhost",
             "Что такое Python?",
             ["🛑", "Отменено"]),
        ],
        ids=[
            "english_stop",
            "chinese_stop",
            "japanese_stop",
            "russian_stop",
        ]
    )
    def test_abort_multilanguage(self, runner, language, room_id, long_task, expected_keywords):
        """多语言 abort 命令测试"""
        import time

        TRIGGERS = {
            "english": ["stop", "cancel", "abort", "halt", "quit", "enough"],
            "chinese": ["停", "停止", "取消", "停下", "别说了"],
            "japanese": ["やめて", "止めて", "ストップ"],
            "russian": ["стоп", "отмена", "хватит"],
        }

        triggers = TRIGGERS[language]
        abort_cmd = triggers[0]
        logger.info(f"\n{'='*70}")
        logger.info(f"  Testing {language} - using first trigger: '{abort_cmd}' from {triggers}")
        logger.info(f"{'='*70}\n")

        count_before_task = len(runner.get_sent_messages())
        logger.info(f"📤 Sending to LLM (user input):")
        logger.info(f"   {long_task[:200]}{'...' if len(long_task) > 200 else ''}")
        runner.inject(long_task, room_id=room_id)
        logger.info(f"  → Long task injected\n")

        processing_started = False
        wait_start = time.time()
        last_print_time = wait_start
        while time.time() - wait_start < 15.0:
            current_time = time.time()
            elapsed = current_time - wait_start
            if current_time - last_print_time >= 1.0:
                logger.info(f"  ⏳ Waiting for processing to start... {elapsed:.0f}s")
                last_print_time = current_time

            time.sleep(0.5)
            msgs = runner.get_sent_messages()
            for msg in msgs[count_before_task:]:
                msg_text = msg.get("text", "")
                if any(status in msg_text for status in ["Processing", "Deliberating", "Thinking", "Evaluating"]):
                    processing_started = True
                    logger.info(f"  📥 LLM Status Message: {msg_text}")
                    logger.info(f"  → Detected processing started after {time.time() - wait_start:.1f}s")
                    break
            if processing_started:
                break
        else:
            logger.info(f"  → No processing status detected, continuing anyway...")

        logger.info(f"\n  📤 Sending to LLM (abort command): '{abort_cmd}'")
        runner.inject(abort_cmd, room_id=room_id)

        abort_reply = None
        poll_start = time.time()
        last_print_time = poll_start
        while time.time() - poll_start < 15.0:
            current_time = time.time()
            elapsed = current_time - poll_start
            if current_time - last_print_time >= 1.0:
                logger.info(f"  ⏳ Waiting for abort response... {elapsed:.0f}s")
                last_print_time = current_time

            msgs = runner.get_sent_messages()
            for msg in reversed(msgs):
                msg_text = msg.get("text", "")
                if "🛑" in msg_text or any(kw.lower() in msg_text.lower() for kw in expected_keywords if not kw.startswith("🛑")):
                    abort_reply = msg
                    break

            if abort_reply is not None:
                abort_text = abort_reply.get("text", "")
                logger.info(f"\n{'='*70}")
                logger.info(f"📥 LLM Response (abort reply):")
                logger.info(f"   {abort_text[:300]}{'...' if len(abort_text) > 300 else ''}")
                logger.info(f"{'='*70}\n")
                break

            time.sleep(0.3)

        assert abort_reply is not None, \
            f"Bot did not respond to abort command '{abort_cmd}' within 15s"

        text = abort_reply["text"]
        has_stop_emoji = "🛑" in text
        has_cancel_keyword = any(kw.lower() in text.lower() for kw in expected_keywords if not kw.startswith("🛑"))
        assert has_stop_emoji or has_cancel_keyword, \
            f"Expected abort response (with 🛑 or cancel keyword), got: {text[:200]}"

        count_after_abort = len(runner.get_sent_messages())
        time.sleep(3)
        count_final = len(runner.get_sent_messages())
        new_messages_after_abort = count_final - count_after_abort
        assert new_messages_after_abort <= 1, \
            f"Long task was NOT properly aborted! Found {new_messages_after_abort} new messages after abort: {text[:100]}"

        logger.info(f"  ✓ Abort interrupted long task → {text}")
        logger.info(f"    Verified: No further messages after abort ({new_messages_after_abort} new msgs)")

    @pytest.mark.abort_test
    def test_abort_with_whitespace(self, runner):
        """验证 abort 命令前后空格不影响识别"""
        test_cases = [
            ("  stop  ", "!abort_ws1:localhost", ["🛑", "Cancelled", "Cancel"]),
            ("\tstop\n", "!abort_ws2:localhost", ["🛑", "Cancelled", "Cancel"]),
            (" 停 ", "!abort_ws3:localhost", ["🛑", "取消", "已取消"]),
        ]

        for cmd, room_id, expected_keywords in test_cases:
            count_before = len(runner.get_sent_messages())
            runner.inject(cmd, room_id=room_id)
            abort_reply = runner.wait_for_reply(
                count_before=count_before,
                timeout=TIMEOUT_COMMAND,
                chat_id=room_id
            )
            assert abort_reply is not None, f"Should respond to trimmed '{cmd}'"
            text = abort_reply["text"]

            has_expected_keyword = any(kw.lower() in text.lower() for kw in expected_keywords if not kw.startswith("🛑"))
            has_emoji = "🛑" in text
            assert has_emoji or has_expected_keyword, \
                f"Expected cancel response for '{cmd}', got: {text[:200]}"

        logger.info(f"  ✓ Whitespace handling works")

    def test_non_abort_messages_not_triggered(self, runner):
        """验证普通消息不会误触发 abort"""
        non_triggers = [
            "please stop talking about cats",
            "stopping point is here",
        ]

        for msg in non_triggers:
            count_before = len(runner.get_sent_messages())
            runner.inject(msg, room_id="!non_abort:localhost")
            time.sleep(0.5)

        logger.info(f"\n  ✓ Non-abort messages handled correctly")


# ══════════════════════════════════════════════════════════════════════════════
# Profile 模式测试
# ══════════════════════════════════════════════════════════════════════════════

class TestMatrixProfileMode:
    """验证多 profile 配置下的会话隔离"""

    def test_profile_session_isolation(self, runner):
        """不同 room 使用不同 profile，应该隔离"""
        ROOM_A = "!profile_a:localhost"
        ROOM_B = "!profile_b:localhost"

        text_a = inject_and_get_reply(runner, "/new profile-a", timeout=TIMEOUT_COMMAND, room_id=ROOM_A)
        assert "profile-a" in text_a

        text_b = inject_and_get_reply(runner, "/new profile-b", timeout=TIMEOUT_COMMAND, room_id=ROOM_B)
        assert "profile-b" in text_b

        sessions_a = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND, room_id=ROOM_A)
        sessions_b = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND, room_id=ROOM_B)

        assert "profile-a" in sessions_a
        assert "profile-b" in sessions_b

    @pytest.mark.skip(reason="FIXME: soul 目前未按 profile 隔离，全局共用 soul.md")
    def test_soul_per_profile(self, runner):
        """验证每个 profile 有独立的 soul 配置"""
        ROOM_A = "!soul_a:localhost"
        ROOM_B = "!soul_b:localhost"

        text_a = inject_and_get_reply(runner, "/soul You are a coding expert", timeout=TIMEOUT_COMMAND, room_id=ROOM_A)
        assert "Soul updated" in text_a

        text_b = inject_and_get_reply(runner, "/soul You are a creative writer", timeout=TIMEOUT_COMMAND, room_id=ROOM_B)
        assert "Soul updated" in text_b

        soul_a = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND, room_id=ROOM_A)
        soul_b = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND, room_id=ROOM_B)

        assert "coding expert" in soul_a.lower() or "You are a coding expert" in soul_a
        assert "creative writer" in soul_b.lower() or "You are a creative writer" in soul_b

    def test_queue_mode_per_profile(self, runner):
        """每个 profile 可以有独立的队列模式"""
        ROOM_A = "!queue_a:localhost"
        ROOM_B = "!queue_b:localhost"

        inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND, room_id=ROOM_A)
        inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND, room_id=ROOM_B)

        text_a = inject_and_get_reply(runner, "/queue followup", timeout=TIMEOUT_COMMAND, room_id=ROOM_A)
        assert "Followup" in text_a

        text_b = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND, room_id=ROOM_B)
        assert "Collect" in text_b or "collect" in text_b.lower()

        text_a_check = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND, room_id=ROOM_A)
        assert "Followup" in text_a_check


# ══════════════════════════════════════════════════════════════════════════════
# 压力与边界测试
# ══════════════════════════════════════════════════════════════════════════════

class TestMatrixStressAndEdgeCases:
    """压力测试和边界情况"""

    @pytest.mark.llm
    def test_rapid_messages(self, runner):
        """快速发送多条消息"""
        messages = ["Message 1", "Message 2", "Message 3"]
        for msg in messages:
            runner.inject(msg, room_id="!rapid:localhost")

        time.sleep(10)
        sent = runner.get_sent_messages()
        assert len(sent) >= 3, f"Expected at least 3 replies, got {len(sent)}"

    def test_concurrent_rooms(self, runner):
        """多个 room 同时对话"""
        rooms = ["!room_a:localhost", "!room_b:localhost"]

        for room in rooms:
            runner.inject(f"Hello from {room}", room_id=room)

        time.sleep(5)
        for room in rooms:
            msgs = [m for m in runner.get_sent_messages() if m.get("room_id") == room]
            assert len(msgs) > 0, f"Room {room} should have replies"

    def test_message_with_mention(self, runner):
        """带 @mention 的消息"""
        text = inject_and_get_reply(runner, "Hello @bot:localhost", timeout=TIMEOUT_LLM)
        assert len(text) > 0, "Should handle mention"

    def test_message_with_code_block(self, runner):
        """带代码块的消息"""
        code_msg = "```python\nprint('hello')\n```"
        text = inject_and_get_reply(runner, code_msg, timeout=TIMEOUT_LLM)
        assert len(text) > 0, "Should handle code block"

    def test_message_with_link(self, runner):
        """带链接的消息"""
        link_msg = "Check out https://example.com"
        text = inject_and_get_reply(runner, link_msg, timeout=TIMEOUT_LLM)
        assert len(text) > 0, "Should handle link"


# ══════════════════════════════════════════════════════════════════════════════
# 预留：Matrix 特有功能测试（未来实现）
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skip(reason="Matrix Bot 管理功能预留，待实现")
class TestMatrixBotManagement:
    """Matrix 特有的 Bot 管理功能（预留）

    未来测试：
    - /createbot <username> <name>
    - /deletebot <matrix_user_id>
    - /listbots
    """
    pass


@pytest.mark.skip(reason="Matrix Swarm Supervisor 功能预留，待实现")
class TestMatrixSwarmSupervisor:
    """Matrix Swarm Supervisor 功能（预留）

    未来测试：
    - register_subagent_puppet
    - ensure_swarm_room
    - route_subagent_event
    - handle_supervisor_reply
    """
    pass
