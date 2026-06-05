# Octos 测试仓库迁移说明

本文档说明了如何将测试代码从 octos 主项目分离为独立仓库，以及如何使用新的测试框架。

## 主要变更

### 1. 统一测试入口

**之前**: `tests/run_tests.sh` (Bash 脚本)  
**现在**: `test_run.py` (Python 脚本)

优势：
- 跨平台兼容性更好（Windows/macOS/Linux）
- 更好的错误处理和日志管理
- 统一的 Python 生态系统集成

### 2. 二进制文件检测

测试脚本现在支持多种方式查找 octos 二进制文件：

```python
# 搜索顺序：
1. OCTOS_BINARY 环境变量
2. ./target/release/octos
3. ../target/release/octos
4. ../../target/release/octos
5. 系统 PATH 中的 octos 命令
```

### 3. 可选编译

如果找到 octos 源代码（Cargo.toml），可以自动编译；否则使用预编译二进制。

## 使用方法

### 方式一：设置环境变量（推荐）

```bash
export OCTOS_BINARY=/path/to/octos/target/release/octos
export ANTHROPIC_API_KEY=your_api_key
export TELEGRAM_BOT_TOKEN=your_bot_token

python test_run.py all
```

### 方式二：在 octos 项目目录中运行

```bash
# 假设测试仓库在 octos 项目旁边
cd /path/to/octos-test
python test_run.py all
```

### 方式三：手动编译

```bash
# 需要有 octos 源代码
cargo build --release -p octos-cli --features telegram,discord,api
python test_run.py all
```

## 测试命令

```bash
# 查看所有帮助
python test_run.py --help

# 运行所有测试
python test_run.py all

# 仅运行 Bot 测试
python test_run.py --test bot
python test_run.py --test bot telegram  # 仅 Telegram
python test_run.py --test bot discord   # 仅 Discord

# 仅运行 CLI 测试
python test_run.py --test cli
python test_run.py --test cli -v        # 详细输出

# 仅运行 Serve 测试
python test_run.py --test serve
python test_run.py --test serve list    # 列出可用测试
```

## 依赖安装

**推荐使用 uv（超快的 Python 包管理器）**

```bash
# 在项目根目录安装所有依赖
uv sync
```

**或使用传统 pip**

```bash
pip install -r requirements.txt
```

### 依赖说明

项目使用 `pyproject.toml` 管理依赖，包括：
- FastAPI + Uvicorn（Mock Server）
- httpx（HTTP 客户端）
- pytest + pytest-asyncio（测试框架）
- websockets（Discord WebSocket 支持）

## 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `OCTOS_BINARY` | 否 | octos 二进制文件路径（可选，自动检测） |
| `ANTHROPIC_API_KEY` | Bot 测试 | LLM API 密钥 |
| `TELEGRAM_BOT_TOKEN` | Telegram | Telegram Bot Token（Mock 模式下可为任意非空值） |
| `DISCORD_BOT_TOKEN` | 否 | Discord Mock 模式自动填充假 token |

## 日志位置

所有测试日志保存在 `/tmp/octos_test/logs/`：

```
/tmp/octos_test/logs/
├── build.log                    # 编译日志（如果执行了编译）
├── cli_test.log                 # CLI 测试独立日志
├── octos_bot_test_<ts>.log      # Bot 测试日志
└── sessions/                    # Session 日志
    └── <timestamp>.log
```

## 常见问题

### Q: 提示找不到 octos 二进制文件？

A: 设置 `OCTOS_BINARY` 环境变量：

```bash
export OCTOS_BINARY=/path/to/octos/target/release/octos
```

### Q: 如何只运行特定测试？

A: 使用相应的命令：

```bash
# 仅 Telegram 测试
python test_run.py --test bot telegram

# 仅 CLI Init 测试
python test_run.py --test cli -s Init

# 仅 Serve 8.1 测试
python test_run.py --test serve 8.1
```

### Q: 测试失败如何调试？

A: 查看日志文件：

```bash
# 查看最新 session 日志
ls -lt /tmp/octos_test/logs/sessions/ | head -1

# 查看 Bot 测试日志
ls -lt /tmp/octos_test/logs/octos_*_bot_test_*.log | head -1
```

## 与 octos 主项目的关系

本测试仓库是从 octos 主项目的 `tests/` 目录分离出来的，包含：

- `bot_mock_test/` - Bot Mock 测试
- `cli_test/` - CLI 测试
- `serve/` - Serve 测试
- `test_run.py` - 统一测试入口

可以独立于 octos 主项目运行，只需要提供 octos 二进制文件即可。

## 贡献

如需添加新测试或修复问题，请参考各子目录的 README.md：

- `bot_mock_test/README.md` - Bot 测试详细说明
- `serve/README.md` - Serve 测试详细说明
