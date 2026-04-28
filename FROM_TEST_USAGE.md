# --from-test 参数使用指南

## 📋 功能说明

`--from-test` 参数允许你从指定的测试用例开始运行，包括该测试及其之后的所有测试。这对于调试和重试非常有用。

## 🎯 使用场景

### 1. **调试特定测试**
当你发现某个测试失败，想从那个测试开始重新运行，而不需要从头开始：

```bash
test_run.py --test bot tg --from-test test_abort_with_whitespace
```

### 2. **跳过已通过的测试**
如果前 30 个测试都通过了，但第 31 个失败了，你可以直接从第 31 个开始：

```bash
test_run.py --test bot tg --from-test TestTelegramAbortCommands::test_abort_multilanguage
```

### 3. **快速验证修复**
修复了某个 bug 后，只想运行相关的测试及后续测试来验证：

```bash
test_run.py --test bot all --from-test test_soul_per_profile
```

## 💡 使用方法

### 基本语法

```bash
test_run.py --test bot <module> --from-test <test_name>
```

### 示例

#### 1. Telegram 模块，从指定测试开始

```bash
# 从 test_abort_with_whitespace 开始运行所有后续测试
test_run.py --test bot tg --from-test test_abort_with_whitespace

# 输出示例：
# 🎯 Running from test: test_abort_with_whitespace (index 37)
# 📋 Tests to run: 8
```

#### 2. Discord 模块，从指定测试开始

```bash
test_run.py --test bot dc --from-test test_message_send
```

#### 3. 所有 Bot 测试，从指定测试开始

```bash
# 对 Telegram 和 Discord 都应用相同的起始测试
test_run.py --test bot all --from-test test_new_default
```

#### 4. 使用完整测试名称

```bash
# 支持完整的测试路径
test_run.py --test bot tg --from-test "TestTelegramAbortCommands::test_abort_multilanguage[english_stop]"
```

## 🔍 工作原理

### 1. **查找测试索引**

系统会在测试列表中查找匹配的测试：

```python
for i, test in enumerate(all_tests):
    if test == from_test or from_test in test:
        from_idx = i
        break
```

**匹配规则：**
- 精确匹配：`test == from_test`
- 包含匹配：`from_test in test`（支持部分名称）

### 2. **过滤测试列表**

找到起始位置后，只运行从该位置开始的测试：

```python
if from_idx is not None:
    all_tests = all_tests[from_idx:]
```

### 3. **应用 Flaky Retry 逻辑**

从指定测试开始后，仍然会应用智能重试逻辑：
- 检测到 flaky 模式 → 重试所有从第一个失败开始的测试
- 非 flaky 模式 → 只重试第一个失败的测试

## ⚠️ 注意事项

### 1. **测试名称匹配**

如果提供的测试名称不唯一，会使用第一个匹配项：

```bash
# 如果有多个测试包含 "abort"，会使用第一个
test_run.py --test bot tg --from-test abort
```

**建议：** 使用更具体的名称或完整测试路径。

### 2. **跨模块限制**

`--from-test` 对每个模块独立应用：

```bash
# Telegram 和 Discord 会分别从各自的 test_new_default 开始
test_run.py --test bot all --from-test test_new_default
```

如果某个模块没有这个测试，会警告并运行所有测试：

```
⚠️  Test 'test_new_default' not found in discord, running all tests
```

### 3. **与具体测试参数的互斥**

`--from-test` 和具体测试名称不能同时使用：

```bash
# ❌ 错误：冲突的参数
test_run.py --test bot tg test_specific --from-test test_other

# ✅ 正确：只使用一个
test_run.py --test bot tg --from-test test_other
test_run.py --test bot tg test_specific
```

当前实现中，如果同时提供，会优先使用具体测试名称。

## 📊 日志输出

使用 `--from-test` 时，会看到详细的日志：

```
2026-04-28 16:45:00 [BOT_TG] INFO Total tests in telegram: 45
2026-04-28 16:45:00 [BOT_TG] INFO 🎯 Running from test: test_abort_with_whitespace (index 37)
2026-04-28 16:45:00 [BOT_TG] INFO 📋 Tests to run: 8
2026-04-28 16:45:00 [BOT_TG] INFO ============================================================
2026-04-28 16:45:00 [BOT_TG] INFO Running tg bot tests
2026-04-28 16:45:00 [BOT_TG] INFO ============================================================
```

## 🔧 技术实现

### 修改的函数

1. **`run_bot_test_with_per_test_retry(module, from_test=None)`**
   - 添加 `from_test` 可选参数
   - 在运行测试前过滤测试列表

2. **`run_all_bot_tests(from_test=None)`**
   - 添加 `from_test` 可选参数
   - 传递给每个模块的 `run_bot_test_with_per_test_retry`

3. **命令行参数解析**
   - 在 bot 命令处理器中解析 `--from-test`
   - 支持 `all` 和具体模块命令

### 代码位置

- 文件：`test_run.py`
- Line ~1100: `run_bot_test_with_per_test_retry()` 函数签名
- Line ~1127: 过滤测试列表的逻辑
- Line ~1275: `run_all_bot_tests()` 函数签名
- Line ~1609: `all` 命令的参数解析
- Line ~1630: 模块命令的参数解析

## 🎓 最佳实践

### 1. **使用完整测试名称**

```bash
# ✅ 推荐：使用完整名称
test_run.py --test bot tg --from-test "TestTelegramAbortCommands::test_abort_multilanguage[english_stop]"

# ⚠️ 可能不精确：使用部分名称
test_run.py --test bot tg --from-test abort
```

### 2. **先列出测试确认名称**

```bash
# 查看所有测试
test_run.py --test bot tg list

# 然后使用准确的名称
test_run.py --test bot tg --from-test test_abort_with_whitespace
```

### 3. **结合日志分析**

当测试失败时，查看日志确定应该从哪个测试开始：

```bash
# 查看失败信息
grep "FAILED" /tmp/octos_test/logs/01_runner_*.log

# 从第一个失败的测试开始重试
test_run.py --test bot tg --from-test test_first_failure
```

## 📝 更新历史

- **2026-04-28**: 初始实现
  - 添加 `--from-test` 参数支持
  - 支持 `all` 和模块特定命令
  - 集成到 flaky retry 逻辑中

---

**相关文档：**
- [TEST_SKIP_ANALYSIS.md](./TEST_SKIP_ANALYSIS.md) - 测试跳过分析
- [TEST_SOUL_PER_PROFILE_FAILURE.md](./TEST_SOUL_PER_PROFILE_FAILURE.md) - Soul 隔离测试失败分析
