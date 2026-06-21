#!/usr/bin/env python3
"""
Octos Test Runner - Unified test execution tool.

This script can be used in two modes:
1. Standalone test repository (this repo)
2. Tests directory within the octos project

Usage:
    test_run.py <command> [args...]

Commands:
    all                          Run all test suites (bot + cli + serve)
    --test bot [bot-args...]     Run bot mock tests
    --test cli [cli-args...]     Run CLI tests
    --test serve [serve-args...] Run serve tests
    --test email [email-args...] Run Email tests (real mailbox)
    --test tui [tui-args...]     Run octos-tui tests (sibling Rust crate)
    -h, --help                   Show this help message

Bot test arguments (after --test bot):
    all              Run all tests
    telegram, tg     Run Telegram tests only
    discord, dc      Run Discord tests only
    matrix, mx       Run Matrix tests only
    slack, sl        Run Slack tests only
    list             List available bot modules
    list <mod>       List test cases in a module
    <mod> [case]     Run module or specific test case
    --from-test <name>  Run from specified test onwards (with all subsequent tests)

CLI test arguments (after --test cli):
    -v, --verbose              Verbose output
    -o, --output-dir DIR       Output directory (default: test-results)
    -s, --scope SCOPE          Test scope
    list                       List available test categories
    list <category>            List test cases in a category

Serve test arguments (after --test serve):
    -v, --verbose              Verbose output
    list                       List available serve tests
    <test_id>                  Run specific test (e.g., 8.1, server_startup)

Examples:
    test_run.py all                     # run everything
    test_run.py --test bot              # all bot tests
    test_run.py --test bot telegram     # Telegram only
    test_run.py --test bot list         # list bot modules
    test_run.py --test bot tg list      # list Telegram test cases
    test_run.py --test bot tg           # run Telegram tests
    test_run.py --test bot tg test_new_default  # run specific test
    test_run.py --test bot tg --from-test test_abort_with_whitespace  # run from test onwards
    test_run.py --test cli              # CLI tests
    test_run.py --test cli -v           # CLI tests, verbose
    test_run.py --test cli list         # List test categories
    test_run.py --test serve            # Serve tests
    test_run.py --test serve -v         # Serve tests, verbose
    test_run.py --test serve list       # List serve tests

Environment:
    OCTOS_BINARY       Path to octos binary (optional, auto-detected if not set)
    ANTHROPIC_API_KEY  Required for bot LLM tests
    TELEGRAM_BOT_TOKEN Required for Telegram bot tests
    DISCORD_BOT_TOKEN  Optional (auto-set for mock mode)

Test directory: /tmp/octos_test
Logs: /tmp/octos_test/logs
"""

import argparse
import hashlib
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

# Constants
SCRIPT_DIR = Path(__file__).parent

# Load .env file if it exists
def load_env_file():
    """Load environment variables from .env file if present."""
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value

load_env_file()
# Support both standalone test repo and tests/ subdirectory in octos project
if (SCRIPT_DIR / "bot_mock_test").exists():
    # Standalone test repository
    TEST_REPO_ROOT = SCRIPT_DIR
else:
    # Tests directory within octos project
    TEST_REPO_ROOT = SCRIPT_DIR

TEST_DIR = Path("/tmp/octos_test")
LOG_DIR = TEST_DIR / "logs"
REPORT_DIR = SCRIPT_DIR / "test-results"  # 项目根下的统一报告目录
BINARY_PATH = Path(os.environ.get("OCTOS_BINARY", "")) if os.environ.get("OCTOS_BINARY") else None
BOT_TEST_DIR = TEST_REPO_ROOT / "bot_mock_test"
CLI_TEST_DIR = TEST_REPO_ROOT / "cli_test"
SERVE_TEST_DIR = TEST_REPO_ROOT / "serve"

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)

# Import CLI test module
from cli_test.test_cli import run_cli_tests as run_cli_tests_module

# Import Serve test module
try:
    from serve.test_serve import OctosServeTester
    SERVE_TEST_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
    SERVE_TEST_AVAILABLE = False
    # Don't log here, will be logged when actually used


class UnifiedTestReporter:
    """统一测试报告器 —— 收集所有模块结果并生成合并报告。"""

    def __init__(self, binary_path: str, test_date: str, output_dir: Path):
        self.modules: Dict[str, dict] = {}
        self.binary_path = str(binary_path)
        self.test_date = test_date
        self.output_dir = output_dir

    def add_module(
        self,
        name: str,
        results: List[dict],
        passed: int = 0,
        failed: int = 0,
        total: int = 0,
        skipped: int = 0,
        error: str = "",
    ):
        """添加一个模块的测试结果。"""
        pass_rate = round((passed * 100 / total), 1) if total > 0 else 0
        self.modules[name] = {
            "results": results,
            "passed": passed,
            "failed": failed,
            "total": total,
            "skipped": skipped,
            "passed_pct": pass_rate,
            "error": error,
        }

    def _get_overall_summary(self) -> dict:
        """计算总体统计。"""
        total_t = sum(m["total"] for m in self.modules.values())
        total_p = sum(m["passed"] for m in self.modules.values())
        total_f = sum(m["failed"] for m in self.modules.values())
        total_s = sum(m["skipped"] for m in self.modules.values())
        pct = round((total_p * 100 / total_t), 1) if total_t > 0 else 0
        return {
            "total": total_t,
            "passed": total_p,
            "failed": total_f,
            "skipped": total_s,
            "passed_pct": pct,
        }

    def generate_markdown(self) -> str:
        """生成完整 Markdown 报告。"""
        summary = self._get_overall_summary()
        lines = []
        lines.append("# Octos 统一测试报告\n")
        lines.append(f"**测试日期**: {self.test_date}\n")
        lines.append(f"**二进制**: {self.binary_path}\n")

        # 1. 总体结果
        lines.append("---\n")
        lines.append("## 1. 总体结果\n")
        lines.append("")
        lines.append("| 模块 | 总计 | 通过 | 失败 | 跳过 | 通过率 | 状态 |")
        lines.append("|------|------|------|------|------|--------|------|")
        for name, mod in sorted(self.modules.items()):
            status_icon = "✅" if mod["failed"] == 0 else "❌"
            lines.append(
                f"| {name} | {mod['total']} | {mod['passed']} | "
                f"{mod['failed']} | {mod['skipped']} | {mod['passed_pct']}% | "
                f"{status_icon}{' ' + mod['error'] if mod['error'] else ''} |"
            )
        overall_ok = summary["failed"] == 0
        overall_icon = "✅" if overall_ok else "❌"
        lines.append(
            f"| **总计** | **{summary['total']}** | **{summary['passed']}** | "
            f"**{summary['failed']}** | **{summary['skipped']}** | "
            f"**{summary['passed_pct']}%** | **{overall_icon}** |"
        )
        lines.append("")

        # 2. 各模块详细结果
        lines.append("---\n")
        lines.append("## 2. 各模块详细结果\n")

        module_display_names = {
            "cli": "2.1 CLI 测试",
            "serve": "2.2 Serve 测试",
            "stdio": "2.3 Stdio 测试",
            "bot": "2.4 Bot 测试",
        }

        for name, mod in sorted(self.modules.items()):
            display = module_display_names.get(name, name)
            lines.append(f"### {display}\n")
            lines.append(
                f"**总计**: {mod['total']} | **通过**: {mod['passed']} | "
                f"**失败**: {mod['failed']} | **跳过**: {mod['skipped']} | "
                f"**通过率**: {mod['passed_pct']}%\n"
            )

            if mod["results"]:
                # Determine columns based on first result
                sample = mod["results"][0]
                has_category = "category" in sample
                has_duration = sample.get("duration_sec", 0) > 0

                if name == "bot":
                    # Bot 结果按通道分组
                    channels = {}
                    for r in mod["results"]:
                        ch = r.get("channel", "unknown")
                        channels.setdefault(ch, []).append(r)
                    lines.append("| 通道 | 通过 | 失败 | 总计 | 状态 |")
                    lines.append("|------|------|------|------|------|")
                    for ch, res_list in sorted(channels.items()):
                        ch_pass = sum(1 for r in res_list if r["status"] == "PASS")
                        ch_fail = sum(1 for r in res_list if r["status"] == "FAIL")
                        ch_total = len(res_list)
                        ch_icon = "✅" if ch_fail == 0 else "❌"
                        lines.append(
                            f"| {ch} | {ch_pass} | {ch_fail} | "
                            f"{ch_total} | {ch_icon} |"
                        )
                    lines.append("")
                else:
                    # 普通模块展示表格
                    if has_category:
                        lines.append("| 编号 | 分类 | 名称 | 状态 | 耗时 |")
                        lines.append("|------|------|------|------|------|")
                        for r in mod["results"]:
                            dur = f"{r.get('duration_sec', 0):.2f}s" if r.get("duration_sec", 0) > 0 else "-"
                            lines.append(
                                f"| {r['test_id']} | {r.get('category', '-')} | "
                                f"{r['name']} | {r['status']} | {dur} |"
                            )
                    else:
                        lines.append("| 编号 | 名称 | 状态 | 耗时 |")
                        lines.append("|------|------|------|------|")
                        for r in mod["results"]:
                            dur = f"{r.get('duration_sec', 0):.2f}s" if r.get("duration_sec", 0) > 0 else "-"
                            lines.append(
                                f"| {r['test_id']} | {r['name']} | "
                                f"{r['status']} | {dur} |"
                            )
                    lines.append("")
            else:
                lines.append("*无测试用例数据*\n")

        # 3. 失败测试详情
        lines.append("---\n")
        lines.append("## 3. 失败测试详情\n")
        any_failures = any(mod["failed"] > 0 for mod in self.modules.values())
        if any_failures:
            for name, mod in sorted(self.modules.items()):
                if mod["error"]:
                    lines.append(f"### {name} 模块错误\n")
                    lines.append(f"```\n{mod['error']}\n```\n")
                    lines.append("")
                failed_results = [r for r in mod["results"] if r.get("status") == "FAIL"]
                if failed_results:
                    lines.append(f"### {name} 测试失败\n")
                    lines.append("")
                    for r in failed_results:
                        tid = r.get("test_id", "?")
                        rname = r.get("name", "?")
                        details = r.get("details", "")
                        lines.append(f"- **[{tid}] {rname}**: {details}")
                    lines.append("")
        else:
            lines.append("*无失败测试*\n")

        # 4. 覆盖矩阵
        lines.append("---\n")
        lines.append("## 4. 功能覆盖矩阵\n")
        lines.append("")
        lines.append("| 模块 | 测试数 | 通过率 | 评估 |")
        lines.append("|------|--------|--------|------|")
        for name, mod in sorted(self.modules.items()):
            if mod["passed_pct"] >= 95:
                rating = "🟢 良好"
            elif mod["passed_pct"] >= 80:
                rating = "🟡 一般"
            else:
                rating = "🔴 不足"
            lines.append(
                f"| {name} | {mod['total']} | {mod['passed_pct']}% | {rating} |"
            )
        lines.append("")

        # Footer
        lines.append("---\n")
        lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

        return "\n".join(lines)

    def generate_json(self) -> dict:
        """生成完整 JSON 数据结构。"""
        summary = self._get_overall_summary()
        modules_data = {}
        for name, mod in sorted(self.modules.items()):
            modules_data[name] = {
                "total": mod["total"],
                "passed": mod["passed"],
                "failed": mod["failed"],
                "skipped": mod["skipped"],
                "passed_pct": mod["passed_pct"],
                "error": mod["error"],
                "results": mod["results"],
            }
        return {
            "report_type": "octos_unified_test_report",
            "test_date": self.test_date,
            "binary_path": self.binary_path,
            "summary": summary,
            "modules": modules_data,
        }

    def save_report(self) -> Path:
        """保存 .md + .json 报告，返回 .md 路径。"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        md_path = self.output_dir / f"OCTOS_TEST_REPORT_{ts}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self.generate_markdown())
        log.info(f"Unified report saved: {md_path}")

        json_path = self.output_dir / f"OCTOS_TEST_REPORT_{ts}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.generate_json(), f, ensure_ascii=False, indent=2)
        log.info(f"Unified JSON report saved: {json_path}")

        return md_path

    def print_summary(self):
        """打印终端摘要。"""
        summary = self._get_overall_summary()
        print("")
        print("=" * 70)
        print("📊 UNIFIED TEST SUMMARY")
        print("=" * 70)
        print("")
        print(f"📅 Test Date: {self.test_date}")
        print("")
        print("🔹 Module Status:")
        for name, mod in sorted(self.modules.items()):
            icon = "✅" if mod["failed"] == 0 else "❌"
            err = f" ({mod['error'][:60]})" if mod['error'] else ""
            print(f"   • {name:<10}: {icon}  {mod['passed']}/{mod['total']} passed{err}")
        print("")
        overall_ok = summary["failed"] == 0
        overall_icon = "✅ ALL PASSED" if overall_ok else "❌ SOME FAILED"
        print(f"🎯 Overall: {overall_icon}")
        print(f"   Total: {summary['total']}, Passed: {summary['passed']}, "
              f"Failed: {summary['failed']}, Pass Rate: {summary['passed_pct']}%")
        print("")


class LoggerManager:
    """Manage multiple loggers for different modules."""
    
    def __init__(self):
        self.loggers: Dict[str, logging.Logger] = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Main test runner log
        self.main_logger = self._create_logger("main", LOG_DIR / f"01_runner_{timestamp}.log")
    
    def _create_logger(self, name: str, log_file: Optional[Path] = None) -> logging.Logger:
        """Create a logger with both stdout and file handlers."""
        logger = logging.getLogger(f"octos.{name}")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Format
        formatter = logging.Formatter(
            f"%(asctime)s [{name.upper()}] %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Stdout handler
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)
        
        # File handler
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def get_module_logger(self, module_name: str) -> logging.Logger:
        """Get or create a logger for a specific module. All logs go to main log file."""
        if module_name not in self.loggers:
            # Module logger: reuse main logger's file handler
            logger = logging.getLogger(f"octos.{module_name}")
            logger.setLevel(logging.INFO)
            logger.handlers.clear()
            
            # Format (same as main logger)
            formatter = logging.Formatter(
                f"%(asctime)s [{module_name.upper()}] %(levelname)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            
            # Stdout handler
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setFormatter(formatter)
            logger.addHandler(stdout_handler)
            
            # Reuse main logger's file handler
            for handler in self.main_logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    # Create a new FileHandler pointing to the same file
                    file_handler = logging.FileHandler(handler.baseFilename)
                    file_handler.setFormatter(formatter)
                    logger.addHandler(file_handler)
                    break
            
            self.loggers[module_name] = logger
        return self.loggers[module_name]
    
    def info(self, msg: str):
        self.main_logger.info(msg)
    
    def error(self, msg: str):
        self.main_logger.error(msg)
    
    def warning(self, msg: str):
        self.main_logger.warning(msg)


logger_mgr = LoggerManager()
log = logger_mgr.main_logger


def print_help():
    """Print help message."""
    print("""
  Octos Test Runner

  Usage:
    test_run.py <command> [args...]

  Commands:
    all                          Run all test suites (bot + cli + serve)
    --test bot [bot-args...]     Run bot mock tests
    --test cli [cli-args...]     Run CLI tests
    --test serve [serve-args...] Run serve tests
    --test email [email-args...] Run Email tests (real mailbox)
    --test tui [tui-args...]     Run octos-tui tests (sibling Rust crate)
    -h, --help                   Show this help message

  Bot test arguments (after --test bot):
    all              Run all tests
    telegram, tg     Run Telegram tests only
    discord, dc      Run Discord tests only
    matrix, mx       Run Matrix tests only
    slack, sl        Run Slack tests only
    list             List available bot modules
    list <mod>       List test cases in a module
    <mod> [case]     Run module or specific test case

  CLI test arguments (after --test cli):
    -v, --verbose              Verbose output
    -o, --output-dir DIR       Output directory (default: test-results)
    -s, --scope SCOPE          Test scope
    list                       List available test categories
    list <category>            List test cases in a category

  Serve test arguments (after --test serve):
    -v, --verbose              Verbose output
    list                       List available serve tests
    <test_id>                  Run specific test (e.g., 8.1, server_startup)

  Email test arguments (after --test email):
    <test_name>                Run specific test case (optional)
    -v, --verbose              Verbose output

  Examples:
    test_run.py all                     # run everything
    test_run.py --test bot              # all bot tests
    test_run.py --test bot telegram     # Telegram only
    test_run.py --test bot list         # list bot modules
    test_run.py --test bot tg list      # list Telegram test cases
    test_run.py --test bot tg           # run Telegram tests
    test_run.py --test bot tg test_new_default  # run specific test
    test_run.py --test bot matrix            # Matrix only
    test_run.py --test bot mx list           # list Matrix test cases
    test_run.py --test cli              # CLI tests
    test_run.py --test cli -v           # CLI tests, verbose
    test_run.py --test cli list         # List test categories
    test_run.py --test serve            # Serve tests
    test_run.py --test serve -v         # Serve tests, verbose
    test_run.py --test serve list       # List serve tests
    test_run.py --test email            # Email tests (real mailbox)
    test_run.py --test email -v         # Email tests, verbose
    test_run.py --test tui              # octos-tui tests (lib + integration + pty + smoke)
    test_run.py --test tui smoke        # octos-tui --mode mock PTY smoke only
    test_run.py --test tui build       # cargo build only (prepare binary)
    test_run.py --test tui smoke       # PTY smoke (octos-test black-box)

  Environment:
    OCTOS_BINARY       Path to octos binary (optional, auto-detected if not set)
    ANTHROPIC_API_KEY  Required for bot LLM tests
    TELEGRAM_BOT_TOKEN Required for Telegram bot tests
    DISCORD_BOT_TOKEN  Optional (auto-set for mock mode)
    OCTOS_TUI_DIR      Path to octos-tui checkout (default: ../octos-tui)
    OCTOS_TUI_BIN      Prebuilt octos-tui binary (skips cargo build)
    CARGO_TARGET_DIR   cargo target dir (default: /tmp/octos-tui-target)

  Test directory: /tmp/octos_test
  Logs: /tmp/octos_test/logs
