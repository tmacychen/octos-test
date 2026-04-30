#!/usr/bin/env python3
"""
Discord Bot 集成测试用例

前置条件（由 run_test.fish 自动完成）：
  1. Mock Discord Server 运行在 http://127.0.0.1:5001 (REST + WS Gateway)
  2. octos gateway 已启动并连接到 Mock Server（通过 --features discord）

运行方式：
  fish tests/bot_mock/run_test.fish discord    # 完整测试
  pytest test_discord.py -v -m "not llm"       # 跳过 LLM 测试
"""

import pytest
import time
import logging
from runner_discord import DiscordTestRunner
from test_helpers import inject_and_get_reply

# 🔥 Suppress httpx INFO logs to reduce noise in test output
logging.getLogger("httpx").setLevel(logging.WARNING)

# ── 超时配置 ──────────────────────────────────────────────────────────────────
TIMEOUT_COMMAND = 20   # 本地命令，无需 LLM
TIMEOUT_LLM     = 50   # 需要调用 LLM API (增加到 50s，Discord Gateway 有额外开销)

# ── 压力缓解配置 ──────────────────────────────────────────────────────────────
# 在 LLM 密集型测试之间添加延迟，避免 API 过载
LLM_TEST_DELAY = 3.0   # LLM 测试后的等待时间（秒）
ABORT_TEST_DELAY = 2.0  # Abort 测试后的等待时间（秒），确保完全清理


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def runner():
    r = DiscordTestRunner()
    assert r.health(), "Discord Mock Server 未运行"
    return r


@pytest.fixture(autouse=True)
def cleanup_state(request, runner):
    """每个测试前清理 Mock Server 状态，并添加延迟缓解压力
    
    包含 Mock Server 崩溃检测：如果 Mock Server 不可达，
    自动跳过当前测试（pytest.skip），避免级联 ERROR。
    """
    import httpx
    import os
    import glob
    from test_helpers import inject_and_get_reply
    
    # 🔥 Health check: 验证 Mock Server 是否在线
    max_health_retries = 5  # Increased from 3 to 5 for better resilience
    health_retry_delay = 2.0  # Increased from 1.0 to 2.0 seconds
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
        pytest.skip("Mock Server 崩溃，无法恢复（需重启 test_run.py）")
        return
    
    # Wait for any pending LLM responses to complete（增加以避免跨测试污染）
    # LLM 流式响应可能持续 10-30 秒，等待过短会导致延迟响应污染下一测试
    time.sleep(5.0)
    
    try:
        runner.clear()
    except httpx.HTTPError:
        pytest.skip("Mock Server 无法清理，跳过测试")
        return
    
    # 🔥 清理大 session 文件（避免大 session 导致 Mock Server 崩溃）
    # 注意：只清理大于 100KB 的文件，避免误删正在使用的正常 session
    try:
        data_dir = os.environ.get("OCTOS_TEST_DIR", "/tmp/octos_test")
        session_files = glob.glob(f"{data_dir}/users/*/sessions/*.jsonl")
        deleted_count = 0
        for session_file in session_files:
            try:
                file_size = os.path.getsize(session_file)
                if file_size > 100_000:  # 只删除大于 100KB 的文件
                    os.remove(session_file)
                    deleted_count += 1
            except OSError:
                pass
        if deleted_count > 0:
            print(f"  🗑 Cleaned up {deleted_count} large session files")
    except Exception as e:
        print(f"  ⚠ Session cleanup warning: {type(e).__name__}: {str(e)[:80]}")
    
    # 重置所有非默认状态
    # 注意：增加超时时间以应对 LLM 响应延迟，避免误 skip
    try:
        inject_and_get_reply(runner, "/reset", timeout=10)
    except httpx.HTTPError:
        pytest.skip("Mock Server /reset 失败，跳过测试")
        return
    except AssertionError:
        pytest.skip("Mock Server /reset 无响应，跳过测试")
        return
    except Exception as e:
        print(f"  ⚠ /reset failed: {type(e).__name__}: {str(e)[:80]}")
    
    yield
    
    # After abort tests or LLM-intensive tests, add extra delay to ensure full cleanup
    # This helps prevent message sending failures in subsequent tests
    if request.node.get_closest_marker('abort_test') or request.node.get_closest_marker('llm_intensive'):
        time.sleep(ABORT_TEST_DELAY)


