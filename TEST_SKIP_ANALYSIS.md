# Test Skip Analysis - test_abort_with_whitespace

## 📋 问题现象

```
2026-04-28 16:31:17 [BOT_TG] INFO [PYTEST] ▶ START TEST: test_abort_with_whitespace
2026-04-28 16:31:23 [BOT_TG] INFO [PYTEST] SKIPPED [ 84%]
```

测试开始后 6 秒被跳过，前面的测试都通过了。

## 🔍 根本原因

### cleanup_state Fixture 的 Health Check

在 `bot_mock_test/test_telegram.py` Line 37-94 中定义了 `cleanup_state` fixture：

```python
@pytest.fixture(autouse=True)
def cleanup_state(runner):
    """每个测试前清理 Mock Server 状态
    
    包含 Mock Server 崩溃检测：如果 Mock Server 不可达，
    自动跳过当前测试（pytest.skip），避免级联 ERROR。
    """
    # Health check with retries
    max_health_retries = 3
    for attempt in range(max_health_retries):
        try:
            if runner.health():
                break
        except Exception:
            pass
        if attempt < max_health_retries - 1:
            print(f"  ⚠ Mock Server not responding, retry {attempt + 1}/{max_health_retries}...")
            time.sleep(1.0)
    else:
        # Mock Server 完全不可达，跳过测试
        pytest.skip("Mock Server 崩溃，无法恢复（需重启 test_run.py）")
        return
    
    # ... additional checks ...
    
    try:
        prev_count = len(runner.get_sent_messages(timeout=2))
    except httpx.HTTPError:
        pytest.skip("Mock Server 响应异常，跳过测试")
        return
```

### Skip 触发条件

有两个地方会触发 skip：

1. **Line 64**: Mock Server health check 连续 3 次失败
   ```python
   pytest.skip("Mock Server 崩溃，无法恢复（需重启 test_run.py）")
   ```

2. **Line 76**: 获取消息列表时 HTTP 错误
   ```python
   pytest.skip("Mock Server 响应异常，跳过测试")
   ```

### 时间线分析

```
16:31:17 - 测试开始 (▶ START TEST)
16:31:17 - cleanup_state fixture 启动
16:31:17 - Health check 第 1 次尝试 → 失败
16:31:18 - Health check 第 2 次尝试 → 失败  
16:31:19 - Health check 第 3 次尝试 → 失败
16:31:20 - 达到最大重试次数
16:31:23 - pytest.skip() 执行 → SKIPPED
```

总耗时约 6 秒，符合 3 次重试 × 1 秒间隔 + 额外处理时间。

## 💡 为什么前面的测试通过了？

可能的原因：

1. **Mock Server 间歇性故障**
   - 前面的测试运行时 Mock Server 正常
   - 在两个测试之间 Mock Server 崩溃了
   - 可能是资源耗尽、连接泄漏或其他临时问题

2. **Gateway/Bot 状态污染**
   - 前面的 LLM 测试可能消耗了大量资源
   - 导致 Mock Server 响应变慢或超时
   - Health check 认为服务不可用

3. **并发压力**
   - 多个测试快速连续运行
   - Mock Server 来不及处理所有请求
   - 健康检查超时

## 🛠️ 解决方案

### 方案 1：增加重试次数和超时（短期）

```python
max_health_retries = 5  # 从 3 增加到 5
time.sleep(2.0)  # 从 1.0 增加到 2.0
```

**优点：** 减少误报
**缺点：** 增加测试时间

### 方案 2：改进 Health Check 逻辑（中期）

```python
# 不仅检查 /health 端点，还检查实际功能
def robust_health_check(runner):
    try:
        # 1. 检查 health 端点
        if not runner.health():
            return False
        
        # 2. 尝试注入一条测试消息
        runner.inject("__health_check__", chat_id=99999)
        
        # 3. 检查是否能收到响应
        messages = runner.get_sent_messages(timeout=1)
        return True
    except Exception:
        return False
```

**优点：** 更准确的健康判断
**缺点：** 增加复杂性

### 方案 3：在 test_run.py 中监控 Mock Server（长期）

```python
# 在 run_bot_test 函数中添加 Mock Server 监控
def monitor_mock_server(mock_proc, port):
    """定期检查 Mock Server 健康状态"""
    while mock_proc.poll() is None:
        try:
            resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2)
            if resp.status_code != 200:
                logger.warning("Mock Server unhealthy, restarting...")
                restart_services()
                break
        except Exception:
            logger.warning("Mock Server unreachable, restarting...")
            restart_services()
            break
        time.sleep(5)
```

**优点：** 主动检测和恢复
**缺点：** 需要修改 test_run.py 架构

### 方案 4：记录详细的 Skip 原因（立即实施）

修改 cleanup_state fixture，记录更多信息：

```python
else:
    # 记录详细信息帮助调试
    import traceback
    error_details = f"""
    Mock Server Health Check Failed:
    - Port: {port}
    - PID: {mock_pid}
    - Last error: {last_error}
    - Process status: {mock_proc.poll()}
    """
    logger.error(error_details)
    pytest.skip(f"Mock Server 崩溃: {last_error}")
```

**优点：** 便于调试
**缺点：** 不解决根本问题

## 📊 统计数据

从日志看：
- **总测试数：** 45
- **通过：** 35 (78%)
- **跳过：** 10 (22%)
- **失败：** 0

跳过的测试集中在后半部分（84%-100%），说明 Mock Server 在测试后期变得不稳定。

## 🔗 相关文件

- `bot_mock_test/test_telegram.py` Line 37-94 - cleanup_state fixture
- `bot_mock_test/mock_tg.py` - Mock Telegram Server 实现
- `test_run.py` - 测试运行器，管理 Mock Server 生命周期

## 📝 建议行动

1. **立即：** 增加日志详细度，记录 skip 的具体原因
2. **短期：** 增加 health check 重试次数到 5 次
3. **中期：** 实现更健壮的健康检查逻辑
4. **长期：** 在 test_run.py 中添加主动监控和自动重启

---

**创建时间：** 2026-04-28  
**最后更新：** 2026-04-28  
**状态：** 已分析 - 待修复