""")


def check_environment(required_vars: List[str]) -> bool:
    """Check if required environment variables are set."""
    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        log.error("Missing required environment variables:")
        for var in missing:
            log.error(f"  - {var}")
        return False
    return True


def compute_file_hash(file_path: Path) -> str:
    """Compute MD5 hash of a file."""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_directory_hash(directory: Path) -> Dict[str, str]:
    """Compute hashes for all files in a directory."""
    hashes = {}
    if directory.exists():
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                rel_path = file_path.relative_to(directory)
                hashes[str(rel_path)] = compute_file_hash(file_path)
    return hashes


def save_directory_hashes(directory: Path, hash_file: Path):
    """Save directory hashes to a file."""
    hashes = compute_directory_hash(directory)
    with open(hash_file, 'w') as f:
        json.dump(hashes, f, indent=2)


def load_directory_hashes(hash_file: Path) -> Optional[Dict[str, str]]:
    """Load directory hashes from a file."""
    if hash_file.exists():
        with open(hash_file, 'r') as f:
            return json.load(f)
    return None


def has_directory_changed(directory: Path, hash_file: Path) -> bool:
    """Check if directory content has changed since last hash save."""
    current_hashes = compute_directory_hash(directory)
    saved_hashes = load_directory_hashes(hash_file)
    
    if saved_hashes is None:
        return True
    
    return current_hashes != saved_hashes


def find_octos_binary() -> Optional[Path]:
    """Find octos binary from environment or common locations.
    
    Search order:
    1. OCTOS_BINARY environment variable
    2. ./target/release/octos (if in octos project)
    3. ../target/release/octos (if in tests/ subdirectory)
    4. System PATH (octos command)
    """
    # Check environment variable first
    env_path = os.environ.get("OCTOS_BINARY")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        log.warning(f"OCTOS_BINARY set but file not found: {path}")
    
    # Check relative paths
    candidates = [
        Path("./target/release/octos"),
        Path("../target/release/octos"),
        Path("../../target/release/octos"),
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    
    # Check system PATH
    import shutil
    octos_in_path = shutil.which("octos")
    if octos_in_path:
        return Path(octos_in_path)
    
    return None


def build_octos(features: str = "telegram,discord,slack,whatsapp,email,feishu,twilio,wecom,line,matrix,wecom-bot,qq-bot,wechat,api") -> bool:
    """Build octos binary with required features.
    
    Args:
        features: Comma-separated list of features to enable (default: all channel features + api)
    
    Note:
        This function requires the octos source code to be available.
        If you have a pre-built binary, set OCTOS_BINARY environment variable instead.
    """
    global BINARY_PATH
    
    # Try to find existing binary first
    if BINARY_PATH is None:
        BINARY_PATH = find_octos_binary()
    
    if BINARY_PATH and BINARY_PATH.exists():
        log.info(f"Using existing octos binary: {BINARY_PATH}")
        return True
    
    # No binary found — instruct user to build manually
    log.error("No octos binary found.")
    log.error("")
    log.error("Please build octos manually first:")
    log.error("")
    log.error("  cd <octos-project-root>")
    log.error(f"  cargo build --release -p octos-cli --features {features}")
    log.error("")
    log.error("Or set OCTOS_BINARY environment variable to point to a pre-built binary:")
    log.error("  export OCTOS_BINARY=/path/to/octos")
    log.error("")
    return False


def _cleanup_stale_processes():
    """清理残留的 octos 进程，释放 episode store 锁和端口。"""
    for name in ["octos serve", "octos chat", "octos gateway"]:
        try:
            subprocess.run(["pkill", "-f", name], capture_output=True, timeout=5)
        except Exception:
            pass


def _ensure_nvidia_config():
    """检测 NVIDIA key 并配置 octos 使用 NVIDIA OpenAI 兼容 API。"""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key.startswith("nvapi-"):
        return

    config_path = Path.home() / ".config" / "octos" / "config.json"
    if not config_path.exists():
        return

    try:
        config = json.loads(config_path.read_text())
        # 已有 base_url 则跳过（用户自定义）
        if config.get("base_url"):
            return

        nvidia_base_url = "https://integrate.api.nvidia.com/v1"
        nvidia_model = "deepseek-ai/deepseek-v4-pro"
        config["base_url"] = nvidia_base_url
        config["model"] = nvidia_model
        config_path.write_text(json.dumps(config, indent=2))
        log.info(f"🔄 NVIDIA API key detected → updated octos config: base_url={nvidia_base_url}, model={nvidia_model}")
    except Exception as e:
        log.warning(f"⚠️  Failed to update octos config for NVIDIA: {e}")


def prepare_test_environment():
    """Prepare test environment and copy files if needed."""
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ── 清理残留的 octos 进程 ──
    _cleanup_stale_processes()

    # ── 自动配置 NVIDIA OpenAI 兼容 API ──
    # 当 OPENAI_API_KEY 是 NVIDIA key 时，在 octos config 中添加 base_url
    _ensure_nvidia_config()
    
    # Check if bot test files have changed
    bot_hash_file = TEST_DIR / ".bot_test_hashes.json"
    if has_directory_changed(BOT_TEST_DIR, bot_hash_file):
        log.info("Bot test files changed, updating...")
        # In a real scenario, you might copy files here
        # For now, we just track the hashes
        save_directory_hashes(BOT_TEST_DIR, bot_hash_file)
    else:
        log.info("Bot test files unchanged, skipping copy")
    
    # Check if CLI test files have changed
    cli_hash_file = TEST_DIR / ".cli_test_hashes.json"
    if has_directory_changed(CLI_TEST_DIR, cli_hash_file):
        log.info("CLI test files changed, updating...")
        save_directory_hashes(CLI_TEST_DIR, cli_hash_file)
    else:
        log.info("CLI test files unchanged, skipping copy")


def list_bot_modules():
    """List available bot test modules."""
    print("")
    print("Available bot test modules:")
    print("  telegram (tg)      - Telegram bot tests")
    print("  discord (dc)       - Discord bot tests")
    print("  matrix (mx)        - Matrix bot tests")
    print("  slack (sl)         - Slack bot tests")
    print("  feishu (fs)        - Feishu bot tests")
    print("  wechat (wx)        - WeChat bot tests")
    print("  whatsapp (wa)      - WhatsApp bot tests")
    print("  wecom-bot (wcb)    - WeCom Bot tests")
    print("  wecom (we)         - WeCom Channel tests")
    print("  qq-bot (qq)        - QQ Bot tests")
    print("  twilio (tw)        - Twilio tests")
    print("")


def list_bot_cases(module: str):
    """List test cases in a bot module."""
    test_files = {
        "telegram": BOT_TEST_DIR / "test_telegram.py",
        "tg": BOT_TEST_DIR / "test_telegram.py",
        "discord": BOT_TEST_DIR / "test_discord.py",
        "dc": BOT_TEST_DIR / "test_discord.py",
        "matrix": BOT_TEST_DIR / "test_matrix.py",
        "mx": BOT_TEST_DIR / "test_matrix.py",
        "slack": BOT_TEST_DIR / "test_slack.py",
        "sl": BOT_TEST_DIR / "test_slack.py",
        "feishu": BOT_TEST_DIR / "test_feishu.py",
        "fs": BOT_TEST_DIR / "test_feishu.py",
        "wechat": BOT_TEST_DIR / "test_wechat.py",
        "wx": BOT_TEST_DIR / "test_wechat.py",
        "email": BOT_TEST_DIR / "test_email.py",
        "whatsapp": BOT_TEST_DIR / "test_whatsapp.py",
        "wa": BOT_TEST_DIR / "test_whatsapp.py",
        "wecom-bot": BOT_TEST_DIR / "test_wecom_bot.py",
        "wecom_bot": BOT_TEST_DIR / "test_wecom_bot.py",
        "wcb": BOT_TEST_DIR / "test_wecom_bot.py",
        "wecom": BOT_TEST_DIR / "test_wecom.py",
        "we": BOT_TEST_DIR / "test_wecom.py",
    }
    
    test_file = test_files.get(module)
    if not test_file or not test_file.exists():
        print(f"Test file not found for module: {module}")
        return
    
    # Use pytest to collect tests
    venv_python = BOT_TEST_DIR / ".venv" / "bin" / "python"
    if not venv_python.exists():
        print("Python venv not found. Run a test first to create it.")
        return
    
    result = subprocess.run(
        [str(venv_python), "-m", "pytest", str(test_file), "--collect-only", "-q"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(BOT_TEST_DIR)},
    )
    
    print(f"\nTest cases in {module}:")
    count = 0
    current_class = None
    for line in result.stdout.splitlines():
        if "::" in line and "test_" in line:
            # Parse class and test name from full path
            parts = line.split("::")
            if len(parts) >= 2:
                cls = parts[-2]
                func = parts[-1]
                
                # Print class header when it changes
                if cls != current_class:
                    current_class = cls
                    print(f"\n  {cls}")
                
                count += 1
                print(f"    {count}. {func}")
    
    if count == 0:
        print("No test cases found")
    else:
        print(f"\nTotal: {count} test(s)\n")


def get_test_order(module: str) -> List[str]:
    """Get ordered list of test names for a module.

    Returns tests in the order pytest would execute them.
    """
    test_files = {
        "telegram": BOT_TEST_DIR / "test_telegram.py",
        "tg": BOT_TEST_DIR / "test_telegram.py",
        "discord": BOT_TEST_DIR / "test_discord.py",
        "dc": BOT_TEST_DIR / "test_discord.py",
        "matrix": BOT_TEST_DIR / "test_matrix.py",
        "mx": BOT_TEST_DIR / "test_matrix.py",
        "slack": BOT_TEST_DIR / "test_slack.py",
        "sl": BOT_TEST_DIR / "test_slack.py",
        "feishu": BOT_TEST_DIR / "test_feishu.py",
        "fs": BOT_TEST_DIR / "test_feishu.py",
        "wechat": BOT_TEST_DIR / "test_wechat.py",
        "wx": BOT_TEST_DIR / "test_wechat.py",
        "wecom-bot": BOT_TEST_DIR / "test_wecom_bot.py",
        "wecom_bot": BOT_TEST_DIR / "test_wecom_bot.py",
        "wcb": BOT_TEST_DIR / "test_wecom_bot.py",
        "wecom": BOT_TEST_DIR / "test_wecom.py",
        "we": BOT_TEST_DIR / "test_wecom.py",
        "qq-bot": BOT_TEST_DIR / "test_qq.py",
        "qq_bot": BOT_TEST_DIR / "test_qq.py",
        "qq": BOT_TEST_DIR / "test_qq.py",
        "twilio": BOT_TEST_DIR / "test_twilio.py",
        "tw": BOT_TEST_DIR / "test_twilio.py",
    }

    test_file = test_files.get(module)
    if not test_file or not test_file.exists():
        return []

    venv_python = BOT_TEST_DIR / ".venv" / "bin" / "python"
    if not venv_python.exists():
        return []

    result = subprocess.run(
        [str(venv_python), "-m", "pytest", str(test_file), "--collect-only", "-q"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(BOT_TEST_DIR)},
    )

    tests = []
    for line in result.stdout.splitlines():
        if "::" in line and "test_" in line:
            parts = line.split("::")
            if len(parts) >= 2:
                test_name = parts[-1]
                tests.append(test_name)
    return tests


def get_tests_to_rerun(failed_tests: List[str], all_tests: List[str]) -> List[str]:
    """Get tests to re-run from the first failure onwards.

    Args:
        failed_tests: List of failed test names
        all_tests: List of all tests in execution order

    Returns:
        Tests from the first failed test onwards (in original order)
    """
    if not failed_tests or not all_tests:
        return []

    failed_set = set(failed_tests)

    # Find the first failed test's index in the full order
    for i, test in enumerate(all_tests):
        if test in failed_set:
            return all_tests[i:]

    return []


def detect_flaky_failure(failed_tests: List[str], passed_tests: List[str], all_tests: List[str]) -> bool:
    """Detect if failure pattern suggests flaky test.

    Returns True if:
    - There was at least one failure
    - At least one test PASSED after the first failure
    This suggests the failure was due to state corruption that later cleared.

    Args:
        failed_tests: Tests that failed in this run
        passed_tests: Tests that passed in this run
        all_tests: All tests in execution order
    """
    if not failed_tests or not passed_tests:
        return False

    # Find first failed test's position
    first_failed_idx = None
    for i, test in enumerate(all_tests):
        if test in set(failed_tests):
            first_failed_idx = i
            break

    if first_failed_idx is None:
        return False

    # Check if any passed tests come after the first failure
    for i, test in enumerate(all_tests):
        if i > first_failed_idx and test in set(passed_tests):
            return True

    return False


def run_email_test(test_case: Optional[str] = None) -> Tuple[bool, List[str], List[str]]:
    """Run Email bot tests (real mailbox mode, no mock server).

    Email tests connect to real IMAP/SMTP servers, so no mock server is needed.
    Requires EMAIL_USERNAME, EMAIL_PASSWORD, and EMAIL_REAL_TEST in .env.

    Returns:
        Tuple of (passed, failed_test_names, passed_test_names)
    """
    module = "email"
    module_logger = logger_mgr.get_module_logger("email")

    module_logger.info("=" * 60)
    module_logger.info("📧 Running Email bot tests")
    module_logger.info("=" * 60)

    # Check environment
    required_vars = ["OPENAI_API_KEY"]
    if not check_environment(required_vars):
        return False, [], []

    # Clean up any lingering octos processes
    module_logger.info("Cleaning up lingering processes...")
    try:
        subprocess.run(["pkill", "-f", "octos gateway"], capture_output=True, timeout=5)
    except Exception:
        pass
    time.sleep(1)

    # Setup venv if needed
    venv_python = BOT_TEST_DIR / ".venv" / "bin" / "python"
    if not venv_python.exists():
        module_logger.info("Creating Python venv...")
        subprocess.run(["uv", "venv", str(BOT_TEST_DIR / ".venv")], check=True)
        subprocess.run([
            "uv", "pip", "install",
            "fastapi", "uvicorn", "httpx", "pytest", "pytest-asyncio", "pytest-timeout", "websockets",
            "--python", str(venv_python),
        ], check=True)

    # Determine test file
    port = 5080
    test_path = BOT_TEST_DIR / "test_email.py"
    if not test_path.exists():
        module_logger.error(f"Test file not found: {test_path}")
        return False, [], []

    # Prepare config
    config_dir = TEST_DIR / ".octos"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "test_email_config.json"

    # ── 检查 .env 配置 ─────────────────────────────────────────────
    env_file = SCRIPT_DIR / ".env"
    email_header_written = False

    def _ensure_env_var(key: str, default: str, comment: str):
        nonlocal email_header_written
        if key in os.environ:
            return True
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith(f"# {key}=") or stripped.startswith(f"{key}="):
                        return False
        try:
            with open(env_file, "a") as f:
                if not email_header_written:
                    f.write("""