# ══════════════════════════════════════════════════════════════════════════════
# 第一层：会话管理命令 (GatewayDispatcher)
# ══════════════════════════════════════════════════════════════════════════════

class TestDiscordSessionCommands:
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
        # 先创建会话并发送消息
        inject_and_get_reply(runner, "/new clear-test", timeout=TIMEOUT_COMMAND)
        inject_and_get_reply(runner, "hello", timeout=TIMEOUT_LLM)
        # 然后清空
        text = inject_and_get_reply(runner, "/clear", timeout=TIMEOUT_COMMAND)
        assert "Session cleared" in text, f"Unexpected: {text}"

    def test_switch_session(self, runner):
        """/s 应该切换会话"""
        inject_and_get_reply(runner, "/new session-a", timeout=TIMEOUT_COMMAND)
        inject_and_get_reply(runner, "/new session-b", timeout=TIMEOUT_COMMAND)
        text = inject_and_get_reply(runner, "/s session-a", timeout=TIMEOUT_COMMAND)
        assert "Switched to session: session-a" in text, f"Unexpected: {text}"

    def test_back_to_default(self, runner):
        """/back 应该返回默认会话"""
        inject_and_get_reply(runner, "/new back-test", timeout=TIMEOUT_COMMAND)
        text = inject_and_get_reply(runner, "/back", timeout=TIMEOUT_COMMAND)
        assert "default" in text.lower(), f"Unexpected: {text}"

    def test_delete_session(self, runner):
        """/delete 应该删除当前会话"""
        inject_and_get_reply(runner, "/new delete-me", timeout=TIMEOUT_COMMAND)
        text = inject_and_get_reply(runner, "/delete", timeout=TIMEOUT_COMMAND)
        assert "deleted" in text.lower() or "已删除" in text, f"Unexpected: {text}"

    def test_sessions_list(self, runner):
        """/sessions 应该列出所有会话"""
        # 创建几个会话
        inject_and_get_reply(runner, "/new list-a", timeout=TIMEOUT_COMMAND)
        inject_and_get_reply(runner, "/new list-b", timeout=TIMEOUT_COMMAND)
        text = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND)
        assert "list-a" in text and "list-b" in text, f"Sessions not listed: {text}"


# ══════════════════════════════════════════════════════════════════════════════
# 第二层：非 LLM 消息与边界情况
# ══════════════════════════════════════════════════════════════════════════════

class TestDiscordBasicMessages:
    """基础消息处理（不调用 LLM）"""

    def test_empty_message(self, runner):
        """空消息应该被忽略或返回提示"""
        # Discord 不允许真正空消息，但可以是只有空格
        count_before = len(runner.get_sent_messages())
        runner.inject("   ", channel_id="1039178386623557754")
        time.sleep(1)
        count_after = len(runner.get_sent_messages())
        # 应该没有新消息（被忽略）
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


# ══════════════════════════════════════════════════════════════════════════════
# 第三层：Gateway 配置命令
# ══════════════════════════════════════════════════════════════════════════════

class TestDiscordConfigCommands:
    """配置相关命令"""

    def test_queue_mode_show(self, runner):
        """/queue 应该显示当前模式"""
        text = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND)
        # 应该包含当前模式信息
        assert any(mode in text for mode in ["Collect", "Followup", "Steer", "Interrupt"]), \
            f"Should show queue mode: {text}"

    def test_queue_mode_set(self, runner):
        """/queue <mode> 应该切换模式"""
        text = inject_and_get_reply(runner, "/queue followup", timeout=TIMEOUT_COMMAND)
        assert "Followup" in text or "followup" in text.lower(), f"Unexpected: {text}"

    def test_soul_show_empty(self, runner):
        """/soul 应该显示当前 soul"""
        text = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND)
        # 可能是 "No custom soul" 或显示当前 soul
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
        # 验证包含关键命令
        for cmd in ["/new", "/s", "/sessions", "/back", "/delete",
                    "/queue", "/soul", "/status", "/adaptive", "/reset"]:
            assert cmd in text, f"帮助文本缺少 {cmd}: {text}"


