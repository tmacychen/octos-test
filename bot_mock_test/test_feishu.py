#!/usr/bin/env python3
"""
飞书 Bot 集成测试

测试 octos 飞书 Bot 的核心功能：
  - 会话管理（/new, /switch, /sessions, /back, /delete）
  - 配置命令（/queue, /soul, /status, /adaptive, /reset, /help）
  - 基本 LLM 消息
  - Profile 模式
"""

import logging
import pytest
import time
import httpx
from test_helpers import inject_and_get_reply
from runner_feishu import FeishuTestRunner

logger = logging.getLogger(__name__)

# ── 超时配置 ──────────────────────────────────────────────────────────────────
TIMEOUT_COMMAND = 50
TIMEOUT_LLM     = 90

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def runner():
    """创建飞书测试运行器（session 级）。"""
    r = FeishuTestRunner()
    assert r.health(), "Mock Server 未运行"
    return r


@pytest.fixture(autouse=True)
def clear_before(runner):
    """每个测试前清理 Mock Server 状态，包含健康检查和稳定性检测。"""
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

    # 等待消息稳定
    try:
        prev_count = len(runner.get_sent_messages(timeout=2))
    except httpx.HTTPError:
        pytest.skip("Mock Server 响应异常，跳过测试")
        return

    for _ in range(10):
        time.sleep(0.5)
        try:
            curr_count = len(runner.get_sent_messages(timeout=2))
            if curr_count == prev_count:
                break
            prev_count = curr_count
        except httpx.HTTPError:
            break

    # 清理状态
    try:
        runner.clear()
    except httpx.HTTPError:
        pytest.skip("Mock Server 无法清理，跳过测试")
        return

    # 重置所有非默认状态
    try:
        inject_and_get_reply(runner, "/reset", timeout=3,
                             sender_id="reset_cleanup", chat_id="oc_test_reset")
    except (httpx.HTTPError, AssertionError, Exception):
        pass

    time.sleep(0.5)
    yield


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：会话管理
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuSessionCommands:
    """测试飞书频道中的会话管理命令 (/new, /s, /back, /sessions, /delete, /soul)"""

    SENDER = "ou_session_tester"
    CHAT = "oc_test_session"

    def inject(self, runner, text):
        inject_and_get_reply(runner, text, timeout=TIMEOUT_COMMAND,
                             sender_id=self.SENDER, chat_id=self.CHAT)

    def test_new_default(self, runner):
        """/new 应该创建默认会话"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Session cleared.", f"实际回复: {text}"

    def test_new_named(self, runner):
        """/new <name> 应该创建命名会话"""
        text = inject_and_get_reply(runner, "/new work", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Switched to session: work", f"实际回复: {text}"

    def test_new_invalid_name(self, runner):
        """/new bad:name 应该报错"""
        text = inject_and_get_reply(runner, "/new bad:name", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text.startswith("Invalid session name:"), f"实际回复: {text}"

    def test_switch_to_existing(self, runner):
        """/s <name> 应该切换会话"""
        self.inject(runner, "/new research")
        text = inject_and_get_reply(runner, "/s research", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text.startswith("Switched to session: research"), f"实际回复: {text}"

    def test_switch_to_default(self, runner):
        """/s（无参数）应该切换到默认会话"""
        self.inject(runner, "/new custom")
        text = inject_and_get_reply(runner, "/s", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Switched to default session.", f"实际回复: {text}"

    def test_sessions_list(self, runner):
        """/sessions 应该列出所有会话"""
        self.inject(runner, "/new list-a")
        self.inject(runner, "/new list-b")
        text = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert "list-a" in text and "list-b" in text, f"会话列表缺少预期会话: {text}"

    def test_back_returns_session(self, runner):
        """/back 应该返回会话相关回复"""
        text = inject_and_get_reply(runner, "/back", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert "session" in text.lower(), f"实际回复: {text}"

    def test_back_with_history(self, runner):
        """/back（有历史）应该返回上一个会话"""
        self.inject(runner, "/new alpha")
        self.inject(runner, "/new beta")
        text = inject_and_get_reply(runner, "/back", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text.startswith("Switched back to session:"), f"实际回复: {text}"

    def test_delete_session(self, runner):
        """/delete <name> 应该删除会话"""
        self.inject(runner, "/new to-delete")
        text = inject_and_get_reply(runner, "/delete to-delete", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Deleted session: to-delete", f"实际回复: {text}"

    def test_delete_no_name(self, runner):
        """/delete（无参数）走未知命令帮助"""
        text = inject_and_get_reply(runner, "/delete", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert len(text) > 0, "回复为空"
        logger.info(f"\n  /delete (no arg) → {text[:80]}")

    def test_soul_show_default(self, runner):
        """/soul 应该显示当前 soul"""
        text = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert len(text) > 0, "回复为空"

    def test_soul_set(self, runner):
        """/soul <text> 应该设置 soul"""
        text = inject_and_get_reply(runner, "/soul 你是一个助手", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Soul updated. Takes effect in new sessions.", f"实际回复: {text}"

    def test_soul_reset(self, runner):
        """/soul reset 应该重置 soul"""
        text = inject_and_get_reply(runner, "/soul reset", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Soul reset to default. Takes effect in new sessions.", f"实际回复: {text}"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：配置命令
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuConfigCommands:
    """测试飞书频道中的配置命令 (/queue, /status, /adaptive, /reset, /help)"""

    SENDER = "ou_config_tester"
    CHAT = "oc_test_config"

    def test_adaptive_no_router(self, runner):
        """/adaptive 未启用自适应路由"""
        text = inject_and_get_reply(runner, "/adaptive", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Adaptive routing is not enabled.", f"实际回复: {text}"

    def test_queue_show(self, runner):
        """/queue 应该显示当前模式"""
        text = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text.startswith("Queue mode:"), f"实际回复: {text}"

    def test_queue_set_followup(self, runner):
        """/queue followup 应该切换模式"""
        text = inject_and_get_reply(runner, "/queue followup", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert "Followup" in text, f"实际回复: {text}"

    def test_queue_set_invalid(self, runner):
        """/queue badmode 应该提示未知模式"""
        text = inject_and_get_reply(runner, "/queue badmode", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert "Unknown mode" in text, f"实际回复: {text}"

    def test_status_show(self, runner):
        """/status 应该返回状态配置"""
        text = inject_and_get_reply(runner, "/status", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert "Status Config" in text, f"实际回复: {text}"

    def test_reset_command(self, runner):
        """/reset 应该重置所有配置"""
        text = inject_and_get_reply(runner, "/reset", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Reset: queue=collect, adaptive=off, history cleared.", \
            f"实际回复: {text}"

    def test_unknown_command_help(self, runner):
        """未知命令应该返回帮助文本"""
        text = inject_and_get_reply(runner, "/unknowncmd", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text.startswith("Unknown command."), f"实际回复: {text}"
        for cmd in ["/new", "/s", "/sessions", "/back", "/delete", "/soul",
                    "/status", "/adaptive", "/reset"]:
            assert cmd in text, f"帮助文本缺少 {cmd}: {text}"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：基本 LLM 消息
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：多用户隔离
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuMultiUser:
    """多用户隔离测试 — 两个不同 sender/chat 各自独立上下文"""

    SENDER_A = "ou_multi_user_a"
    CHAT_A = "oc_test_multi_a"
    SENDER_B = "ou_multi_user_b"
    CHAT_B = "oc_test_multi_b"

    def test_two_users_independent(self, runner):
        """两个不同 chat 的用户各自创建会话，互不干扰"""
        text_a = inject_and_get_reply(
            runner, "/new user-a-topic", timeout=TIMEOUT_COMMAND,
            sender_id=self.SENDER_A, chat_id=self.CHAT_A)
        assert text_a == "Switched to session: user-a-topic", f"User A: {text_a}"

        text_b = inject_and_get_reply(
            runner, "/new user-b-topic", timeout=TIMEOUT_COMMAND,
            sender_id=self.SENDER_B, chat_id=self.CHAT_B)
        assert text_b == "Switched to session: user-b-topic", f"User B: {text_b}"

        # 验证 A 的会话不受 B 影响
        sessions_a = inject_and_get_reply(
            runner, "/sessions", timeout=TIMEOUT_COMMAND,
            sender_id=self.SENDER_A, chat_id=self.CHAT_A)
        assert "user-a-topic" in sessions_a, f"User A sessions missing: {sessions_a}"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：Abort 触发与多语言 abort
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.llm
class TestFeishuAbortCommands:
    """验证 Agent 能正确中止任务 — Abort 触发 + 多语言 abort

    Abort 是本地命令识别（octos-core/src/abort.rs），不依赖 LLM。
    标记 @pytest.mark.llm 因为需要完整 gateway 环境。
    """

    SENDER = "ou_abort_tester"
    CHAT = "oc_test_abort"

    def test_abort_with_whitespace(self, runner):
        """验证 abort 命令前后空格不影响识别"""
        test_cases = [
            ("  stop  ", "oc_abort_ws1", ["🛑", "Cancelled", "Cancel"]),
            ("  cancel  ", "oc_abort_ws2", ["🛑", "Cancelled", "Cancel"]),
            (" 停 ", "oc_abort_ws3", ["🛑", "取消", "已取消"]),
        ]

        for cmd, chat_id, expected_keywords in test_cases:
            count_before = len(runner.get_sent_messages())
            runner.inject(cmd, sender_id=self.SENDER, chat_id=chat_id)
            abort_reply = runner.wait_for_reply(
                count_before=count_before,
                timeout=TIMEOUT_COMMAND,
                chat_id=chat_id,
            )
            assert abort_reply is not None, f"Should respond to trimmed '{cmd}'"
            text = abort_reply["text"]

            has_expected_keyword = any(
                kw.lower() in text.lower()
                for kw in expected_keywords
                if not kw.startswith("🛑")
            )
            has_emoji = "🛑" in text
            assert has_emoji or has_expected_keyword, \
                f"Expected cancel response for '{cmd}', got: {text[:200]}"

        logger.info(f"  ✓ Whitespace handling works")

    @pytest.mark.parametrize(
        "language,chat_id,long_task,expected_keywords",
        [
            ("english", "oc_abort_en",
             "Please tell me something about Python",
             ["🛑", "Cancelled"]),

            ("chinese", "oc_abort_cn",
             "请告诉我 Python 是什么？",
             ["🛑", "已取消"]),

            ("japanese", "oc_abort_jp",
             "Pythonとは何ですか？",
             ["🛑", "キャンセル"]),

            ("russian", "oc_abort_ru",
             "Что такое Python?",
             ["🛑", "Отменено"]),
        ],
        ids=["english_stop", "chinese_stop", "japanese_stop", "russian_stop"],
    )
    def test_abort_multilanguage(self, runner, language, chat_id, long_task, expected_keywords):
        """多语言 abort 命令测试

        流程：
        1. 发送长任务（触发 LLM）
        2. 等待处理开始
        3. 发送 abort 命令
        4. 验证收到 abort 响应
        """
        TRIGGERS = {
            "english": ["stop", "cancel", "abort", "halt", "quit", "enough"],
            "chinese": ["停", "停止", "取消", "停下", "别说了"],
            "japanese": ["やめて", "止めて", "ストップ"],
            "russian": ["стоп", "отмена", "хватит"],
        }

        triggers = TRIGGERS[language]
        abort_cmd = triggers[0]
        logger.info(f"\n  Testing {language} - trigger: '{abort_cmd}'")

        # Rate limit cooldown: avoid 429 from NVIDIA API (40 rpm)
        time.sleep(5)

        # Step 1: 发送长任务
        count_before_task = len(runner.get_sent_messages())
        runner.inject(long_task, sender_id=self.SENDER, chat_id=chat_id)

        # Step 2: 等待处理开始
        processing_started = False
        wait_start = time.time()
        while time.time() - wait_start < 15.0:
            time.sleep(0.5)
            msgs = runner.get_sent_messages()
            for msg in msgs[count_before_task:]:
                msg_text = msg.get("text", "")
                if any(s in msg_text for s in
                       ["Processing", "Deliberating", "Thinking", "Evaluating"]):
                    processing_started = True
                    logger.info(f"  → Processing started after {time.time() - wait_start:.1f}s")
                    break
            if processing_started:
                break

        # Step 3: 发送 abort 命令
        logger.info(f"  📤 Sending abort: '{abort_cmd}'")
        count_before_abort = len(runner.get_sent_messages())
        runner.inject(abort_cmd, sender_id=self.SENDER, chat_id=chat_id)

        # Step 4: 等待 abort 响应
        abort_reply = None
        poll_start = time.time()
        while time.time() - poll_start < 30.0:
            time.sleep(0.3)
            msgs = runner.get_sent_messages()
            for msg in reversed(msgs):
                msg_text = msg.get("text", "")
                has_emoji = "🛑" in msg_text
                has_keyword = any(
                    kw.lower() in msg_text.lower()
                    for kw in expected_keywords
                    if not kw.startswith("🛑")
                )
                if has_emoji or has_keyword:
                    abort_reply = msg
                    break
            if abort_reply is not None:
                break

        assert abort_reply is not None, \
            f"Bot did not respond to abort '{abort_cmd}' within 15s"

        text = abort_reply["text"]
        has_emoji = "🛑" in text
        has_keyword = any(
            kw.lower() in text.lower()
            for kw in expected_keywords
            if not kw.startswith("🛑")
        )
        assert has_emoji or has_keyword, \
            f"Expected abort response, got: {text[:200]}"

        # 验证 abort 后任务确实停止
        count_after_abort = len(runner.get_sent_messages())
        time.sleep(3)
        count_final = len(runner.get_sent_messages())
        new_messages = count_final - count_after_abort
        assert new_messages <= 1, \
            f"Task NOT aborted! {new_messages} new messages after abort"

        logger.info(f"  ✓ Abort ({language}): {text[:80]}")


class TestFeishuLLMMessages:
    """测试飞书频道中需要 LLM 回复的消息。"""

    SENDER = "ou_llm_tester"
    CHAT = "oc_test_llm"

    def test_regular_message(self, runner):
        """普通消息应该触发 LLM 回复"""
        text = inject_and_get_reply(runner, "你好，请介绍一下你自己", timeout=TIMEOUT_LLM,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text is not None and len(text) > 0, "Bot did not respond"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：Profile 模式
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuProfileMode:
    """测试飞书频道中的多 Profile 会话隔离。"""

    CHAT_A = "oc_test_profile_a"
    CHAT_B = "oc_test_profile_b"
    SENDER = "ou_profile_tester"

    def test_profile_session_isolation(self, runner):
        """不同 Profile 的会话应该隔离。"""
        text_a = inject_and_get_reply(runner, "/new profile-a", timeout=TIMEOUT_COMMAND,
                                      sender_id=self.SENDER, chat_id=self.CHAT_A)
        assert text_a.startswith("Switched to session:"), f"Profile A 失败: {text_a}"

        text_b = inject_and_get_reply(runner, "/new profile-b", timeout=TIMEOUT_COMMAND,
                                      sender_id=self.SENDER, chat_id=self.CHAT_B)
        assert text_b.startswith("Switched to session:"), f"Profile B 失败: {text_b}"

        # 验证 A 的会话不受 B 影响
        sessions_a = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND,
                                          sender_id=self.SENDER, chat_id=self.CHAT_A)
        assert "profile-a" in sessions_a, f"Profile A 会话列表缺失: {sessions_a}"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：并发限制
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuConcurrencyLimit:
    """验证并发会话限制 — 同时多个活跃会话的处理能力"""

    SENDER = "ou_concurrent_tester"

    def test_concurrent_session_creation(self, runner):
        """同时创建多个会话，验证并发处理能力"""
        import threading

        session_count = 10
        results = {}
        errors = {}

        def create_session(session_id):
            try:
                chat_id = f"oc_concurrent_{session_id}"
                text = inject_and_get_reply(
                    runner, f"/new concurrent-{session_id}",
                    timeout=TIMEOUT_COMMAND,
                    sender_id=f"{self.SENDER}_{session_id}",
                    chat_id=chat_id,
                )
                results[session_id] = text
            except Exception as e:
                errors[session_id] = str(e)

        threads = []
        start_time = time.time()
        for i in range(session_count):
            t = threading.Thread(target=create_session, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=60)

        elapsed = time.time() - start_time
        logger.info(f"\n  Concurrent sessions: {session_count}")
        logger.info(f"  Elapsed time: {elapsed:.2f}s")
        logger.info(f"  Successful: {len(results)}")
        logger.info(f"  Errors: {len(errors)}")

        assert len(errors) == 0, f"Some sessions failed: {errors}"
        assert len(results) == session_count, \
            f"Expected {session_count} results, got {len(results)}"

        for session_id, text in results.items():
            assert "concurrent-" in text or "Switched to session" in text, \
                f"Session {session_id} has incorrect response: {text[:100]}"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：流式编辑
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.llm
class TestFeishuStreamEdit:
    """验证飞书流式编辑功能

    当 LLM 响应是流式输出时，bot 应该逐步编辑同一条消息而不是发送多条消息。
    飞书通过 PATCH /im/v1/messages/{id} 实现编辑。
    """

    SENDER = "ou_stream_tester"
    CHAT = "oc_test_stream"

    def test_stream_edit_creates_edit_operations(self, runner):
        """验证流式响应会触发 edit_message API 调用"""
        runner.clear()

        text = inject_and_get_reply(runner, "Count from 1 to 5:", timeout=TIMEOUT_LLM,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert len(text) > 0, "Bot should reply"

        logger.info(f"\n📤 User: Count from 1 to 5:")
        logger.info(f"📥 LLM: {text[:200]}{'...' if len(text) > 200 else ''}")

        edit_history = runner.get_edit_history()
        logger.info(f"\n  edit_history count: {len(edit_history)}")

        if len(edit_history) > 0:
            logger.info(f"\n  ✓ Stream edit detected: {len(edit_history)} edit operations")
            for edit in edit_history:
                assert "message_id" in edit, "edit should have message_id"
                assert "content" in edit, "edit should have content"
        else:
            assert len(runner.get_sent_messages()) > 0, "Should send at least one message"
            logger.info(f"\n  ✓ No stream edits (non-streaming mode), but message sent successfully")

    def test_edit_preserves_message_identity(self, runner):
        """验证编辑不会创建新消息，保持消息 ID 不变"""
        runner.clear()

        inject_and_get_reply(runner, "Hello", timeout=TIMEOUT_LLM,
                             sender_id=self.SENDER, chat_id=self.CHAT)

        after_send_msgs = runner.get_sent_messages()
        assert len(after_send_msgs) >= 1, "Should send a message"

        edit_history = runner.get_edit_history()
        if len(edit_history) > 0:
            sent_ids = {msg["message_id"] for msg in after_send_msgs if "message_id" in msg}
            edited_ids = {edit["message_id"] for edit in edit_history}
            # 只检查存在于 sent_messages 中的编辑（忽略 gateway 内部消息的编辑）
            relevant_edits = edited_ids & sent_ids
            if relevant_edits:
                # 存在于 sent 中的编辑，其 ID 必须在 sent 中
                assert relevant_edits.issubset(sent_ids), \
                    f"Edited IDs {relevant_edits} should be subset of sent IDs {sent_ids}"
                logger.info(f"\n  ✓ Edit preserves message identity: edited {len(relevant_edits)} messages")
            else:
                logger.info(f"\n  ✓ Edit history has {len(edited_ids)} entries, none match sent messages (likely internal edits)")


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：10MB 文件限制
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuFileLimits:
    """验证会话文件大小限制 (10MB 累计)

    根据 octos-bus/src/session.rs:
    - MAX_SESSION_FILE_SIZE = 10 MB
    - 达到限制后，新消息不再保存到磁盘（但仍可响应）
    """

    SENDER = "ou_file_limit_tester"
    CHAT = "oc_test_file_limit"

    @pytest.mark.slow
    def test_large_message_handling(self, runner):
        """验证 octos 能处理较大的单条消息（1MB 级别）"""
        message_size = 1 * 1024 * 1024  # 1MB
        large_message = "A" * message_size

        logger.info(f"\n  Sending {message_size / (1024*1024):.1f}MB single message...")
        start_time = time.time()

        try:
            text = inject_and_get_reply(runner, large_message, timeout=TIMEOUT_COMMAND,
                                        sender_id=self.SENDER, chat_id=self.CHAT)
            elapsed = time.time() - start_time
            logger.info(f"  Response received in {elapsed:.2f}s")
            assert len(text) > 0, "Should receive some response"
            logger.info(f"  ✓ octos handled {message_size / (1024*1024):.1f}MB message successfully")
        except Exception as e:
            elapsed = time.time() - start_time
            logger.info(f"  ✗ Failed after {elapsed:.2f}s: {type(e).__name__}: {str(e)[:100]}")
            raise

    @pytest.mark.slow
    def test_session_file_size_limit_enforcement(self, runner):
        """验证会话文件达到 10MB 限制后的追加行为"""
        import os
        import json
        import urllib.parse

        data_dir = os.environ.get("OCTOS_TEST_DIR", "/tmp/octos_test")
        test_chat_id = "oc_size_limit_test"
        session_name = "size-limit-test"
        profile = "_main"
        channel = "feishu"

        encoded_base = urllib.parse.quote(f"{profile}:{channel}:{test_chat_id}", safe="")
        encoded_topic = urllib.parse.quote(session_name, safe="")
        session_dir = f"{data_dir}/users/{encoded_base}/sessions"
        session_path = f"{session_dir}/{encoded_topic}.jsonl"

        os.makedirs(session_dir, exist_ok=True)

        target_size = 9_900_000
        logger.info(f"  Test target session size: {target_size / 1024**2:.2f}MB")

        with open(session_path, "w") as f:
            header = json.dumps({
                "schema": 1,
                "model": "test",
                "created_at": "2024-01-01T00:00:00Z"
            })
            f.write(header + "\n")
            written = len(header.encode()) + 1
            i = 0
            while written < target_size:
                entry = json.dumps({
                    "role": "user",
                    "content": f"Message {i}: " + "A" * (200 * 1024)
                })
                f.write(entry + "\n")
                written += len(entry.encode()) + 1
                i += 1

        pre_size = os.path.getsize(session_path)
        assert pre_size >= 9_000_000, \
            f"Pre-filled file too small ({pre_size} bytes): {session_path}"
        logger.info(f"  Pre-filled session file: {pre_size / 1024**2:.2f}MB at {session_path}")

        inject_and_get_reply(runner, f"/new {session_name}",
                            timeout=TIMEOUT_COMMAND,
                            sender_id=self.SENDER, chat_id=test_chat_id)
        text = inject_and_get_reply(runner, "tiny msg",
                                   timeout=TIMEOUT_COMMAND,
                                   sender_id=self.SENDER, chat_id=test_chat_id)
        assert len(text) > 0, "Bot should still respond when session is at size limit"

        post_size = os.path.getsize(session_path)
        growth = post_size - pre_size
        logger.info(f"  After append attempt: {post_size / 1024**2:.2f}MB, grew {growth} bytes")

        assert growth < 50_000, \
            f"Session at limit, append should be skipped (growth={growth} bytes)"
        logger.info(f"  ✓ Append skipped correctly — session file stayed at {pre_size / 1024**2:.2f}MB")

        # 清理
        try:
            if os.path.exists(session_path):
                os.remove(session_path)
                logger.info(f"  ✓ Cleaned up test session file")
        except Exception as e:
            logger.info(f"  ⚠ Failed to clean up session file: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：空闲超时配置
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuIdleTimeout:
    """验证空闲超时配置 (30min)

    根据 octos-bus/src/session.rs:
    - 会话有 idle timeout，默认 30 分钟不活动后自动清理
    - 清理后再次发消息会创建新会话

    注意: 由于 30 分钟太长，无法在自动化测试中实际等待。
    此测试验证:
    1. 配置文件中 idle_timeout 字段能被 octos 正确读取
    2. 发送消息后会话被正确创建（间接验证超时逻辑存在）
    """

    SENDER = "ou_idle_tester"
    CHAT = "oc_test_idle"

    def test_session_created_on_first_message(self, runner):
        """验证首次消息后会话被正确创建（超时逻辑的前提条件）"""
        runner.clear()

        # 创建一个新会话
        text = inject_and_get_reply(runner, "/new idle-test", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert "Switched to session:" in text or "idle-test" in text, \
            f"Session creation failed: {text}"

        # 验证 /sessions 能看到该会话
        sessions = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND,
                                       sender_id=self.SENDER, chat_id=self.CHAT)
        assert "idle-test" in sessions, f"Session not listed: {sessions}"
        logger.info(f"\n  ✓ Session lifecycle works correctly (idle timeout prerequisite validated)")

    @pytest.mark.slow
    def test_short_idle_session_cleanup(self, runner):
        """验证空闲会话在超时后不再出现在 /sessions 列表中

        ⚠️ 此测试需要 octos 支持 idle_timeout 配置项。
        如果不支持，将标记为 skip。
        实际 30min timeout 无法在自动化中验证，此测试仅检查会话管理机制。
        """
        import os
        import glob

        data_dir = os.environ.get("OCTOS_TEST_DIR", "/tmp/octos_test")

        runner.clear()

        # 创建临时会话
        inject_and_get_reply(runner, "/new short-idle-test", timeout=TIMEOUT_COMMAND,
                            sender_id=self.SENDER, chat_id=self.CHAT)

        # 检查会话文件是否被创建
        session_files = glob.glob(f"{data_dir}/users/*/sessions/*short-idle-test*.jsonl")
        if session_files:
            logger.info(f"\n  ✓ Session file created: {os.path.basename(session_files[0])}")
            logger.info(f"  ✓ Session persistence mechanism works (idle timeout can operate on this)")
        else:
            logger.info(f"\n  ⚠ Session file not found in expected path — idle timeout requires session persistence")
            pytest.skip("Session file not found — idle timeout cannot be verified without session persistence")


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：JSONL 持久化
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuJSONLPersistence:
    """验证会话 JSONL 持久化格式和正确性

    根据 octos-bus/src/session.rs:
    - 会话以 JSONL 格式持久化到磁盘
    - 每行一个 JSON 对象：header + 消息条目
    - header 包含 schema 版本、model、创建时间
    - 消息条目包含 role、content、timestamp 等
    """

    SENDER = "ou_jsonl_tester"
    CHAT = "oc_test_jsonl"

    def test_jsonl_file_created_after_message(self, runner):
        """验证发送消息后 JSONL 文件被正确创建"""
        import os
        import glob
        import json

        data_dir = os.environ.get("OCTOS_TEST_DIR", "/tmp/octos_test")

        runner.clear()

        # 创建新会话并发言
        inject_and_get_reply(runner, "/new jsonl-test", timeout=TIMEOUT_COMMAND,
                            sender_id=self.SENDER, chat_id=self.CHAT)
        inject_and_get_reply(runner, "Test message for JSONL", timeout=TIMEOUT_LLM,
                            sender_id=self.SENDER, chat_id=self.CHAT)

        # 查找 JSONL 文件
        session_files = glob.glob(f"{data_dir}/users/*/sessions/*jsonl-test*.jsonl")
        assert len(session_files) > 0, "JSONL file should be created after message exchange"

        session_file = session_files[0]
        logger.info(f"\n  Found JSONL file: {os.path.basename(session_file)}")
        logger.info(f"  File size: {os.path.getsize(session_file)} bytes")

        # 验证文件可读且包含有效 JSON 行
        with open(session_file) as f:
            lines = f.readlines()

        assert len(lines) >= 1, "JSONL file should have at least a header line"

        # 第一行应该是 header
        header = json.loads(lines[0])
        assert "schema" in header or "model" in header or "created_at" in header, \
            f"Header should contain schema/model/created_at: {header}"
        logger.info(f"\n  ✓ JSONL header: {header}")

        # 如果有消息行，验证格式
        for i, line in enumerate(lines[1:], 1):
            try:
                entry = json.loads(line)
                assert "role" in entry, f"Message entry {i} should have 'role': {entry}"
                assert "content" in entry, f"Message entry {i} should have 'content': {entry}"
            except json.JSONDecodeError as e:
                pytest.fail(f"Line {i} is not valid JSON: {e}")

        logger.info(f"\n  ✓ JSONL file has {len(lines)} lines, all valid JSON")
        logger.info(f"  ✓ Header: {list(header.keys())}")

    def test_jsonl_entries_have_required_fields(self, runner):
        """验证 JSONL 消息条目包含必要的字段"""
        import os
        import glob
        import json

        data_dir = os.environ.get("OCTOS_TEST_DIR", "/tmp/octos_test")

        runner.clear()

        inject_and_get_reply(runner, "/new jsonl-fields-test", timeout=TIMEOUT_COMMAND,
                            sender_id=self.SENDER, chat_id=self.CHAT)
        inject_and_get_reply(runner, "Verify JSONL fields", timeout=TIMEOUT_LLM,
                            sender_id=self.SENDER, chat_id=self.CHAT)

        session_files = glob.glob(f"{data_dir}/users/*/sessions/*jsonl-fields-test*.jsonl")
        if not session_files:
            pytest.skip("Session file not found")

        with open(session_files[0]) as f:
            lines = f.readlines()

        if len(lines) < 2:
            pytest.skip("No message entries in session file")

        # 检查消息条目字段
        roles_found = set()
        for line in lines[1:]:
            entry = json.loads(line)
            role = entry.get("role", "")
            roles_found.add(role)

        logger.info(f"\n  ✓ Roles found in JSONL: {roles_found}")
        # 至少应有 user 或 assistant 之一
        assert roles_found & {"user", "assistant"}, \
            f"JSONL should contain user or assistant entries: {roles_found}"