# ════════════════════════════════════════════════════════════════════════════
# Email 测试配置（使用真实邮箱）
# ════════════════════════════════════════════════════════════════════════════
#
# ── QQ 邮箱 ──────────────────────────────────────────────────────────────
#   登录 mail.qq.com → 设置 → 账户
#   → 开启 IMAP/SMTP 服务 → 生成授权码（16位字母，不是QQ密码）
#   IMAP: imap.qq.com:993 (SSL)
#   SMTP: smtp.qq.com:465 (SSL)
#
# ── 163 邮箱 ─────────────────────────────────────────────────────────────
#   登录 mail.163.com → 设置 → POP3/SMTP/IMAP
#   → 开启 IMAP/SMTP → 设置授权码
#   IMAP: imap.163.com:993 (SSL)
#   SMTP: smtp.163.com:465 (SSL)
#
""")
                    email_header_written = True
                if comment:
                    f.write(f"# {comment}\n")
                f.write(f"# {key}={default}\n")
            module_logger.info(f"  → 已添加 {key} 到 .env")
        except Exception:
            pass
        return False

    has_user = _ensure_env_var("EMAIL_USERNAME", "your_bot@qq.com",
                                "Bot 邮箱地址（必须，将 # 去掉并替换为你的邮箱）")
    has_pass = _ensure_env_var("EMAIL_PASSWORD", "your_authorization_code",
                                "邮箱授权码（必须，将 # 去掉并替换为你的授权码）")
    has_real = _ensure_env_var("EMAIL_REAL_TEST", "true",
                                "启用真实邮箱模式（必须，去掉 # 启用）")
    _ensure_env_var("EMAIL_IMAP_HOST", "imap.qq.com",
                     "IMAP 服务器（可选，QQ邮箱无需修改；163邮箱改为 imap.163.com）")
    _ensure_env_var("EMAIL_IMAP_PORT", "993", "")
    _ensure_env_var("EMAIL_SMTP_HOST", "smtp.qq.com",
                     "SMTP 服务器（可选，QQ邮箱无需修改；163邮箱改为 smtp.163.com）")
    _ensure_env_var("EMAIL_SMTP_PORT", "465", "")

    module_logger.info("")
    module_logger.info("=" * 60)
    module_logger.info("📧 Email 测试使用真实邮箱，不需要 Mock 服务器")
    module_logger.info("=" * 60)
    module_logger.info("")

    all_set = has_user and has_pass and has_real

    if not all_set:
        module_logger.info("请在 .env 中配置以下环境变量后重试：")
        module_logger.info("")
        if not has_user:
            module_logger.info("  1. 设置 EMAIL_USERNAME=your_bot@qq.com（或 your_bot@163.com）")
        if not has_pass:
            module_logger.info("  2. 设置 EMAIL_PASSWORD=your_authorization_code（授权码！不是QQ密码）")
        if not has_real:
            module_logger.info("  3. 设置 EMAIL_REAL_TEST=true")
        module_logger.info("")
        module_logger.info("  ── QQ 邮箱 ──────────────────────────────────────")
        module_logger.info("    1. 登录 mail.qq.com → 设置 → 账户")
        module_logger.info("    2. 开启 IMAP/SMTP 服务 → 生成授权码（16位字母）")
        module_logger.info("    3. IMAP: imap.qq.com:993 / SMTP: smtp.qq.com:465")
        module_logger.info("")
        return False, [], []
    else:
        module_logger.info("  ✓ EMAIL_USERNAME: " + os.environ.get("EMAIL_USERNAME", ""))
        module_logger.info("  ✓ EMAIL_REAL_TEST=true")
        module_logger.info("  ✓ IMAP: " + os.environ.get("EMAIL_IMAP_HOST", "imap.qq.com") + ":" + os.environ.get("EMAIL_IMAP_PORT", "993"))
        module_logger.info("  ✓ SMTP: " + os.environ.get("EMAIL_SMTP_HOST", "smtp.qq.com") + ":" + os.environ.get("EMAIL_SMTP_PORT", "465"))
        module_logger.info("")
        module_logger.info("⏳ 正在启动 octos gateway 并连接真实邮箱...")
        module_logger.info("")

        # 构建真实邮箱配置
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        imap_host = os.environ.get("EMAIL_IMAP_HOST", "imap.qq.com")
        imap_port = int(os.environ.get("EMAIL_IMAP_PORT", "993"))
        smtp_host = os.environ.get("EMAIL_SMTP_HOST", "smtp.qq.com")
        smtp_port = int(os.environ.get("EMAIL_SMTP_PORT", "465"))
        from_addr = os.environ.get("EMAIL_FROM_ADDRESS", os.environ.get("EMAIL_USERNAME", ""))
        extra_env = {}
        config = {
            "id": "test_email_bot",
            "name": "Test Email Bot",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
            "config": {
                "version": 1,
                "llm": {
                    "primary": {
                        "family_id": "openai",
                        "model_id": "deepseek-ai/deepseek-v4-pro",
                        "route": {
                            "api_key_env": "OPENAI_API_KEY",
                            "base_url": "https://integrate.api.nvidia.com/v1"
                        }
                    },
                    "fallbacks": []
                },
                "channels": [{
                    "type": "email",
                    "imap_host": imap_host,
                    "imap_port": imap_port,
                    "smtp_host": smtp_host,
                    "smtp_port": smtp_port,
                    "username_env": "EMAIL_USERNAME",
                    "password_env": "EMAIL_PASSWORD",
                    "from_address": from_addr,
                    "poll_interval_secs": 15,
                    "allowed_senders": "",
                    "max_body_chars": 50000,
                }],
                "gateway": {
                    "max_history": 5,
                    "max_concurrent_sessions": 10,
                    "system_prompt": "IMPORTANT: When calling the message tool, NEVER specify the channel or chat_id parameters. Leave them empty/null so the system uses the current conversation context. Do not pass strings like 'console', 'current', 'telegram', 'discord', 'slack' or any other value for channel."
                }
            }
        }

    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)

    # Clean up previous test artifacts
    module_logger.info("Cleaning up previous test artifacts...")

    # Kill any existing processes on the port
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            capture_output=True,
            text=True,
        )
        pids = result.stdout.strip().splitlines()
        for pid in pids:
            if pid:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                    module_logger.info(f"Killed process {pid} on port {port}")
                except ProcessLookupError:
                    pass
        if pids:
            time.sleep(1)
    except Exception:
        pass

    # Remove database lock files
    db_files = list(TEST_DIR.glob("*.redb")) + list(TEST_DIR.glob("*.redb.lock"))
    for db_file in db_files:
        try:
            db_file.unlink()
            module_logger.info(f"Removed database file: {db_file}")
        except FileNotFoundError:
            pass

    # Clear Python cache
    import shutil
    for pattern in ["__pycache__", "*.pyc", ".pytest_cache"]:
        for path in BOT_TEST_DIR.glob(f"**/{pattern}"):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.is_file():
                path.unlink(missing_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    bot_log = LOG_DIR / f"02_gateway_email_{timestamp}.log"

    # No mock server for email
    module_logger.info("📧 跳过 Mock 服务器，直接连接真实 IMAP/SMTP")

    # Start Octos Gateway
    if not BINARY_PATH.exists():
        module_logger.error(f"Octos binary not found: {BINARY_PATH}")
        return False, [], []

    bot_env = {**os.environ, **extra_env}

    # Open log file for bot output
    bot_log_file = open(bot_log, 'w')

    bot_proc = subprocess.Popen(
        [str(BINARY_PATH), "gateway", "--profile", str(config_file), "--data-dir", str(TEST_DIR)],
        env=bot_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    bot_pid = bot_proc.pid
    module_logger.info(f"Bot PID: {bot_pid}")

    # Start tee thread
    import threading
    import sys as _sys

    _gateway_ready = threading.Event()

    def tee_output(proc, log_file):
        try:
            while True:
                if proc.poll() is not None:
                    remaining = proc.stdout.read()
                    if remaining:
                        text = remaining.decode('utf-8', errors='ignore')
                        try:
                            log_file.write(text)
                            log_file.flush()
                        except (ValueError, IOError):
                            pass
                        _sys.stdout.write(text)
                        _sys.stdout.flush()
                    break
                line = proc.stdout.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                text = line.decode('utf-8', errors='ignore')
                # Check for gateway ready signal
                if any(kw in text.lower() for kw in ["gateway started", "listening", "[gateway] ready"]):
                    _gateway_ready.set()
                try:
                    log_file.write(text)
                    log_file.flush()
                except (ValueError, IOError):
                    pass
                _sys.stdout.write(text)
                _sys.stdout.flush()
        except Exception as e:
            if not isinstance(e, (ValueError, IOError)):
                module_logger.error(f"Tee thread error: {e}")

    tee_thread = threading.Thread(target=tee_output, args=(bot_proc, bot_log_file), daemon=True)
    tee_thread.start()

    # Wait for gateway to start (via tee thread signal)
    module_logger.info("Waiting for gateway to start...")
    ready = False
    max_wait = 60  # Email might be slower
    start = time.time()

    try:
        while time.time() - start < max_wait:
            if bot_proc.poll() is not None:
                module_logger.error(f"Bot process exited prematurely (exit code: {bot_proc.returncode})")
                break

            if _gateway_ready.is_set():
                ready = True
                break

            time.sleep(0.2)
    except Exception as e:
        module_logger.error(f"Error waiting for gateway: {e}")

    if not ready:
        module_logger.error("Email gateway failed to start within timeout")
        bot_proc.terminate()
        try:
            bot_log_file.close()
        except Exception:
            pass
        return False, [], []

    module_logger.info("Email gateway is ready!")

    # Run tests
    module_logger.info(f"Running email tests...")
    if test_case:
        module_logger.info(f"  Test case filter: {test_case}")

    extra_env = {}

    # Build pytest command
    pytest_args = [
        str(venv_python), "-m", "pytest",
        str(test_path),
        "-v",
        "--timeout=300",
        "-x",  # Stop on first failure
    ]

    if test_case:
        pytest_args.extend(["-k", test_case])

    # Add annotation for slow marker
    pytest_env = {
        **os.environ,
        **extra_env,
        "PYTHONPATH": str(BOT_TEST_DIR),
    }

    result = subprocess.run(pytest_args, env=pytest_env)

    passed = result.returncode == 0

    # Collect test results
    test_names = [f"email/{t}" for t in ["test_email"]]
    failed_tests = [] if passed else test_names
    passed_tests = test_names if passed else []

    # Cleanup
    module_logger.info("Cleaning up email gateway...")
    try:
        bot_log_file.close()
    except Exception:
        pass
    bot_proc.terminate()
    try:
        bot_proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        bot_proc.kill()

    # Wait for tee thread
    tee_thread.join(timeout=5)

    module_logger.info(f"Email test {'PASSED' if passed else 'FAILED'}")

    return passed, failed_tests, passed_tests


def run_bot_test(module: str, test_case: Optional[str] = None) -> Tuple[bool, List[str], List[str]]:
    """Run bot tests for a specific module.

    Returns:
        Tuple of (passed, failed_test_names, passed_test_names)
    """
    module_logger = logger_mgr.get_module_logger(f"bot_{module}")
    
    module_logger.info("=" * 60)
    module_logger.info(f"Running {module} bot tests")
    module_logger.info("=" * 60)
    
    # Check environment
    required_vars = ["OPENAI_API_KEY"]
    if module in ["telegram", "tg"]:
        required_vars.append("TELEGRAM_BOT_TOKEN")
    
    if not check_environment(required_vars):
        return False, [], []
    
    # Clean up any lingering octos processes from previous runs
    module_logger.info("Cleaning up lingering processes...")
    try:
        # Kill any running octos gateway processes
        result = subprocess.run(
            ["pkill", "-f", "octos gateway"],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            module_logger.info("Killed lingering octos gateway processes")
        else:
            module_logger.debug("No lingering octos gateway processes found")
    except FileNotFoundError:
        module_logger.warning("pkill not found, skipping process cleanup")
    except subprocess.TimeoutExpired:
        module_logger.warning("Process cleanup timed out")
    except Exception as e:
        module_logger.warning(f"Failed to clean up processes: {e}")
    
    # Wait a moment for processes to fully terminate
    time.sleep(1)
    
    # Setup venv if needed
    venv_python = BOT_TEST_DIR / ".venv" / "bin" / "python"
    if not venv_python.exists():
        module_logger.info("Creating Python venv...")
        subprocess.run(["uv", "venv", str(BOT_TEST_DIR / ".venv")], check=True)
        subprocess.run([
            "uv", "pip", "install",
            "fastapi", "uvicorn", "httpx", "pytest", "pytest-asyncio", "pytest-timeout", "websockets",
            "--python", str(venv_python),
        ], check=True)

    # Determine test file and module info
    # module_info dict - email has been moved to run_email_test()
    module_info = {
        "telegram": {"port": 5000, "test_file": "test_telegram.py", "mock_module": "mock_tg", "mock_class": "MockTelegramServer"},
        "tg": {"port": 5000, "test_file": "test_telegram.py", "mock_module": "mock_tg", "mock_class": "MockTelegramServer"},
        "discord": {"port": 5001, "test_file": "test_discord.py", "mock_module": "mock_discord", "mock_class": "MockDiscordServer"},
        "dc": {"port": 5001, "test_file": "test_discord.py", "mock_module": "mock_discord", "mock_class": "MockDiscordServer"},
        "matrix": {"port": 5002, "test_file": "test_matrix.py", "mock_module": "mock_matrix", "mock_class": "MockMatrixServer"},
        "mx": {"port": 5002, "test_file": "test_matrix.py", "mock_module": "mock_matrix", "mock_class": "MockMatrixServer"},
        "slack": {"port": 5003, "test_file": "test_slack.py", "mock_module": "mock_slack", "mock_class": "MockSlackServer"},
        "sl": {"port": 5003, "test_file": "test_slack.py", "mock_module": "mock_slack", "mock_class": "MockSlackServer"},
        "feishu": {"port": 5004, "test_file": "test_feishu.py", "mock_module": "mock_feishu", "mock_class": "MockFeishuServer"},
        "fs": {"port": 5004, "test_file": "test_feishu.py", "mock_module": "mock_feishu", "mock_class": "MockFeishuServer"},
        "wechat": {"port": 5005, "test_file": "test_wechat.py", "mock_module": "mock_wechat", "mock_class": "MockWeChatServer"},
        "wx": {"port": 5005, "test_file": "test_wechat.py", "mock_module": "mock_wechat", "mock_class": "MockWeChatServer"},
        "whatsapp": {"port": 5006, "test_file": "test_whatsapp.py", "mock_module": "mock_whatsapp", "mock_class": "MockWhatsAppServer"},
        "wa": {"port": 5006, "test_file": "test_whatsapp.py", "mock_module": "mock_whatsapp", "mock_class": "MockWhatsAppServer"},
        "line": {"port": 5007, "test_file": "test_line.py", "mock_module": "mock_line", "mock_class": "MockLineServer"},
        "ln": {"port": 5007, "test_file": "test_line.py", "mock_module": "mock_line", "mock_class": "MockLineServer"},
        "wecom-bot": {"port": 5008, "test_file": "test_wecom_bot.py", "mock_module": "mock_wecom_bot", "mock_class": "MockWeComBotServer"},
        "wecom_bot": {"port": 5008, "test_file": "test_wecom_bot.py", "mock_module": "mock_wecom_bot", "mock_class": "MockWeComBotServer"},
        "wcb": {"port": 5008, "test_file": "test_wecom_bot.py", "mock_module": "mock_wecom_bot", "mock_class": "MockWeComBotServer"},
        "wecom": {"port": 5009, "test_file": "test_wecom.py", "mock_module": "mock_wecom", "mock_class": "MockWeComServer"},
        "we": {"port": 5009, "test_file": "test_wecom.py", "mock_module": "mock_wecom", "mock_class": "MockWeComServer"},
        "qq-bot": {"port": 5010, "test_file": "test_qq.py", "mock_module": "mock_qq", "mock_class": "MockQqServer"},
        "qq_bot": {"port": 5010, "test_file": "test_qq.py", "mock_module": "mock_qq", "mock_class": "MockQqServer"},
        "qq": {"port": 5010, "test_file": "test_qq.py", "mock_module": "mock_qq", "mock_class": "MockQqServer"},
        "twilio": {"port": 5011, "test_file": "test_twilio.py", "mock_module": "mock_twilio", "mock_class": "MockTwilioServer"},
        "tw": {"port": 5011, "test_file": "test_twilio.py", "mock_module": "mock_twilio", "mock_class": "MockTwilioServer"},
        "cross": {"port": 5000, "test_file": "test_cross_channel.py", "mock_module": "", "mock_class": ""},
    }
    
    info = module_info.get(module)
    if not info:
        module_logger.error(f"Unknown module: {module}")
        return False, [], []
    
    port = info["port"]
    test_file = info["test_file"]
    mock_module = info["mock_module"]
    mock_class = info["mock_class"]
    
    test_path = BOT_TEST_DIR / test_file
    if not test_path.exists():
        module_logger.error(f"Test file not found: {test_path}")
        return False, [], []
    
    # Prepare config
    config_dir = TEST_DIR / ".octos"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / f"test_{module}_config.json"
    
    if module in ["telegram", "tg"]:
        extra_env = {"TELEGRAM_API_URL": f"http://127.0.0.1:{port}"}
        # Use UserProfile format for --profile parameter
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        config = {
            "id": "test_telegram_bot",
            "name": "Test Telegram Bot",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
            "config": {
                "version": 1,
                "llm": {
                    "primary": {
                        "family_id": "openai",
                        "model_id": "deepseek-ai/deepseek-v4-pro",
                        "route": {
                            "api_key_env": "OPENAI_API_KEY",
                            "base_url": "https://integrate.api.nvidia.com/v1"
                        }
                    },
                    "fallbacks": []
                },
                "channels": [{
                    "type": "telegram",
                    "token_env": "TELEGRAM_BOT_TOKEN",
                    "allowed_senders": "testuser,user_a,user_b"
                }],
                "gateway": {
                    "max_history": 5,
                    "max_concurrent_sessions": 10,
                    "system_prompt": "IMPORTANT: When calling the message tool, NEVER specify the channel or chat_id parameters. Leave them empty/null so the system uses the current conversation context. Do not pass strings like 'console', 'current', 'telegram', 'discord', 'slack' or any other value for channel."
                }
            }
        }
    elif module in ["discord", "dc"]:
        if not os.environ.get("DISCORD_BOT_TOKEN"):
            os.environ["DISCORD_BOT_TOKEN"] = "mock-bot-token-for-testing"
            module_logger.info("DISCORD_BOT_TOKEN not set, using dummy value (mock mode)")
        extra_env = {"DISCORD_API_BASE_URL": f"http://127.0.0.1:{port}"}
        # Use UserProfile format for --profile parameter
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        config = {
            "id": "test_discord_bot",
            "name": "Test Discord Bot",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
            "config": {
                "version": 1,
                "llm": {
                    "primary": {
                        "family_id": "openai",
                        "model_id": "deepseek-ai/deepseek-v4-pro",
                        "route": {
                            "api_key_env": "OPENAI_API_KEY",
                            "base_url": "https://integrate.api.nvidia.com/v1"
                        }
                    },
                    "fallbacks": []
                },
                "channels": [{
                    "type": "discord",
                    "token_env": "DISCORD_BOT_TOKEN"
                }],
                "gateway": {
                    "max_history": 5,
                    "max_concurrent_sessions": 10,
                    "system_prompt": "IMPORTANT: When calling the message tool, NEVER specify the channel or chat_id parameters. Leave them empty/null so the system uses the current conversation context. Do not pass strings like 'console', 'current', 'telegram', 'discord', 'slack' or any other value for channel."
                }
            }
        }
    elif module in ["matrix", "mx"]:
        # Matrix appservice listens on port 8009, mock server on port 5002
        extra_env = {"OCTOS_APPSERVICE_URL": "http://127.0.0.1:8009"}
        # Use UserProfile format for --profile parameter
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        config = {
            "id": "test_matrix_bot",
            "name": "Test Matrix Bot",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
            "config": {
                "version": 1,
                "llm": {
                    "primary": {
                        "family_id": "openai",
                        "model_id": "deepseek-ai/deepseek-v4-pro",
                        "route": {
                            "api_key_env": "OPENAI_API_KEY",
                            "base_url": "https://integrate.api.nvidia.com/v1"
                        }
                    },
                    "fallbacks": []
                },
                "channels": [{
                    "type": "matrix",
                    "homeserver": f"http://127.0.0.1:{port}",
                    "as_token": "test_token",
                    "hs_token": "test_secret",
                    "server_name": "localhost",
                    "sender_localpart": "bot",
                    "user_prefix": "bot_",
                    "port": 8009,
                    "allowed_senders": []
                }],
                "admin_mode": True,  # Enable slash commands (/createbot, /listbots, /deletebot)
            }
        }
    elif module in ["slack", "sl"]:
        # Slack Socket Mode, requires bot_token and app_token
        port = 5003
        mock_module = "mock_slack"
        mock_class = "MockSlackServer"
        extra_env = {
            "SLACK_BOT_TOKEN": "xoxb-test-bot-token",
            "SLACK_APP_TOKEN": "xapp-test-app-token",
            "SLACK_API_BASE_URL": f"http://127.0.0.1:{port}/api",  # Point to mock server base URL
        }
        # Use UserProfile format (required by gateway --profile)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        config = {
            "id": "test_slack_bot",
            "name": "Test Slack Bot",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
            "config": {
                "version": 1,
                "llm": {
                    "primary": {
                        "family_id": "openai",
                        "model_id": "deepseek-ai/deepseek-v4-pro",
                        "route": {
                            "api_key_env": "OPENAI_API_KEY",
                            "base_url": "https://integrate.api.nvidia.com/v1"
                        }
                    },
                    "fallbacks": []
                },
                "channels": [
                    {
                        "type": "slack",
                        "bot_token_env": "SLACK_BOT_TOKEN",
                        "app_token_env": "SLACK_APP_TOKEN"
                    }
                ],
                "gateway": {
                    "max_history": 5,
                    "max_concurrent_sessions": 10,
                    "system_prompt": "IMPORTANT: When calling the message tool, NEVER specify the channel or chat_id parameters. Leave them empty/null so the system uses the current conversation context. Do not pass strings like 'console', 'current', 'telegram', 'discord', 'slack' or any other value for channel."
                }
            }
        }
    elif module in ["feishu", "fs"]:
        # 飞书 Webhook 模式
        port = 5004
        mock_module = "mock_feishu"
        mock_class = "MockFeishuServer"
        extra_env = {
            "FEISHU_APP_ID": "cli_test_app_id",
            "FEISHU_APP_SECRET": "test_app_secret",
        }
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        config = {
            "id": "test_feishu_bot",
            "name": "Test Feishu Bot",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
            "config": {
                "version": 1,
                "llm": {
                    "primary": {
                        "family_id": "openai",
                        "model_id": "deepseek-ai/deepseek-v4-pro",
                        "route": {
                            "api_key_env": "OPENAI_API_KEY",
                            "base_url": "https://integrate.api.nvidia.com/v1"
                        }
                    },
                    "fallbacks": []
                },
                "channels": [{
                    "type": "feishu",
                    "mode": "webhook",
                    "base_url": f"http://127.0.0.1:{port}",
                    "webhook_port": 9321,
                }],
                "gateway": {
                    "max_history": 5,
                    "max_concurrent_sessions": 10,
                    "system_prompt": "IMPORTANT: When calling the message tool, NEVER specify the channel or chat_id parameters. Leave them empty/null so the system uses the current conversation context. Do not pass strings like 'console', 'current', 'telegram', 'discord', 'slack' or any other value for channel."
                }
            }
        }
    elif module in ["wechat", "wx"]:
        # 微信 WebSocket bridge 模式
        port = 5005
        mock_module = "mock_wechat"
        mock_class = "MockWeChatServer"
        extra_env = {}
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        config = {
            "id": "test_wechat_bot",
            "name": "Test WeChat Bot",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
            "config": {
                "version": 1,
                "llm": {
                    "primary": {
                        "family_id": "openai",
                        "model_id": "deepseek-ai/deepseek-v4-pro",
                        "route": {
                            "api_key_env": "OPENAI_API_KEY",
                            "base_url": "https://integrate.api.nvidia.com/v1"
                        }
                    },
                    "fallbacks": []
                },
                "channels": [{
                    "type": "wechat",
                    "bridge_url": f"ws://127.0.0.1:{port}/ws",
                }],
                "gateway": {
                    "max_history": 5,
                    "max_concurrent_sessions": 10,
                    "system_prompt": "IMPORTANT: When calling the message tool, NEVER specify the channel or chat_id parameters. Leave them empty/null so the system uses the current conversation context. Do not pass strings like 'console', 'current', 'telegram', 'discord', 'slack' or any other value for channel."
                }
            }
        }

    elif module in ["whatsapp", "wa"]:
        # WhatsApp WebSocket bridge 模式
        port = 5006
        mock_module = "mock_whatsapp"
        mock_class = "MockWhatsAppServer"
        extra_env = {}
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        config = {
            "id": "test_whatsapp_bot",
            "name": "Test WhatsApp Bot",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
            "config": {
                "version": 1,
                "llm": {
                    "primary": {
                        "family_id": "openai",
                        "model_id": "deepseek-ai/deepseek-v4-pro",
                        "route": {
                            "api_key_env": "OPENAI_API_KEY",
                            "base_url": "https://integrate.api.nvidia.com/v1"
                        }
                    },
                    "fallbacks": []
                },
                "channels": [{
                    "type": "whatsapp",
                    "bridge_url": f"ws://127.0.0.1:{port}/ws",
                }],
                "gateway": {
                    "max_history": 5,
                    "max_concurrent_sessions": 10,
                    "system_prompt": "IMPORTANT: When calling the message tool, NEVER specify the channel or chat_id parameters. Leave them empty/null so the system uses the current conversation context. Do not pass strings like 'console', 'current', 'telegram', 'discord', 'slack' or any other value for channel."
                }
            }
        }
    elif module in ["line", "ln"]:
        port = 5007
        extra_env = {
            "LINE_CHANNEL_SECRET": "test_secret",
            "LINE_CHANNEL_ACCESS_TOKEN": "test_token",
            "LINE_API_BASE_URL": f"http://127.0.0.1:{port}",
        }
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        webhook_port = 8647
        config = {
            "id": "test_line_bot",
            "name": "Test LINE Bot",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
            "config": {
                "version": 1,
                "llm": {
                    "primary": {
                        "family_id": "openai",
                        "model_id": "deepseek-ai/deepseek-v4-pro",
                        "route": {
                            "api_key_env": "OPENAI_API_KEY",
                            "base_url": "https://integrate.api.nvidia.com/v1"
                        }
                    },
                    "fallbacks": []
                },
                "channels": [{
                    "type": "line",
                    "channel_secret_env": "LINE_CHANNEL_SECRET",
                    "channel_access_token_env": "LINE_CHANNEL_ACCESS_TOKEN",
                    "webhook_port": webhook_port,
                    "allowed_senders": "U_test_user,U_line_test_1,U_line_test_2,U_line_test_3,U_line_dedup,U_line_media,U_line_mention",
                }],
                "gateway": {
                    "max_history": 5,
                    "max_concurrent_sessions": 10,
                    "system_prompt": "IMPORTANT: When calling the message tool, NEVER specify the channel or chat_id parameters. Leave them empty/null so the system uses the current conversation context. Do not pass strings like 'console', 'current', 'telegram', 'discord', 'slack' or any other value for channel."
                }
            }
        }
    elif module in ["wecom-bot", "wecom_bot", "wcb"]:
        port = 5008
        extra_env = {
            "WECOM_BOT_WS_URL": f"ws://127.0.0.1:{port}/ws",
        }
        if not os.environ.get("WECOM_BOT_SECRET"):
            os.environ["WECOM_BOT_SECRET"] = "test-mock-secret"
            module_logger.info("WECOM_BOT_SECRET not set, using dummy value (mock mode)")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        config = {
            "id": "test_wecom_bot",
            "name": "Test WeCom Bot",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
            "config": {
                "version": 1,
                "llm": {
                    "primary": {
                        "family_id": "openai",
                        "model_id": "deepseek-ai/deepseek-v4-pro",
                        "route": {
                            "api_key_env": "OPENAI_API_KEY",
                            "base_url": "https://integrate.api.nvidia.com/v1"
                        }
                    },
                    "fallbacks": []
                },
                "channels": [{
                    "type": "wecom-bot",
                    "bot_id": "test_bot_id",
                    "secret_env": "WECOM_BOT_SECRET",
                    "allowed_senders": "wcb_user1,wcb_user2,wcb_allowed,wcb_dedup_user",
                }],
                "gateway": {
                    "max_history": 5,
                    "max_concurrent_sessions": 10,
                    "system_prompt": "IMPORTANT: When calling the message tool, NEVER specify the channel or chat_id parameters. Leave them empty/null so the system uses the current conversation context. Do not pass strings like 'console', 'current', 'telegram', 'discord', 'slack' or any other value for channel."
                }
            }
        }
    elif module in ["wecom", "we"]:
        port = 5009
        webhook_port = 9323
        extra_env = {
            "WECOM_API_BASE_URL": f"http://127.0.0.1:{port}/cgi-bin",
            "WECOM_CORP_ID": "test_corp_id",
            "WECOM_AGENT_SECRET": "test_agent_secret",
        }
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        config = {
            "id": "test_wecom",
            "name": "Test WeCom",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
            "config": {
                "version": 1,
                "llm": {
                    "primary": {
                        "family_id": "openai",
                        "model_id": "deepseek-ai/deepseek-v4-pro",
                        "route": {
                            "api_key_env": "OPENAI_API_KEY",
                            "base_url": "https://integrate.api.nvidia.com/v1"
                        }
                    },
                    "fallbacks": []
                },
                "channels": [{
                    "type": "wecom",
                    "corp_id_env": "WECOM_CORP_ID",
                    "agent_secret_env": "WECOM_AGENT_SECRET",
                    "agent_id": "test_agent",
                    "verification_token": "test_verification_token",
                    "encoding_aes_key": "5sYHlCoSGoM55cptBeBF48DRmOZbeYowtPcgwjRQSxc",
                    "webhook_port": webhook_port,
                    "allowed_senders": "wecom_session_user,wecom_config_user,wecom_allowed,wecom_dedup_user",
                }],
                "gateway": {
                    "max_history": 5,
                    "max_concurrent_sessions": 10,
                    "system_prompt": "IMPORTANT: When calling the message tool, NEVER specify the channel or chat_id parameters. Leave them empty/null so the system uses the current conversation context. Do not pass strings like 'console', 'current', 'telegram', 'discord', 'slack' or any other value for channel."
                }
            }
        }
    elif module in ["qq-bot", "qq_bot", "qq"]:
        port = 5010
        extra_env = {
            "QQ_BOT_API_BASE_URL": f"http://127.0.0.1:{port}",
        }
        if not os.environ.get("QQ_BOT_APP_ID"):
            os.environ["QQ_BOT_APP_ID"] = "test_app_id"
            module_logger.info("QQ_BOT_APP_ID not set, using dummy value (mock mode)")
        if not os.environ.get("QQ_BOT_CLIENT_SECRET"):
            os.environ["QQ_BOT_CLIENT_SECRET"] = "test_client_secret"
            module_logger.info("QQ_BOT_CLIENT_SECRET not set, using dummy value (mock mode)")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        config = {
            "id": "test_qq_bot",
            "name": "Test QQ Bot",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
            "config": {
                "version": 1,
                "llm": {
                    "primary": {
                        "family_id": "openai",
                        "model_id": "deepseek-ai/deepseek-v4-pro",
                        "route": {
                            "api_key_env": "OPENAI_API_KEY",
                            "base_url": "https://integrate.api.nvidia.com/v1"
                        }
                    },
                    "fallbacks": []
                },
                "channels": [{
                    "type": "qq-bot",
                    "app_id": os.environ.get("QQ_BOT_APP_ID", "test_app_id"),
                    "client_secret_env": "QQ_BOT_CLIENT_SECRET",
                    "allowed_senders": "member_test_001,member_test_002,member_test_003,user_c2c_session,user_c2c_config,user_c2c_dedup",
                }],
                "gateway": {
                    "max_history": 5,
                    "max_concurrent_sessions": 10,
                    "system_prompt": "IMPORTANT: When calling the message tool, NEVER specify the channel or chat_id parameters. Leave them empty/null so the system uses the current conversation context. Do not pass strings like 'console', 'current', 'telegram', 'discord', 'slack' or any other value for channel."
                }
            }
        }
    elif module in ["twilio", "tw"]:
        port = 5011
        webhook_port = 8649
        extra_env = {
            "TWILIO_API_BASE_URL": f"http://127.0.0.1:{port}",
        }
        if not os.environ.get("TWILIO_ACCOUNT_SID"):
            os.environ["TWILIO_ACCOUNT_SID"] = "ACtest"
            module_logger.info("TWILIO_ACCOUNT_SID not set, using dummy value (mock mode)")
        if not os.environ.get("TWILIO_AUTH_TOKEN"):
            os.environ["TWILIO_AUTH_TOKEN"] = "test_auth_token"
            module_logger.info("TWILIO_AUTH_TOKEN not set, using dummy value (mock mode)")
        if not os.environ.get("TWILIO_FROM_NUMBER"):
            os.environ["TWILIO_FROM_NUMBER"] = "+15559999999"
            module_logger.info("TWILIO_FROM_NUMBER not set, using dummy value (mock mode)")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        config = {
            "id": "test_twilio",
            "name": "Test Twilio",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
            "config": {
                "version": 1,
                "llm": {
                    "primary": {
                        "family_id": "openai",
                        "model_id": "deepseek-ai/deepseek-v4-pro",
                        "route": {
                            "api_key_env": "OPENAI_API_KEY",
                            "base_url": "https://integrate.api.nvidia.com/v1"
                        }
                    },
                    "fallbacks": []
                },
                "channels": [{
                    "type": "twilio",
                    "account_sid_env": "TWILIO_ACCOUNT_SID",
                    "auth_token_env": "TWILIO_AUTH_TOKEN",
                    "from_number_env": "TWILIO_FROM_NUMBER",
                    "webhook_port": webhook_port,
                    "allowed_senders": "+15550000001,+15550001001,+15550001002,+15550001003,+15550001004,+15550001005",
                }],
                "gateway": {
                    "max_history": 5,
                    "max_concurrent_sessions": 10,
                    "system_prompt": "IMPORTANT: When calling the message tool, NEVER specify the channel or chat_id parameters. Leave them empty/null so the system uses the current conversation context. Do not pass strings like 'console', 'current', 'telegram', 'discord', 'slack' or any other value for channel."
                }
            }
        }

    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    
    # Clean up previous test artifacts
    module_logger.info("Cleaning up previous test artifacts...")
    
    # Kill any existing processes on the port
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            capture_output=True,
            text=True,
        )
        pids = result.stdout.strip().splitlines()
        for pid in pids:
            if pid:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                    module_logger.info(f"Killed process {pid} on port {port}")
                except ProcessLookupError:
                    pass
        if pids:
            time.sleep(1)
    except Exception:
        pass
    
    # Remove database lock files
    db_files = list(TEST_DIR.glob("*.redb")) + list(TEST_DIR.glob("*.redb.lock"))
    for db_file in db_files:
        try:
            db_file.unlink()
            module_logger.info(f"Removed database file: {db_file}")
        except FileNotFoundError:
            pass
    
    # Clear Python cache
    import shutil
    for pattern in ["__pycache__", "*.pyc", ".pytest_cache"]:
        for path in BOT_TEST_DIR.glob(f"**/{pattern}"):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.is_file():
                path.unlink(missing_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    bot_log = LOG_DIR / f"02_gateway_{module}_{timestamp}.log"

    # Start Mock Server
    mock_code = f"""