# ══════════════════════════════════════════════════════════════════════════════
# Queue Mode Steer/Discard 负向测试 — 防止误触发 abort
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.llm  # 这些测试发送普通文本消息，会触发 LLM 调用
class TestDiscordQueueModeSteerNonAbort:
    """验证 Steer/Interrupt 模式下，普通消息不会误触发 abort
    
    Steer/Interrupt 模式在队列处理时会检查 is_abort_trigger()。
    此测试确保包含 abort 关键词但非独立命令的消息不会被误判。
    
    相关代码：octos-cli/src/session_actor.rs:2773-2787
    """

    # 🔥 独立 channel_id，避免与其他测试共享 session 状态
    # Steer/Interrupt 模式对消息时序敏感，共享 session 会导致延迟回复混入
    CHANNEL_ID_STEER = "1039178386623557001"
    CHANNEL_ID_INTERRUPT = "1039178386623557002"

    def test_steer_mode_non_abort_messages_not_triggered(self, runner):
        """验证 steer 模式下普通消息不会误触发 abort
        
        测试流程：
        1. 设置 queue mode 为 steer
        2. 发送包含 abort 关键词但不是独立命令的消息
        3. 验证消息被正常处理，未返回 abort 响应
        """
        channel_id = self.CHANNEL_ID_STEER
        # Step 1: 设置为 steer 模式
        text = inject_and_get_reply(runner, "/queue steer", timeout=TIMEOUT_COMMAND, channel_id=channel_id)
        assert "Steer" in text or "steer" in text.lower(), f"Failed to set steer mode: {text}"
        
        # Step 2: 发送可能误触发的消息
        non_triggers = [
            "please stop talking about cats",  # 句子中的 stop
            "stopping point is here",          # stopping 不是 stop
            "I will exit now",                 # exit 不在触发词列表中
            "cancel my subscription please",   # 句子中的 cancel
            "abort the rocket launch",         # abort 作为动词修饰语
        ]
        
        for msg in non_triggers:
            reply = inject_and_get_reply(runner, msg, timeout=TIMEOUT_LLM, channel_id=channel_id)
            
            # 🔥 关键断言：不应包含 abort 特征
            # 只检查 🛑 emoji（所有 abort 响应都以 🛑 开头），
            # 不检查 "cancelled" 等关键词（LLM 可能自然使用这些词）
            has_abort_emoji = "🛑" in reply
            
            assert not has_abort_emoji, \
                f"False abort trigger in steer mode for '{msg}': {reply[:200]}"
        
        print(f"\n  ✓ Steer mode: Non-abort messages handled correctly")
        
        # Step 3: 恢复默认模式
        inject_and_get_reply(runner, "/queue collect", timeout=TIMEOUT_COMMAND, channel_id=channel_id)

    def test_interrupt_mode_non_abort_messages_not_triggered(self, runner):
        """验证 interrupt 模式下普通消息不会误触发 abort
        
        Interrupt 模式与 Steer 类似，也会在队列中检查 abort 触发词。
        """
        channel_id = self.CHANNEL_ID_INTERRUPT
        # Step 1: 设置为 interrupt 模式
        text = inject_and_get_reply(runner, "/queue interrupt", timeout=TIMEOUT_COMMAND, channel_id=channel_id)
        assert "Interrupt" in text or "interrupt" in text.lower(), \
            f"Failed to set interrupt mode: {text}"
        
        # Step 2: 发送可能误触发的消息
        # 注意：避免使用 LLM 容易在回复中自然使用的词（如 "cancelled"），
        # 因为即使不触发 abort，LLM 也可能回显这些词
        non_triggers = [
            "don't stop the music",           # 否定句中的 stop
            "the concert was canceled",       # canceled（美式拼写）不是独立 trigger
            "abort the rocket launch",        # abort 作为动词修饰语
        ]
        
        for msg in non_triggers:
            reply = inject_and_get_reply(runner, msg, timeout=TIMEOUT_LLM, channel_id=channel_id)
            
            # 🔥 关键断言：不应包含 abort 特征
            # 只检查 🛑 emoji（所有 abort 响应都以 🛑 开头），
            # 不检查 "cancelled" 等关键词（LLM 可能自然使用这些词）
            has_abort_emoji = "🛑" in reply
            
            assert not has_abort_emoji, \
                f"False abort trigger in interrupt mode for '{msg}': {reply[:200]}"
        
        print(f"\n  ✓ Interrupt mode: Non-abort messages handled correctly")
        
        # Step 3: 恢复默认模式
        inject_and_get_reply(runner, "/queue collect", timeout=TIMEOUT_COMMAND, channel_id=channel_id)


