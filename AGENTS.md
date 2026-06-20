# AGENTS.md

## Project Identity

This is the **automated test framework** for the Rust `octos` CLI project, not the CLI itself. It is a Python 3.8+ repository.

## Package Management

- **Preferred tool**: `uv`. Use `uv sync` to install dependencies and `uv run` to execute scripts.
- `pyproject.toml` is the source of truth for dependencies. `requirements.txt` exists for backwards compatibility but is secondary.

## Critical External Dependency

Tests require the `octos` binary (a Rust project). `test_run.py` auto-detects it via this priority:
1. `OCTOS_BINARY` environment variable
2. `./target/release/octos`
3. `../target/release/octos`
4. `../../target/release/octos`
5. System `PATH`

If the binary is missing and the octos source tree is detected, `test_run.py` can trigger `cargo build --release -p octos-cli --features telegram,discord,api` automatically.

## Unified Test Entry Point

Always prefer `test_run.py` over raw `pytest` because it handles binary detection, mock server lifecycle, environment setup, and logging.

```bash
# Run everything
uv run python test_run.py all

# Bot tests (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)
uv run python test_run.py --test bot
uv run python test_run.py --test bot telegram
uv run python test_run.py --test bot discord

# CLI tests
uv run python test_run.py --test cli
uv run python test_run.py --test cli -s Init

# Serve tests
uv run python test_run.py --test serve
uv run python test_run.py --test serve 8.1
```

## Required Environment Variables

| Variable | Required For | Notes |
|----------|-------------|-------|
| `ANTHROPIC_API_KEY` | Bot tests | 二选一，兼容 NVIDIA/OpenAI 等任何 OpenAI 兼容 API |
| `OPENAI_API_KEY` | Bot tests | 二选一，NVIDIA key (`nvapi-...`) 或 OpenAI key 均可 |
| `TELEGRAM_BOT_TOKEN` | Telegram tests | Mock mode accepts any non-empty string |
| `DISCORD_BOT_TOKEN` | Discord tests | Optional; mock mode auto-fills a fake token |

## Architecture

- `bot_mock_test/`: Telegram (port 5000) and Discord (port 5001) mock servers using FastAPI. Uses `pytest`.
- `cli_test/`: CLI tests driven by `test_cases.json`.
- `serve/`: REST API and SSE tests for `octos serve`.

## Logs and Artifacts

All runtime output goes to `/tmp/octos_test/logs/`:
- `sessions/<timestamp>.log` — full session stdout/stderr
- `cli_test.log` — structured CLI test output
- `octos_*_bot_test_<ts>.log` — bot gateway output

CLI tests use isolated working directories under `/tmp/octos_test/cli/<Category>_<timestamp>/`.

## Lint / Typecheck / CI

There are no linting, formatting, type-checking, or CI configurations in this repository. Do not run `ruff`, `mypy`, `flake8`, or similar unless you are adding them.

## Documentation Language

READMEs and inline documentation are primarily in Chinese. This does not affect code conventions.

## AI 执行规则

### 输出完整性
执行命令时**禁止过滤输出**：
- 禁止使用 `grep`、`tail`、`head`、`|` 等管道过滤命令输出
- 禁止使用 `2>&1 | grep` 等组合过滤
- 必须让所有 stdout/stderr 原样输出，便于定位问题
- 如需查看特定内容，应在命令执行完成后用额外的只读命令读取已生成的文件/日志