import time, signal, sys, logging
from {mock_module} import {mock_class}
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("serenity").setLevel(logging.ERROR)
server = {mock_class}(port={port})
server.start_background(log_file='{bot_log}')
print('ready', flush=True)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
while True:
    time.sleep(1)
"""

    mock_proc = subprocess.Popen(
        [str(venv_python), "-c", mock_code],
        env={**os.environ, **extra_env, "PYTHONPATH": str(BOT_TEST_DIR), "PYTHONDONTWRITEBYTECODE": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    health_timeout = 10 if module in ["telegram", "tg"] else (10 if module in ["discord", "dc"] else 3)
    start = time.time()
    mock_ready = False
    last_error = None

    while time.time() - start < health_timeout:
        if mock_proc.poll() is not None:
            stdout, _ = mock_proc.communicate()
            last_error = stdout.decode('utf-8', errors='ignore') if stdout else "Unknown error"
            break
        try:
            resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2)
            if resp.status_code == 200:
                mock_ready = True
                break
        except Exception as e:
            last_error = str(e)
        time.sleep(0.5)

    if not mock_ready:
        module_logger.error(f"{module} Mock server failed to start")
        if last_error:
            module_logger.error(f"Error details: {last_error}")
        try:
            mock_proc.terminate()
            stdout, _ = mock_proc.communicate(timeout=2)
            if stdout:
                output = stdout.decode('utf-8', errors='ignore')
                module_logger.error(f"Mock server output:\n{output}")
        except Exception:
            pass
        return False, [], []

    mock_pid = mock_proc.pid
    module_logger.info(f"{module} Mock server running on port {port} (PID {mock_pid})")


    # Start Octos Gateway
    if not BINARY_PATH.exists():
        module_logger.error(f"Octos binary not found: {BINARY_PATH}")
        if mock_pid is not None:
            mock_proc.terminate()
        return False, [], []
    
    bot_env = {**os.environ, **extra_env}
    
    # Open log file for bot output
    bot_log_file = open(bot_log, 'w')
    
    bot_proc = subprocess.Popen(
        [str(BINARY_PATH), "gateway", "--profile", str(config_file), "--data-dir", str(TEST_DIR)],
        env=bot_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    bot_pid = bot_proc.pid
    module_logger.info(f"Bot PID: {bot_pid}")
    
    # Start a thread to read bot output and tee to file + stdout
    import threading
    import select
    import sys  # Import sys inside the function scope
    
    def tee_output(proc, log_file):
        """Read process output and write to both file and stdout.
        
        Uses non-blocking reads with timeout to avoid blocking indefinitely.
        Handles file closure gracefully.
        """
        try:
            while True:
                # Check if process is still running
                if proc.poll() is not None:
                    # Process ended, read any remaining output
                    remaining = proc.stdout.read()
                    if remaining:
                        text = remaining.decode('utf-8', errors='ignore')
                        try:
                            log_file.write(text)
                            log_file.flush()
                        except (ValueError, IOError):
                            pass  # File already closed, skip
                        sys.stdout.write(text)
                        sys.stdout.flush()
                    break
                
                # Try to read a line with a short timeout
                line = proc.stdout.readline()
                if not line:  # EOF or empty
                    time.sleep(0.1)  # Small delay to avoid busy-waiting
                    continue
                
                text = line.decode('utf-8', errors='ignore')
                # Write to file (handle closed file gracefully)
                try:
                    log_file.write(text)
                    log_file.flush()
                except (ValueError, IOError):
                    pass  # File already closed, continue writing to stdout only
                
                # Write to stdout
                sys.stdout.write(text)
                sys.stdout.flush()
        except Exception as e:
            # Only log unexpected errors, not file closure issues
            if not isinstance(e, (ValueError, IOError)):
                module_logger.error(f"Tee thread error: {e}")
                import traceback
                traceback.print_exc()
    
    tee_thread = threading.Thread(target=tee_output, args=(bot_proc, bot_log_file), daemon=True)
    tee_thread.start()
    
    # Wait for gateway to start
    module_logger.info("Waiting for gateway to start...")
    
    ready = False
    max_wait = 50 if module in ["discord", "dc"] else 40
    start = time.time()
    
    try:
        while time.time() - start < max_wait:
            if bot_proc.poll() is not None:
                module_logger.error("Bot process exited unexpectedly")
                break
            
            # Check both file and captured output
            found_ready = False
            try:
                with open(bot_log) as f:
                    content = f.read()
                    if re.search(r"gateway.*ready|Gateway ready|\[gateway\] ready", content):
                        found_ready = True
            except FileNotFoundError:
                pass
            
            if found_ready:
                # Give tee thread a moment to finish writing
                time.sleep(0.5)
                ready = True
                break
            
            time.sleep(1)
    finally:
        def cleanup():
            # Step 1: Terminate processes first (tee thread will detect EOF)
            try:
                os.kill(bot_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            if mock_pid is not None:
                try:
                    os.kill(mock_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            
            # Step 2: Wait for processes to exit and tee thread to finish
            time.sleep(1)
            
            # Force kill if still running
            try:
                os.kill(bot_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            if mock_pid is not None:
                try:
                    os.kill(mock_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            
            # Step 3: Wait for tee thread to finish (it should exit when process ends)
            try:
                tee_thread.join(timeout=3)
            except Exception:
                pass
            
            # Step 4: Close log file AFTER tee thread has finished
            try:
                bot_log_file.close()
            except Exception:
                pass
    
    if not ready:
        module_logger.error("Bot failed to start. Full log:")
        try:
            with open(bot_log) as f:
                for line in f:
                    module_logger.info(f"    {line.rstrip()}")
        except FileNotFoundError:
            pass
        cleanup()
        return False, [], []
    
    module_logger.info("Gateway ready!")
    
    # Run pytest
    pytest_args = [
        str(venv_python), "-u", "-m", "pytest",  # -u for unbuffered output
        str(test_path),
        "--tb=line", "--no-header", "-p", "no:warnings",
        "--log-cli-level=DEBUG",  # Show all debug logs for troubleshooting
        "--color=yes",  # Enable colored output for better readability
        "-v",  # Verbose mode: show test name and status
    ]
    
    if test_case:
        pytest_args.extend(["-k", test_case])
        module_logger.info(f"Running specific test: {test_case}")
    
    module_logger.info(f"Executing: {' '.join(pytest_args)}")
    
    # Start pytest process
    pytest_env = {
        **os.environ,
        "PYTHONPATH": str(BOT_TEST_DIR),
        "MOCK_BASE_URL": f"http://127.0.0.1:{port}",
        "PYTHONUNBUFFERED": "1",  # Force unbuffered output at interpreter level
    }
    
    pytest_proc = subprocess.Popen(
        pytest_args,
        env=pytest_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    
    # Read pytest output line by line and log it
    # This ensures unified timestamp format and perfect ordering
    import sys
    failed_tests = []  # Collect failed test names
    passed_tests = []  # Collect passed test names
    error_messages = []  # Collect error messages for unknown failures
    current_test_name = None  # Track the current test being executed
    while True:
        # Check if Mock Server is still alive
        if mock_pid is not None and mock_proc.poll() is not None:
            module_logger.error("❌ Mock Server process exited unexpectedly during tests!")
            try:
                stdout, _ = mock_proc.communicate(timeout=2)
                if stdout:
                    module_logger.error(f"Mock Server last output:\n{stdout.decode('utf-8', errors='ignore')}")
            except Exception:
                pass
            break

        # Check if Bot is still alive
        if bot_proc.poll() is not None:
            module_logger.error("❌ Bot process exited unexpectedly during tests!")
            break

        line = pytest_proc.stdout.readline()
        if not line:
            if pytest_proc.poll() is not None:
                break
            time.sleep(0.1)
            continue

        text = line.decode('utf-8', errors='ignore').rstrip()
        if text:
            # Clean up excessive whitespace in pytest output
            # Remove trailing progress indicators like [XX%] and extra spaces
            cleaned_text = re.sub(r'\s+\[\d+%\]\s*$', '', text)  # Remove [XX%]
            cleaned_text = re.sub(r'\s{2,}', ' ', cleaned_text)  # Collapse multiple spaces to one
            module_logger.info(f"[PYTEST] {cleaned_text}")
            clean_text = re.sub(r'\x1b\[[0-9;]*m', '', text)
            
            # Track current test name from lines like: "bot_mock_test/test_slack.py::TestClass::test_name"
            test_name_match = re.search(r'(\S+\.py::\S+::\S+)', clean_text)
            if test_name_match:
                full_test_path = test_name_match.group(1)
                current_test_name = full_test_path.split('::')[-1]  # Extract just the function name
            
            # Match PASSED/FAILED status (may be on separate line from test name)
            status_match = re.search(r'\b(PASSED|FAILED)\b', clean_text)
            if status_match and current_test_name:
                status = status_match.group(1)
                if status == 'FAILED' and current_test_name not in failed_tests:
                    failed_tests.append(current_test_name)
                elif status == 'PASSED' and current_test_name not in passed_tests:
                    passed_tests.append(current_test_name)
            elif 'ERROR' in text and ('test_' in text or 'setup' in text.lower()):
                error_messages.append(text)
    
    pytest_proc.wait(timeout=300)
    result = subprocess.CompletedProcess(
        args=pytest_args,
        returncode=pytest_proc.returncode,
    )
    
    cleanup()

    # Check if all tests were skipped (pytest returns 0 for all-skipped)
    all_skipped = len(failed_tests) == 0 and len(passed_tests) == 0
    
    if result.returncode == 0:
        if all_skipped:
            module_logger.warning(f"⚠️  All {module} tests were SKIPPED (no tests actually ran)")
            module_logger.warning(f"   This usually means Mock Server or Bot is not responding properly")
            module_logger.warning(f"   Check the logs above for skip reasons")
            # Return False to indicate tests didn't actually pass
            return False, ["ALL_TESTS_SKIPPED"], []
        else:
            module_logger.info(f"✅ All {module} tests passed!")
    else:
        module_logger.error(f"❌ Some {module} tests failed")
        if failed_tests:
            module_logger.error(f"Failed tests: {', '.join(failed_tests)}")
        elif error_messages:
            # If we have error messages but no specific test names, use those
            module_logger.error(f"Errors detected: {len(error_messages)} issues")
            for err_msg in error_messages[:5]:  # Show first 5 errors
                module_logger.error(f"  - {err_msg}")

    # Return (passed, failed_tests, passed_tests) for flaky detection
    return result.returncode == 0 and not all_skipped, failed_tests if failed_tests else error_messages, passed_tests


def run_bot_test_with_per_test_retry(module: str, from_test: Optional[str] = None) -> Tuple[bool, List[str]]:
    """Run bot tests with per-test retry and service restart on failure.

    Strategy:
    1. Run all tests in order (or from specified test if from_test is set)
    2. On ANY failure: check if subsequent tests passed (flaky pattern)
    3. If flaky detected: restart services, retry ALL tests from first failure onwards
    4. If NOT flaky (all subsequent tests also failed/skipped): retry just the first failed test
    5. Retry only once. If still fails, report final failure.

    This handles two scenarios:
    - Flaky failures: state corruption that clears later → retry all from first failure
    - Real failures: persistent issues → retry first failed test to confirm

    Args:
        module: Bot module name (telegram/discord)
        from_test: Optional test name to start from. If set, runs this test and all subsequent tests.

    Returns:
        Tuple of (all_passed, failed_test_names)
    """
    module_logger = logger_mgr.get_module_logger(f"bot_{module}")

    # Get full test order
    all_tests = get_test_order(module)
    if not all_tests:
        module_logger.warning("Could not determine test order")
        passed, failed, _ = run_bot_test(module)
        return passed, failed

    module_logger.info(f"Total tests in {module}: {len(all_tests)}")

    # If from_test is specified, filter to run from that test onwards
    if from_test:
        from_idx = None
        for i, test in enumerate(all_tests):
            if test == from_test or from_test in test:
                from_idx = i
                break
        
        if from_idx is not None:
            all_tests = all_tests[from_idx:]
            module_logger.info(f"🎯 Running from test: {from_test} (index {from_idx})")
            module_logger.info(f"📋 Tests to run: {len(all_tests)}")
        else:
            module_logger.warning(f"⚠️  Test '{from_test}' not found, running all tests")

    # Track overall results
    failed_tests = []
    passed_tests = []

    # Run all tests first (with from_test filter if specified)
    test_filter = None
    if from_test:
        # Convert filtered test list to pytest -k expression
        test_filter = " or ".join(all_tests)
        module_logger.info(f"🔍 Using pytest filter: {test_filter[:100]}{'...' if len(test_filter) > 100 else ''}")
    
    passed, failed, passed_tests = run_bot_test(module, test_case=test_filter)

    if passed:
        return True, []

    # Find the first failure index
    first_failure_idx = None
    for i, test in enumerate(all_tests):
        if test in set(failed):
            first_failure_idx = i
            break

    if first_failure_idx is None:
        module_logger.warning("No failed tests found despite non-zero exit code")
        return False, failed

    first_failed_test = all_tests[first_failure_idx]
    module_logger.info(f"🔄 First failure: {first_failed_test} at index {first_failure_idx}")

    # Check if this is a flaky failure (some tests passed after first failure)
    is_flaky = detect_flaky_failure(failed, passed_tests, all_tests)

    if is_flaky:
        # Flaky pattern detected: retry ALL tests from first failure onwards
        tests_to_rerun = get_tests_to_rerun(failed, all_tests)
        module_logger.info(f"🔄 Flaky failure detected! Some tests passed after first failure")
        module_logger.info(f"🔄 Retrying {len(tests_to_rerun)} tests from first failure onwards")
        module_logger.info(f"🔄 Tests: {', '.join(tests_to_rerun[:5])}{'...' if len(tests_to_rerun) > 5 else ''}")
        
        # Restart services and retry all tests from first failure
        test_filter = " or ".join(tests_to_rerun)
        retry_passed, retry_failed, _ = run_bot_test(module, test_filter)

        if retry_passed:
            module_logger.info(f"✅ Retry succeeded! All {len(tests_to_rerun)} tests passed")
            return True, []
        else:
            module_logger.error(f"❌ Retry also failed, stopping")
            return False, retry_failed
    else:
        # Not flaky: all subsequent tests also failed/skipped
        # Just retry the first failed test to confirm it's a real failure
        module_logger.info(f"🔄 No flaky pattern (all subsequent tests also failed)")
        module_logger.info(f"🔄 Restarting services to retry first failed test...")
        
        retry_passed, retry_failed, _ = run_bot_test(module, first_failed_test)

        if retry_passed:
            module_logger.info(f"✅ Retry succeeded for {first_failed_test}!")
            module_logger.info(f"   Continuing with remaining tests...")
            # Continue running the rest of the tests
            remaining_tests = all_tests[first_failure_idx + 1:]
            if remaining_tests:
                cont_passed, cont_failed, _ = run_bot_test(module, " or ".join(remaining_tests))
                if cont_passed:
                    return True, []
                else:
                    failed_tests.extend(retry_failed)
                    failed_tests.extend(cont_failed)
                    return False, failed_tests
            return True, []
        else:
            module_logger.error(f"❌ Retry also failed for {first_failed_test}, stopping")
            return False, retry_failed


def run_bot_test_with_flaky_retry(module: str) -> Tuple[bool, List[str]]:
    """Run bot tests with automatic flaky retry.

    If a test fails but subsequent tests pass, this suggests the failure
    was due to state corruption (flaky). Automatically retries from the
    first failing test onwards.

    Only retries once. If retry also fails, reports final failure.

    Returns:
        Tuple of (all_passed, failed_test_names)
    """
    module_logger = logger_mgr.get_module_logger(f"bot_{module}")

    # Get full test order for determining which tests to rerun
    all_tests = get_test_order(module)
    if not all_tests:
        module_logger.warning("Could not determine test order")
        passed, failed, _ = run_bot_test(module)
        return passed, failed

    module_logger.info(f"Total tests in {module}: {len(all_tests)}")

    # First run: all tests
    passed, failed, passed_tests = run_bot_test(module)

    if passed:
        return True, []

    # Check if failure was flaky (failure followed by later passes)
    if not detect_flaky_failure(failed, passed_tests, all_tests):
        module_logger.info("No flaky pattern detected, not retrying")
        return False, failed

    # Flaky detected - determine tests to rerun from first failure onwards
    tests_to_rerun = get_tests_to_rerun(failed, all_tests)
    if not tests_to_rerun:
        module_logger.warning("Could not determine tests to rerun")
        return False, failed

    module_logger.info(f"🔄 Flaky failure detected (some tests passed after failure)")
    module_logger.info(f"🔄 Retrying {len(tests_to_rerun)} tests from first failure")
    module_logger.info(f"🔄 Tests: {', '.join(tests_to_rerun[:5])}{'...' if len(tests_to_rerun) > 5 else ''}")

    # Retry from first failure onwards
    test_filter = " or ".join(tests_to_rerun)
    retry_passed, retry_failed, _ = run_bot_test(module, test_filter)

    if retry_passed:
        module_logger.info(f"✅ Retry succeeded!")
        return True, []

    module_logger.error(f"❌ Retry also failed, stopping")
    return False, retry_failed


def run_all_bot_tests(from_test: Optional[str] = None, return_details: bool = False) -> Tuple[bool, List[str]]:
    """Run all bot tests (telegram + discord + matrix + ...).
    
    Args:
        from_test: Optional test name to start from. Applied to both modules.
        return_details: If True, also return detailed results list.
    
    Returns:
        Tuple of (all_passed, error_messages) or (all_passed, error_messages, detailed_results)
    """
    log.info("=" * 60)
    log.info("Running ALL bot tests")
    if from_test:
        log.info(f"Starting from test: {from_test}")
    log.info("=" * 60)
    
    modules = ["telegram", "discord", "matrix", "slack", "feishu", "wechat", "whatsapp", "wecom-bot", "wecom", "qq-bot", "twilio"]
    all_passed = True
    errors = []
    detailed_results = []
    
    for module in modules:
        passed, failures = run_bot_test_with_per_test_retry(module, from_test=from_test)
        if not passed:
            all_passed = False
            # Add detailed error messages for each failed test
            if failures:
                for failure in failures:
                    # If it's an error message (not a test name), format it differently
                    if '::' in failure or failure.startswith('test_'):
                        errors.append(f"{module}: {failure}")
                        detailed_results.append({
                            "channel": module,
                            "test_id": failure,
                            "name": failure,
                            "status": "FAIL",
                        })
                    else:
                        # It's an error message, truncate if too long
                        error_summary = failure[:100] + "..." if len(failure) > 100 else failure
                        errors.append(f"{module}: {error_summary}")
                        detailed_results.append({
                            "channel": module,
                            "test_id": failure,
                            "name": error_summary,
                            "status": "FAIL",
                        })
            else:
                errors.append(f"{module}: (unknown failures - check logs)")
                detailed_results.append({
                    "channel": module,
                    "test_id": "unknown",
                    "name": "unknown failure",
                    "status": "FAIL",
                })
        else:
            # All passed for this module
            detailed_results.append({
                "channel": module,
                "test_id": "all",
                "name": f"{module} all tests",
                "status": "PASS",
            })
    
    if return_details:
        return all_passed, errors, detailed_results
    return all_passed, errors


def list_cli_categories():
    """List CLI test categories from full_cases.json."""
    test_cases_file = CLI_TEST_DIR / "full_cases.json"
    if not test_cases_file.exists():
        test_cases_file = CLI_TEST_DIR / "test_cases.json"
    if not test_cases_file.exists():
        print(f"Test cases file not found: {test_cases_file}")
        return
    
    with open(test_cases_file, 'r') as f:
        data = json.load(f)
    
    # Collect unique categories from tests list
    categories = sorted(set(t["category"] for t in data.get("tests", [])))
    
    print(f"\nAvailable CLI test categories ({len(categories)}):")
    for cat in categories:
        count = sum(1 for t in data["tests"] if t["category"] == cat)
        print(f"  - {cat} ({count} tests)")
    print("")


def list_cli_category_cases(category: str):
    """List test cases in a CLI category from full_cases.json."""
    test_cases_file = CLI_TEST_DIR / "full_cases.json"
    if not test_cases_file.exists():
        test_cases_file = CLI_TEST_DIR / "test_cases.json"
    if not test_cases_file.exists():
        print(f"Test cases file not found: {test_cases_file}")
        return
    
    with open(test_cases_file, 'r') as f:
        data = json.load(f)
    
    cases = [t for t in data.get("tests", []) if t["category"] == category]
    if not cases:
        print(f"Unknown category: {category}")
        return
    
    # Only list if it's a list type
    if not isinstance(cases, list):
        print(f"\n'{category}' is not a test category (type: {type(cases).__name__})")
        print(f"Value: {cases}")
        print("")
        return
    
    print(f"\nTest cases in '{category}':")
    for idx, case in enumerate(cases, 1):
        # Handle both string and dict formats
        if isinstance(case, str):
            print(f"  {idx}. {case}")
        elif isinstance(case, dict):
            print(f"  {idx}. {case.get('name', 'Unnamed')}")
        else:
            print(f"  {idx}. {case}")
    print(f"\nTotal: {len(cases)} test(s)\n")


def run_cli_tests(verbose: bool = False, output_dir: Optional[str] = None, scope: Optional[str] = None, return_details: bool = False) -> Tuple[bool, List[str]]:
    """Run CLI tests using the Python implementation.

    Args:
        return_details: If True, also return detailed results list.

    Returns:
        Tuple of (all_passed, error_messages) or (all_passed, error_messages, detailed_results)
    """
    cli_logger = logger_mgr.get_module_logger("cli")
    
    cli_logger.info("=" * 60)
    cli_logger.info("Running CLI tests")
    cli_logger.info("=" * 60)
    
    # Convert output_dir to Path if provided
    output_path = Path(output_dir) if output_dir else None
    
    try:
        # Call the Python CLI test module (always with return_details internally)
        result = run_cli_tests_module(
            binary_path=BINARY_PATH,
            test_dir=TEST_DIR,
            log_dir=LOG_DIR,
            verbose=verbose,
            output_dir=output_path,
            scope=scope,
            return_details=return_details,
        )
        
        if return_details:
            all_passed, errors, detailed = result
        else:
            all_passed, errors = result
            detailed = []
        
        if all_passed:
            cli_logger.info("✅ CLI tests passed")
        else:
            cli_logger.error("❌ CLI tests failed")
        
        if return_details:
            return all_passed, errors, detailed
        return all_passed, errors
    except Exception as e:
        cli_logger.error(f"CLI tests failed with exception: {e}")
        import traceback
        cli_logger.error(traceback.format_exc())
        if return_details:
            return False, [f"CLI tests exception: {str(e)}"], []
        return False, [f"CLI tests exception: {str(e)}"]


def list_serve_tests():
    """List available serve tests."""
    print("\nAvailable Serve tests:")
    print("  ── 公开端点 (无需认证) ──")
    print("  8.1   server_startup          - /health 健康检查")
    print("  8.2   version_endpoint       - /api/version 版本信息")
    print("  8.3   metrics_endpoint       - /metrics Prometheus 格式")
    print("  ── 认证 ──")
    print("  8.4   auth_token_required     - 无 token 请求返回 401")
    print("  8.5   auth_invalid_token      - 错误 token 返回 401/403")
    print("  ── Dashboard ──")
    print("  8.6   dashboard_webui         - Dashboard Web UI 加载")
    print("  ── WebSocket UI Protocol (API Channel) ──")
    print("  8.7   ws_connection           - WS 连接 + client/hello 握手")
    print("  8.8   ws_system_status        - WS system/status.get")
    print("  8.9   ws_session_list         - WS session/list")
    print("  8.10  ws_session_open_chat    - WS session/open + turn/start (需 API Key)")
    print("  8.11  ws_session_delete       - WS session/delete")
    print("  8.14  ws_session_snapshot     - WS session/snapshot (合并引导)")
    print("  8.15  ws_session_messages_page- WS session/messages_page (分页历史)")
    print("  8.16  ws_session_status_get    - WS session/status.get (单会话状态)")
    print("  8.17  ws_session_title_set     - WS session/title.set (重命名)")
    print("  8.18  ws_content_list          - WS content/list (内容目录)")
    print("  8.19  ws_turn_interrupt        - WS turn/interrupt (中断 turn, 需 API Key)")
    print("  ── 绑定地址 (环境限制) ──")
    print("  8.12  bind_address_external   - --host 0.0.0.0 绑定 ⚠️")
    print("  8.13  bind_address_local      - 默认 127.0.0.1 绑定 ⚠️")
    print("\n⚠️  8.10/8.19 需要 ANTHROPIC_API_KEY 或 OPENAI_API_KEY 才能获得 LLM 回复")
    print("⚠️  8.14–8.18 需要 LLM profile 配置才能创建会话")
    print("⚠️  8.12/8.13 存在环境限制, 详见 README.md\n")


def run_serve_tests(verbose: bool = False, test_ids: Optional[List[str]] = None, return_details: bool = False) -> Tuple[bool, List[str]]:
    """Run serve tests.

    Args:
        verbose: Enable verbose output
        test_ids: Specific test IDs to run (e.g., ['8.1', '8.2']). None means all.
        return_details: If True, also return detailed results list.

    Returns:
        Tuple of (all_passed, error_messages) or (all_passed, error_messages, detailed_results)
    """
    if not SERVE_TEST_AVAILABLE:
        log.error("Serve test module not available.")
        log.error("Please install required dependencies:")
        log.error("  pip install httpx pytest")
        log.error("")
        log.error("Or run from tests directory with proper PYTHONPATH")
        if return_details:
            return False, ["Serve test module import failed - missing dependencies"], []
        return False, ["Serve test module import failed - missing dependencies"]

    serve_logger = logger_mgr.get_module_logger("serve")

    serve_logger.info("=" * 60)
    serve_logger.info("Running Serve tests")
    serve_logger.info("=" * 60)

    # Create serve tester
    tester = OctosServeTester(BINARY_PATH, LOG_DIR)

    try:
        # Start server
        serve_logger.info("Starting octos serve...")
        if not tester.start_server(port=8080, host="127.0.0.1"):
            serve_logger.error("Failed to start octos serve")
            if return_details:
                return False, ["Failed to start server"], []
            return False, ["Failed to start server"]

        # Define all tests — MUST stay in sync with serve/test_serve.py __main__ list
        all_tests = [
            ("8.1", "Server Startup", tester.test_server_startup),
            ("8.2", "Version Endpoint", tester.test_version_endpoint),
            ("8.3", "Metrics Endpoint", tester.test_metrics_endpoint),
            ("8.4", "Auth Token Required", tester.test_auth_token_required),
            ("8.5", "Auth Invalid Token", tester.test_auth_invalid_token),
            ("8.6", "Dashboard Web UI", tester.test_dashboard_webui),
            ("8.7", "WS Connection + Hello", tester.test_ws_connection),
            ("8.8", "WS system/status.get", tester.test_ws_system_status),
            ("8.9", "WS session/list", tester.test_ws_session_list),
            ("8.10", "WS session/open + turn/start", tester.test_ws_session_open_and_chat),
            ("8.11", "WS session/delete", tester.test_ws_session_delete),
            ("8.14", "WS session/snapshot", tester.test_ws_session_snapshot),
            ("8.15", "WS session/messages_page", tester.test_ws_session_messages_page),
            ("8.16", "WS session/status.get", tester.test_ws_session_status_get),
            ("8.17", "WS session/title.set", tester.test_ws_session_title_set),
            ("8.18", "WS content/list", tester.test_ws_content_list),
            ("8.19", "WS turn/interrupt", tester.test_ws_turn_interrupt),
            # NOTE: 8.12/8.13 会重启服务器，放在最末尾避免影响后续测试
            # ── 10.x WS 基础协议 ──
            ("10.1", "WS Hello Capabilities", tester.test_10_1_ws_hello_capabilities),
            ("10.2", "Config Capabilities List", tester.test_10_2_ws_config_capabilities_list),
            ("10.3", "WS System Status", tester.test_10_3_ws_system_status),
            ("10.4", "WS Auth Me", tester.test_10_4_ws_auth_me),
            # ── 11.x Session ──
            ("11.1", "Session List Empty", tester.test_11_1_session_list_empty),
            ("11.2", "Profile Local Create", tester.test_11_2_profile_local_create),
            ("11.3", "Session Open After Profile", tester.test_11_3_session_open_after_profile),
            ("11.4", "Session List After Open", tester.test_11_4_session_list_after_open),
            ("11.5", "Session Title Set", tester.test_11_5_session_title_set_and_verify),
            ("11.6", "Session Messages Page", tester.test_11_6_session_messages_page),
            ("11.7", "Session Status Get", tester.test_11_7_session_status_get),
            ("11.8", "Session Files List", tester.test_11_8_session_files_list),
            ("11.9", "Session Tasks List", tester.test_11_9_session_tasks_list),
            ("11.10", "Session Workspace Get", tester.test_11_10_session_workspace_get),
            ("11.11", "Session Delete", tester.test_11_11_session_delete),
            ("11.12", "Session Hydrate", tester.test_11_12_session_hydrate),
            ("11.13", "Session Goal Get", tester.test_11_13_session_goal_get),
            ("11.14", "Session Goal Set", tester.test_11_14_session_goal_set),
            # ── 12.x Turn ──
            ("12.1", "Turn State Get No Active", tester.test_12_1_turn_state_get_no_active_turn),
            ("12.2", "Turn Start Error Without LLM", tester.test_12_2_turn_start_returns_error_without_llm),
            # ── 13.x Profile ──
            ("13.1", "Profile LLM List", tester.test_13_1_profile_llm_list),
            ("13.2", "Profile Skills List", tester.test_13_2_profile_skills_list),
            ("13.3", "Profile LLM Catalog", tester.test_13_3_profile_llm_catalog),
            ("13.4", "Onboarding Workspace Probe", tester.test_13_4_onboarding_workspace_probe),
            # ── 14.x Auth/Config ──
            ("14.1", "Auth Status", tester.test_14_1_auth_status_unauthenticated),
            ("14.2", "MCP Status List", tester.test_14_2_mcp_status_list),
            # ── 15.x Tool/Content ──
            ("15.1", "Tool Status List", tester.test_15_1_tool_status_list),
            ("15.2", "Content List", tester.test_15_2_content_list),
            # ── 16.x 通知 ──
            ("16.1", "Notification Session Opened", tester.test_16_1_notification_session_opened),
            ("16.2", "Notification Turn Started", tester.test_16_2_notification_turn_started),
            ("16.3", "Notification Turn Completed", tester.test_16_3_notification_turn_completed),
            ("16.4", "Notification Turn Error", tester.test_16_4_notification_turn_error),
            ("16.5", "Notification Agent Updated", tester.test_16_5_notification_agent_updated),
            # ── 17.x 错误路径 ──
            ("17.1", "Unknown Method Error", tester.test_17_1_unknown_method),
            ("17.2", "Missing Session ID", tester.test_17_2_missing_session_id),
            ("17.3", "Session Open Invalid", tester.test_17_3_session_open_invalid_format),
            ("17.4", "Turn State Unknown", tester.test_17_4_turn_state_unknown_turn),
            ("17.5", "JSON-RPC Missing Version", tester.test_17_5_jsonrpc_missing_version),
            # ── 18.x Approval / Permission / Diff ──
            ("18.1", "Approval Scopes List", tester.test_18_1_approval_scopes_list),
            ("18.2", "Permission Profile List", tester.test_18_2_permission_profile_list),
            ("18.3", "Permission Profile Set", tester.test_18_3_permission_profile_set),
            ("18.4", "Diff Preview Get", tester.test_18_4_diff_preview_get),
            ("18.5", "User Question Respond", tester.test_18_5_user_question_respond),
            # ── 19.x Task ──
            ("19.1", "Task List", tester.test_19_1_task_list),
            ("19.2", "Task Cancel", tester.test_19_2_task_cancel),
            ("19.3", "Task Restart From Node", tester.test_19_3_task_restart_from_node),
            ("19.4", "Task Output Read", tester.test_19_4_task_output_read),
            ("19.5", "Task Artifact List", tester.test_19_5_task_artifact_list),
            ("19.6", "Task Artifact Read", tester.test_19_6_task_artifact_read),
            # ── 20.x Agent ──
            ("20.1", "Agent List", tester.test_20_1_agent_list),
            ("20.2", "Agent Status Read", tester.test_20_2_agent_status_read),
            ("20.3", "Agent Output Read", tester.test_20_3_agent_output_read),
            ("20.4", "Agent Artifact List", tester.test_20_4_agent_artifact_list),
            ("20.5", "Agent Artifact Read", tester.test_20_5_agent_artifact_read),
            ("20.6", "Agent Interrupt", tester.test_20_6_agent_interrupt),
            ("20.7", "Agent Close", tester.test_20_7_agent_close),
            # ── 21.x Session Goal / Thread / Loop / Review ──
            ("21.1", "Session Goal Clear", tester.test_21_1_session_goal_clear),
            ("21.2", "Thread Graph Get", tester.test_21_2_thread_graph_get),
            ("21.3", "Session Status Read", tester.test_21_3_session_status_read),
            ("21.4", "Loop List", tester.test_21_4_loop_list),
            ("21.5", "Loop Create", tester.test_21_5_loop_create),
            ("21.6", "Review Start", tester.test_21_6_review_start),
            # ── 22.x Router / Content ──
            ("22.1", "Router Get Metrics", tester.test_22_1_router_get_metrics),
            ("22.2", "Router Set Mode", tester.test_22_2_router_set_mode),
            ("22.3", "Content Delete", tester.test_22_3_content_delete),
            ("22.4", "Content Bulk Delete", tester.test_22_4_content_bulk_delete),
            # ── 23.x Profile LLM / Skills ──
            ("23.1", "Profile LLM Select", tester.test_23_1_profile_llm_select),
            ("23.2", "Profile LLM Upsert", tester.test_23_2_profile_llm_upsert),
            ("23.3", "Profile LLM Delete", tester.test_23_3_profile_llm_delete),
            ("23.4", "Profile LLM Test", tester.test_23_4_profile_llm_test),
            ("23.5", "Profile LLM Fetch Models", tester.test_23_5_profile_llm_fetch_models),
            ("23.6", "Profile Skills Registry Search", tester.test_23_6_profile_skills_registry_search),
            ("23.7", "Profile Skills Install", tester.test_23_7_profile_skills_install),
            ("23.8", "Profile Skills Remove", tester.test_23_8_profile_skills_remove),
            # ── 24.x Auth ──
            ("24.1", "Auth Send Code", tester.test_24_1_auth_send_code),
            ("24.2", "Auth Logout", tester.test_24_2_auth_logout),
            ("24.3", "Profile LLM Select No Profile", tester.test_24_3_profile_llm_select_no_profile),
            # ── 8.12/8.13 Bind Address (会重启服务器，必须放在最后) ──
            ("8.12", "Bind Address (0.0.0.0)", tester.test_bind_address_external),
            ("8.13", "Default Bind (127.0.0.1)", tester.test_bind_address_local_default),
        ]

        # Filter tests if specific IDs provided
        if test_ids:
            tests_to_run = []
            for test_id in test_ids:
                # Support both numeric (8.1) and name (server_startup) formats
                matched = False
                for tid, tname, tfunc in all_tests:
                    if tid == test_id or tname.lower().replace(' ', '_') == test_id.lower():
                        tests_to_run.append((tid, tname, tfunc))
                        matched = True
                        break
                if not matched:
                    serve_logger.warning(f"Test not found: {test_id}")

            if not tests_to_run:
                serve_logger.error("No valid tests to run")
                if return_details:
                    return False, [f"Invalid test IDs: {', '.join(test_ids)}"], []
                return False, [f"Invalid test IDs: {', '.join(test_ids)}"]
        else:
            tests_to_run = all_tests

        # Run tests
        for test_id, test_name, test_func in tests_to_run:
            tester.run_test(test_id, test_name, test_func)

        # Generate and save report
        tester.save_report()
        tester.print_report_to_stdout()

        # Determine result
        all_passed = tester.failed == 0
        errors = [f"{r.test_id} {r.name}: {r.details}" for r in tester.results if r.status == "FAIL"]

        if all_passed:
            serve_logger.info("✅ All serve tests passed!")
        else:
            serve_logger.error(f"❌ {tester.failed} serve test(s) failed")

        # ── Stdio 传输模式测试 (30.x) ──
        serve_logger.info("")
        serve_logger.info("=" * 60)
        serve_logger.info("Running Stdio transport tests")
        serve_logger.info("=" * 60)

        from serve.test_serve import OctosStdioTester
        stdio_tester = OctosStdioTester(BINARY_PATH, LOG_DIR)
        if stdio_tester.start_server():
            stdio_tests = [
                ("30.1", "Stdio Connectivity", stdio_tester.test_30_1_stdio_connectivity),
                ("30.2", "Stdio Capabilities List", stdio_tester.test_30_2_stdio_capabilities),
                ("30.3", "Stdio System Status", stdio_tester.test_30_3_stdio_system_status),
                ("30.4", "Stdio Session List", stdio_tester.test_30_4_stdio_session_list),
                ("30.5", "Stdio Session Open", stdio_tester.test_30_5_stdio_session_open),
                ("30.6", "Stdio Auth Me", stdio_tester.test_30_6_stdio_auth_me),
            ]
            for test_id, test_name, test_func in stdio_tests:
                stdio_tester.run_test(test_id, test_name, test_func)
            stdio_tester.save_report()
            stdio_tester.print_report_to_stdout()
            stdio_failed = stdio_tester.failed
            stdio_errors = [
                f"{r.test_id} {r.name}: {r.details}"
                for r in stdio_tester.results if r.status == "FAIL"
            ]
        else:
            serve_logger.warning("Failed to start stdio server — skipping stdio tests")
            stdio_failed = 0
            stdio_errors = []

        all_passed = all_passed and stdio_failed == 0
        errors.extend(stdio_errors)

        if return_details:
            # Collect detailed results
            serve_details = [
                {
                    "test_id": r.test_id,
                    "name": r.name,
                    "status": r.status,
                    "details": r.details,
                    "duration_sec": r.duration_sec,
                }
                for r in tester.results
            ]
            stdio_details = [
                {
                    "test_id": r.test_id,
                    "name": r.name,
                    "status": r.status,
                    "details": r.details,
                    "duration_sec": r.duration_sec,
                }
                for r in stdio_tester.results
            ]
            return all_passed, errors, serve_details, stdio_details

        return all_passed, errors
        
    finally:
        # Cleanup
        tester.stop_server()


def parse_args():
    """Parse command line arguments."""
    # Manual parsing to handle complex nested arguments
    args = sys.argv[1:]
    
    if not args or '-h' in args or '--help' in args:
        return argparse.Namespace(
            command='help' if args else None,
            test_target=None,
            remaining=[]
        )
    
    command = args[0]
    
    if command == '--test':
        if len(args) < 2:
            return argparse.Namespace(
                command='--test',
                test_target=None,
                remaining=[]
            )
        
        test_target = args[1]
        remaining = args[2:]
        
        return argparse.Namespace(
            command='--test',
            test_target=test_target,
            remaining=remaining
        )
    
    # For 'all' command
    return argparse.Namespace(
        command=command,
        test_target=None,
        remaining=args[1:]
    )


def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    # Handle help - use print directly, no timestamp
    if args.command == 'help':
        print_help()
        return 0
    
    # No command provided - use print directly, no timestamp
    if args.command is None:
        print_help()
        return 0
    
    # Validate command
    valid_commands = ["all", "--test"]
    if args.command not in valid_commands:
        log.error(f"Unknown command: {args.command}")
        print_help()
        return 1
    
    # Handle --test command
    if args.command == "--test":
        test_target = args.test_target
        
        if not test_target:
            log.error("Missing test target. Use: --test bot/cli/serve/email/tui")
            print_help()
            return 1
        
        if test_target not in ["bot", "cli", "serve", "email", "tui"]:
            log.error(f"Unknown test target: {test_target}")
            print_help()
            return 1
        
        remaining = args.remaining
        
        # Handle bot tests
        if test_target == "bot":
            if not remaining:
                # Default: run all bot tests
                if not build_octos():
                    return 1
                prepare_test_environment()
                passed, _ = run_all_bot_tests()
                return 0 if passed else 1
            
            action = remaining[0]
            
            # Help for bot
            if action in ["-h", "--help"]:
                print_help()
                return 0
            
            # List modules
            if action in ["list", "ls"]:
                if len(remaining) > 1:
                    list_bot_cases(remaining[1])
                else:
                    list_bot_modules()
                return 0
            
            # Run specific module or all
            if action == "all":
                if not build_octos():
                    return 1
                prepare_test_environment()
                
                # Parse --from-test parameter for 'all' command
                from_test = None
                i = 0
                while i < len(remaining):
                    if remaining[i] == "--from-test" and i + 1 < len(remaining):
                        from_test = remaining[i + 1]
                        break
                    i += 1
                
                passed, _ = run_all_bot_tests(from_test=from_test)
                return 0 if passed else 1
            
            # Check if it's a valid module
            valid_modules = ["telegram", "tg", "discord", "dc", "matrix", "mx", "slack", "sl", "feishu", "fs", "wechat", "wx", "whatsapp", "wa", "line", "ln", "wecom-bot", "wecom_bot", "wcb", "wecom", "we", "qq-bot", "qq_bot", "qq", "twilio", "tw", "cross"]
            if action in valid_modules:
                # Special case: check for 'list' subcommand
                if len(remaining) > 1 and remaining[1] == "list":
                    list_bot_cases(action)
                    return 0

                if not build_octos():
                    return 1
                prepare_test_environment()
                
                # Parse --from-test parameter
                from_test = None
                test_case = None
                
                i = 1
                while i < len(remaining):
                    if remaining[i] == "--from-test" and i + 1 < len(remaining):
                        from_test = remaining[i + 1]
                        i += 2
                    elif test_case is None:
                        test_case = remaining[i]
                        i += 1
                    else:
                        i += 1
                
                # Use per-test retry for module runs (no specific test case)
                if test_case is None:
                    passed, _ = run_bot_test_with_per_test_retry(action, from_test=from_test)
                else:
                    passed, _, _ = run_bot_test(action, test_case)
                return 0 if passed else 1
            
            log.error(f"Unknown bot argument: {action}")
            print_help()
            return 1

        # Handle Email tests
        elif test_target == "email":
            if not remaining:
                # Default: run all email tests
                if not build_octos():
                    return 1
                prepare_test_environment()
                passed, _, _ = run_email_test()
                return 0 if passed else 1

            action = remaining[0]

            # Help for email
            if action in ["-h", "--help"]:
                print_help()
                return 0

            # Parse verbose flag
            verbose = "-v" in remaining or "--verbose" in remaining

            if not build_octos():
                return 1
            prepare_test_environment()
            passed, _, _ = run_email_test(test_case=action if action and not action.startswith('-') else None)
            return 0 if passed else 1

        # Handle CLI tests
        elif test_target == "cli":
            if not remaining:
                # Default: run CLI tests
                if not build_octos():
                    return 1
                prepare_test_environment()
                passed, _ = run_cli_tests()
                return 0 if passed else 1
            
            action = remaining[0]
            
            # Help for CLI
            if action in ["-h", "--help"]:
                print_help()
                return 0
            
            # List categories
            if action == "list":
                if len(remaining) > 1:
                    list_cli_category_cases(remaining[1])
                else:
                    list_cli_categories()
                return 0
            
            # Parse CLI options
            verbose = "-v" in remaining or "--verbose" in remaining
            output_dir = None
            scope = None
            
            for i, arg in enumerate(remaining):
                if arg in ["-o", "--output-dir"] and i + 1 < len(remaining):
                    output_dir = remaining[i + 1]
                elif arg in ["-s", "--scope"] and i + 1 < len(remaining):
                    scope = remaining[i + 1]
            
            if not build_octos():
                return 1
            prepare_test_environment()
            passed, _ = run_cli_tests(verbose, output_dir, scope)
            return 0 if passed else 1
        
        # Handle Serve tests
        elif test_target == "serve":
            if not remaining:
                # Default: run all serve tests
                if not build_octos():
                    return 1
                prepare_test_environment()
                passed, _ = run_serve_tests()
                return 0 if passed else 1
            
            action = remaining[0]
            
            # Help for serve
            if action in ["-h", "--help"]:
                print_help()
                return 0
            
            # List tests
            if action == "list":
                list_serve_tests()
                return 0
            
            # Parse options
            verbose = "-v" in remaining or "--verbose" in remaining
            
            # Collect test IDs (skip flags)
            test_ids = [arg for arg in remaining if not arg.startswith('-')]
            
            if not build_octos():
                return 1
            prepare_test_environment()
            passed, _ = run_serve_tests(verbose, test_ids if test_ids else None)
            return 0 if passed else 1

        # Handle TUI tests (sibling Rust crate `octos-tui`).
        elif test_target == "tui":
            # Lazy import to keep startup cheap when TUI tests aren't used.
            try:
                from tui_test.run_tui_tests import main as run_tui_main
            except ImportError as e:
                log.error(f"Cannot import tui_test module: {e}")
                log.error("Make sure tui_test/run_tui_tests.py exists.")
                return 1
            # Pass remaining args to tui subcommand.
            return run_tui_main(remaining)

    # Handle 'all' command
    if args.command == "all":
        # Check for invalid extra arguments
        if args.remaining:
            log.error(f"Invalid arguments for 'all' command: {' '.join(args.remaining)}")
            print("")
            print("The 'all' command runs all tests and does not accept additional arguments.")
            print("")
            print("Usage:")
            print("  test_run.py all                    # Run all tests")
            print("  test_run.py --test bot [args...]   # Run bot tests with options")
            print("  test_run.py --test cli [args...]   # Run CLI tests with options")
            print("  test_run.py --test serve [args...] # Run serve tests with options")
            print("")
            print_help()
            return 1
        
        # Use print instead of log for final report
        print("")
        print("=" * 70)
        print("🚀 Running ALL Test Suites (CLI + Bot + Serve)")
        print("=" * 70)
        print("")
        
        if not build_octos():
            return 1
        
        prepare_test_environment()

        test_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        report_output_dir = REPORT_DIR
        reporter = UnifiedTestReporter(BINARY_PATH, test_date, report_output_dir)

        cli_passed = serve_passed = bot_passed = False
        cli_errors = serve_errors = bot_errors = []
        cli_details = serve_details = stdio_details = bot_details = []

        # ── CLI 测试 ──
        try:
            cli_passed, cli_errors, cli_details = run_cli_tests(return_details=True, output_dir=str(TEST_DIR / "module_reports"))
            cli_total = len(cli_details)
            cli_pass_count = sum(1 for r in cli_details if r["status"] == "PASS")
            cli_fail_count = sum(1 for r in cli_details if r["status"] == "FAIL")
            reporter.add_module("cli", cli_details, passed=cli_pass_count,
                                failed=cli_fail_count, total=cli_total)
        except Exception as e:
            import traceback
            cli_errors = [f"CLI exception: {e}"]
            log.error(f"CLI tests failed with exception: {e}")
            log.error(traceback.format_exc())
            reporter.add_module("cli", [], passed=0, failed=0, total=0, error=str(e))

        # ── Serve + Stdio 测试 ──
        try:
            serve_passed, serve_errors, serve_details, stdio_details = run_serve_tests(return_details=True)
            serve_total = len(serve_details)
            serve_pass = sum(1 for r in serve_details if r["status"] == "PASS")
            serve_fail = sum(1 for r in serve_details if r["status"] == "FAIL")
            serve_skip = sum(1 for r in serve_details if r["status"] == "SKIP")
            reporter.add_module("serve", serve_details, passed=serve_pass,
                                failed=serve_fail, total=serve_total, skipped=serve_skip)

            stdio_total = len(stdio_details)
            stdio_pass = sum(1 for r in stdio_details if r["status"] == "PASS")
            stdio_fail = sum(1 for r in stdio_details if r["status"] == "FAIL")
            stdio_skip = sum(1 for r in stdio_details if r["status"] == "SKIP")
            reporter.add_module("stdio", stdio_details, passed=stdio_pass,
                                failed=stdio_fail, total=stdio_total, skipped=stdio_skip)
        except Exception as e:
            import traceback
            serve_errors = [f"Serve exception: {e}"]
            log.error(f"Serve tests failed with exception: {e}")
            log.error(traceback.format_exc())
            reporter.add_module("serve", [], passed=0, failed=0, total=0, error=str(e))
            reporter.add_module("stdio", [], passed=0, failed=0, total=0, error=str(e))

        # ── Bot 测试 ──
        try:
            bot_passed, bot_errors, bot_details = run_all_bot_tests(return_details=True)
            bot_total = len(bot_details)
            bot_pass = sum(1 for r in bot_details if r["status"] == "PASS")
            bot_fail = sum(1 for r in bot_details if r["status"] == "FAIL")
            reporter.add_module("bot", bot_details, passed=bot_pass,
                                failed=bot_fail, total=bot_total)
        except Exception as e:
            import traceback
            bot_errors = [f"Bot exception: {e}"]
            log.error(f"Bot tests failed with exception: {e}")
            log.error(traceback.format_exc())
            reporter.add_module("bot", [], passed=0, failed=0, total=0, error=str(e))

        # ── 保存报告 ──
        report_path = reporter.save_report()
        reporter.print_summary()

        # ── 额外的失败详情打印 ──
        has_errors = len(cli_errors) > 0 or len(serve_errors) > 0 or len(bot_errors) > 0
        if has_errors:
            print("=" * 70)
            print("❌ FAILED TESTS DETAILS")
            print("=" * 70)
            print("")

            for label, errors in [("CLI", cli_errors), ("Serve", serve_errors), ("Bot", bot_errors)]:
                if errors:
                    print(f"🔸 {label} Test Failures:")
                    for error in errors[:20]:  # Limit to 20 errors
                        print(f"   • {error}")
                    print("")

            print(f"📝 Total Failures: {len(cli_errors) + len(serve_errors) + len(bot_errors)}")
            print("")

        print("=" * 70)
        print(f"📁 Logs:      {LOG_DIR}")
        print(f"📄 Report:    {report_path}")
        print("=" * 70)
        print("")

        return 0 if (cli_passed and serve_passed and bot_passed) else 1
    
    return 1


if __name__ == "__main__":
    sys.exit(main())