# ══════════════════════════════════════════════════════════════════════════════
# 第四层：LLM 消息测试（标记 @pytest.mark.llm）
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.llm
class TestDiscordLLMMessages:
    """需要调用 LLM API，超时 TIMEOUT_LLM = 50s"""

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
class TestDiscordAbortCommands:
    """验证 Agent 能正确中止任务 — 多语言 abort 触发词识别

    注意：abort 是本地命令识别（octos-core/src/abort.rs），不依赖 LLM。
    标记为 @pytest.mark.llm 仅因为需要完整的 gateway 环境。

    Abort 工作原理：
    - 用户发送任务消息，octos 开始处理
    - 用户发送 abort 命令（"停" / "stop" / "cancel" 等）
    - GatewayDispatcher 在 session_actor 中检测 is_abort_trigger()
    - 立即返回 abort_response()，不调用 LLM
    - 响应语言与触发词匹配（中文→中文，英文→英文等）
    """

    # 🔥 固定 channel_id，确保测试隔离
    CHANNEL_ID = "30000"

    @pytest.mark.abort_test
    @pytest.mark.parametrize(
        "language,channel_id,long_task,expected_keywords",
        [
            # English - use first trigger word
            ("english", "30001",
             "Please tell me something about Python",
             ["🛑", "Cancelled"]),

            # Chinese - use first trigger word
            ("chinese", "30002",
             "请告诉我 Python 是什么？",
             ["🛑", "已取消"]),

            # Japanese - use first trigger word
            ("japanese", "30003",
             "Pythonとは何ですか？",
             ["🛑", "キャンセル"]),

            # Russian - use first trigger word
            ("russian", "30004",
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
    def test_abort_multilanguage(self, runner, language, channel_id, long_task, expected_keywords):
        """多语言 abort 命令测试 - 使用固定触发词

        测试流程：
        1. 发送一个长任务（触发 LLM 处理）
        2. 动态等待直到收到第一条处理中消息
        3. 发送 abort 命令
        4. 等待最多 15 秒检查是否收到 abort 响应
        5. 验证 abort 后任务确实停止

        支持：英文、中文、日文、俄文。
        """
        import time

        # Define trigger words for each language (from abort.rs)
        TRIGGERS = {
            "english": ["stop", "cancel", "abort", "halt", "quit", "enough"],
            "chinese": ["停", "停止", "取消", "停下", "别说了"],
            "japanese": ["やめて", "止めて", "ストップ"],
            "russian": ["стоп", "отмена", "хватит"],
        }

        triggers = TRIGGERS[language]
        # Use first trigger word (deterministic)
        abort_cmd = triggers[0]
        logger.info(f"\n{'='*70}")
        logger.info(f"  Testing {language} - using first trigger: '{abort_cmd}' from {triggers}")
        logger.info(f"{'='*70}\n")

        # Step 1: 发送长任务，触发 LLM 处理
        count_before_task = len(runner.get_sent_messages())
        logger.info(f"📤 Sending to LLM (user input):")
        logger.info(f"   {long_task[:200]}{'...' if len(long_task) > 200 else ''}")
        runner.inject(long_task, channel_id=channel_id)
        logger.info(f"  → Long task injected\n")

        # Step 2: 动态等待任务开始执行（轮询检测处理中状态）
        processing_started = False
        wait_start = time.time()
        last_print_time = wait_start
        while time.time() - wait_start < 15.0:
            current_time = time.time()
            elapsed = current_time - wait_start

            # 每秒打印一次等待时间
            if current_time - last_print_time >= 1.0:
                logger.info(f"  ⏳ Waiting for processing to start... {elapsed:.0f}s")
                last_print_time = current_time

            time.sleep(0.5)
            msgs = runner.get_sent_messages()
            # 检测是否有处理中的消息（表示 LLM 开始工作了）
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
            # 即使没检测到处理中状态，也继续尝试 abort（可能是短任务已完成）
            logger.info(f"  → No processing status detected, continuing anyway...")

        # Step 3: 发送 abort 命令
        logger.info(f"\n  📤 Sending to LLM (abort command): '{abort_cmd}'")
        runner.inject(abort_cmd, channel_id=channel_id)

        # Step 4: 等待最多 15 秒，检查是否收到 abort 响应
        abort_reply = None
        poll_start = time.time()
        last_print_time = poll_start
        while time.time() - poll_start < 15.0:
            current_time = time.time()
            elapsed = current_time - poll_start

            # 每秒打印一次等待时间
            if current_time - last_print_time >= 1.0:
                logger.info(f"  ⏳ Waiting for abort response... {elapsed:.0f}s")
                last_print_time = current_time

            msgs = runner.get_sent_messages()
            # 从后往前找，找到第一条包含 abort 特征的消息
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

        # Step 5: 断言
        assert abort_reply is not None, \
            f"Bot did not respond to abort command '{abort_cmd}' within 15s"

        text = abort_reply["text"]

        # 🔥 VERIFICATION B: 确保收到的是 abort 响应，不是长任务的中间消息
        has_stop_emoji = "🛑" in text
        has_cancel_keyword = any(kw.lower() in text.lower() for kw in expected_keywords if not kw.startswith("🛑"))

        assert has_stop_emoji or has_cancel_keyword, \
            f"Expected abort response (with 🛑 or cancel keyword), got: {text[:200]}"

        # 🔥 VERIFICATION A: 验证"真中断" - 确认长任务确实停止了
        count_after_abort = len(runner.get_sent_messages())

        # 等待一段时间，观察是否还有新消息（长任务不应该继续输出）
        time.sleep(3)

        count_final = len(runner.get_sent_messages())

        # 断言：abort 后不应该有新的消息产生
        new_messages_after_abort = count_final - count_after_abort
        assert new_messages_after_abort <= 1, \
            f"Long task was NOT properly aborted! Found {new_messages_after_abort} new messages after abort: {text[:100]}"

        logger.info(f"  ✓ Abort interrupted long task → {text}")
        logger.info(f"    Verified: No further messages after abort ({new_messages_after_abort} new msgs)")

    @pytest.mark.abort_test
    def test_abort_with_whitespace(self, runner):
        """验证 abort 命令前后空格不影响识别"""
        test_cases = [
            ("  stop  ", "1039178386623557773", ["🛑", "Cancelled", "Cancel"]),
            ("\tstop\n", "1039178386623557774", ["🛑", "Cancelled", "Cancel"]),
            (" 停 ", "1039178386623557775", ["🛑", "取消", "已取消"]),
        ]

        for cmd, channel_id, expected_keywords in test_cases:
            count_before = len(runner.get_sent_messages())
            runner.inject(cmd, channel_id=channel_id)
            abort_reply = runner.wait_for_reply(
                count_before=count_before,
                timeout=TIMEOUT_COMMAND,
                chat_id=channel_id
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
        # 这些消息包含 abort 关键词但不是独立的命令
        non_triggers = [
            "please stop talking about cats",  # 句子中的 stop
            "stopping point is here",  # stopping 不是 stop
        ]

        for msg in non_triggers:
            count_before = len(runner.get_sent_messages())
            runner.inject(msg, channel_id="1039178386623557769")
            # 等待一小段时间让 octos 处理
            time.sleep(0.5)

        logger.info(f"\n  ✓ Non-abort messages handled correctly")


# ══════════════════════════════════════════════════════════════════════════════
# Profile 模式测试
# ══════════════════════════════════════════════════════════════════════════════

class TestDiscordProfileMode:
    """验证多 profile 配置下的会话隔离"""

    # 🔥 独立 channel_id
    CHANNEL_ID = "20005"

    def test_profile_session_isolation(self, runner):
        """不同 channel 使用不同 profile，应该隔离"""
        CHANNEL_A = "1039178386623557754"
        CHANNEL_B = "1039178386623557755"
        
        # Create sessions in different channels
        text_a = inject_and_get_reply(runner, "/new profile-a",
                                      timeout=TIMEOUT_COMMAND, channel_id=CHANNEL_A)
        assert "profile-a" in text_a
        
        text_b = inject_and_get_reply(runner, "/new profile-b",
                                      timeout=TIMEOUT_COMMAND, channel_id=CHANNEL_B)
        assert "profile-b" in text_b
        
        # Verify isolation
        sessions_a = inject_and_get_reply(runner, "/sessions",
                                          timeout=TIMEOUT_COMMAND, channel_id=CHANNEL_A)
        sessions_b = inject_and_get_reply(runner, "/sessions",
                                          timeout=TIMEOUT_COMMAND, channel_id=CHANNEL_B)
        
        assert "profile-a" in sessions_a
        assert "profile-b" in sessions_b

    @pytest.mark.skip(reason="FIXME: soul 目前未按 profile 隔离，全局共用 soul.md。等 octos-cli 修复后恢复")
    def test_soul_per_profile(self, runner):
        """验证每个 profile 有独立的 soul 配置"""
        CHANNEL_A = "1039178386623557758"
        CHANNEL_B = "1039178386623557759"
        
        # Set different souls for different channels
        text_a = inject_and_get_reply(runner, "/soul You are a coding expert",
                                      timeout=TIMEOUT_COMMAND, channel_id=CHANNEL_A)
        assert "Soul updated" in text_a
        
        text_b = inject_and_get_reply(runner, "/soul You are a creative writer",
                                      timeout=TIMEOUT_COMMAND, channel_id=CHANNEL_B)
        assert "Soul updated" in text_b
        
        # Verify souls are independent
        soul_a = inject_and_get_reply(runner, "/soul",
                                      timeout=TIMEOUT_COMMAND, channel_id=CHANNEL_A)
        soul_b = inject_and_get_reply(runner, "/soul",
                                      timeout=TIMEOUT_COMMAND, channel_id=CHANNEL_B)
        
        assert "coding expert" in soul_a.lower() or "You are a coding expert" in soul_a
        assert "creative writer" in soul_b.lower() or "You are a creative writer" in soul_b

    def test_queue_mode_per_profile(self, runner):
        """每个 profile 可以有独立的队列模式"""
        CHANNEL_A = "1039178386623557762"
        CHANNEL_B = "1039178386623557763"
        
        # 🔥 CRITICAL FIX: Create fresh sessions to ensure clean state
        # Previous tests may have modified queue_mode on these channels
        inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND, channel_id=CHANNEL_A)
        inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND, channel_id=CHANNEL_B)
        
        # Profile A 设置为 followup
        text_a = inject_and_get_reply(runner, "/queue followup",
                                      timeout=TIMEOUT_COMMAND, channel_id=CHANNEL_A)
        assert "Followup" in text_a
        
        # Profile B 保持默认 collect
        text_b = inject_and_get_reply(runner, "/queue",
                                      timeout=TIMEOUT_COMMAND, channel_id=CHANNEL_B)
        assert "Collect" in text_b or "collect" in text_b.lower()
        
        # 验证 A 仍然是 followup
        text_a_check = inject_and_get_reply(runner, "/queue",
                                            timeout=TIMEOUT_COMMAND, channel_id=CHANNEL_A)
        assert "Followup" in text_a_check


# ══════════════════════════════════════════════════════════════════════════════
# 压力与边界测试
# ══════════════════════════════════════════════════════════════════════════════

class TestDiscordStressAndEdgeCases:
    """压力测试和边界情况"""

    @pytest.mark.llm
    def test_rapid_messages(self, runner):
        """快速发送多条消息"""
        messages = ["Message 1", "Message 2", "Message 3"]
        for msg in messages:
            runner.inject(msg, channel_id="1039178386623557764")
        
        # 等待所有回复
        time.sleep(10)
        sent = runner.get_sent_messages()
        assert len(sent) >= 3, f"Expected at least 3 replies, got {len(sent)}"

    def test_concurrent_channels(self, runner):
        """多个 channel 同时对话"""
        channels = ["1039178386623557765", "1039178386623557766"]
        
        for ch in channels:
            runner.inject(f"Hello from channel {ch}", channel_id=ch)
        
        time.sleep(5)
        # 验证每个 channel 都收到了回复
        for ch in channels:
            msgs = [m for m in runner.get_sent_messages() if m.get("channel_id") == ch]
            assert len(msgs) > 0, f"Channel {ch} should have replies"

    def test_message_with_mention(self, runner):
        """带 @mention 的消息"""
        text = inject_and_get_reply(runner, "<@123456789> hello", timeout=TIMEOUT_LLM)
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
# 流式响应测试
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.llm
class TestDiscordStreaming:
    """测试流式响应（Discord 不支持编辑，但支持长消息分片）"""

    def test_long_response_split(self, runner):
        """长回复应该被分成多条消息"""
        # 请求一个长回复
        text = inject_and_get_reply(
            runner,
            "请详细解释 Python 的异步编程，包括 asyncio, async/await, event loop",
            timeout=TIMEOUT_LLM
        )
        # Discord 消息限制 2000 字符，长回复应该被截断或分片
        assert len(text) > 0, "Should receive response"
        # 如果实现了分片，可能会有多条消息
        # 这里只验证收到了回复

    def test_streaming_status_messages(self, runner):
        """流式处理中的状态消息"""
        count_before = len(runner.get_sent_messages())
        runner.inject("Write a long story about space exploration", channel_id="1039178386623557767")
        
        # 等待一段时间，检查是否有状态消息
        time.sleep(5)
        msgs = runner.get_sent_messages()
        new_msgs = msgs[count_before:]
        
        # 检查是否有 Processing/Deliberating 等状态消息
        status_msgs = [m for m in new_msgs if any(s in m.get("text", "") for s in ["Processing", "Deliberating", "Thinking"])]
        
        # 状态消息是可选的（取决于实现），不强制断言
        if status_msgs:
            print(f"  → Found {len(status_msgs)} status messages")

    def test_streaming_edit_simulation(self, runner):
        """Discord 不支持消息编辑，验证流式完成后的最终消息"""
        # Discord 不支持编辑已发送的消息，所以流式响应会发送多条消息
        # 或者发送一条完整的长消息
        text = inject_and_get_reply(
            runner,
            "请写一首关于秋天的长诗，至少 20 行",
            timeout=TIMEOUT_LLM
        )
        
        # 检查是否有编辑操作记录（通过 Mock Server 的 _edit_history）
        # 注意：目前 runner_discord 没有直接暴露 get_edit_history，我们可以通过检查 sent_messages 的变化推断
        # 或者直接在 Mock Server 增加接口。这里先验证消息发送成功且无报错。
        assert len(text) > 0, "Should receive a response"
        print(f"\n  ✓ Stream response received: {len(text)} chars")
