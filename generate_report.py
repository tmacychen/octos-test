#!/usr/bin/env python3
"""
Octos 测试报告生成器

功能：
  1. 扫描 /tmp/octos_test/logs/ 下的所有日志文件
  2. 解析各模块（CLI / Serve / Stdio / Bot）的测试结果
  3. 收集所有日志到报告输出目录
  4. 生成统一 Markdown + JSON 报告

用法：
  uv run python generate_report.py                          # 使用默认日志目录
  uv run python generate_report.py --log-dir /path/to/logs  # 指定日志目录
  uv run python generate_report.py --output-dir /path/to    # 指定输出目录
  uv run python generate_report.py --run-tests              # 运行测试后生成报告
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

LOG_DIR_DEFAULT = Path("/tmp/octos_test/logs")
REPORT_DIR_DEFAULT = Path(__file__).parent / "test-results"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [REPORT] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("report")


# ══════════════════════════════════════════════════════════════════════════════
# 日志解析器
# ══════════════════════════════════════════════════════════════════════════════


def parse_cli_logs(log_dir: Path) -> List[dict]:
    """解析 CLI 测试日志，提取每条测试的结果。

    CLI 模块会生成独立 JSON 报告。
    优先读取该 JSON，回退到日志解析。
    """
    # CLI 模块将报告写入 /tmp/test-results/
    for test_results_dir in [
        Path("/tmp/test-results"),
        log_dir.parent / "test-results",
    ]:
        if test_results_dir.exists():
            json_files = sorted(test_results_dir.glob("CLI_TEST_REPORT_*.json"))
            if json_files:
                try:
                    data = json.loads(json_files[-1].read_text())
                    if data.get("module") == "cli" and "results" in data:
                        for r in data["results"]:
                            if "category" not in r:
                                r["category"] = _infer_cli_category(
                                    r.get("test_id", ""), r.get("name", "")
                                )
                            if "details" not in r:
                                r["details"] = ""
                        logger.info(f"  从 CLI JSON 报告读取 {len(data['results'])} 条结果")
                        return data["results"]
                except Exception as e:
                    logger.warning(f"  读取 CLI JSON 报告失败: {e}")

    # 回退：从 01_runner_*.log 解析
    results = []
    seen = set()
    runner_logs = sorted(log_dir.glob("01_runner_*.log"))
    for log_file in runner_logs:
        content = log_file.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            # 匹配格式: "[CLI] INFO [SKIP] 2.24 provider minimax: Missing dependency..."
            m = re.search(
                r"\[CLI\]\s+INFO\s+\[SKIP\]\s+(\d+\.\d+)\s+(.+?):\s*(.+)",
                line,
            )
            if m:
                test_id = m.group(1)
                name = m.group(2).strip()
                details = m.group(3).strip()
                key = (test_id, name)
                if key not in seen:
                    seen.add(key)
                    results.append({
                        "test_id": test_id,
                        "name": name,
                        "status": "SKIP",
                        "details": details,
                        "category": _infer_cli_category(test_id, name),
                    })

    return results


def _infer_cli_category(test_id: str, name: str) -> str:
    """从 test_id 和 name 推断 CLI 测试分类。"""
    # 根据 test_id 的范围或 name 中的关键词推断
    id_num = float(test_id) if test_id.replace(".", "").isdigit() else 0

    category_map = [
        (1.0, 1.9, "CLI"),
        (2.0, 2.99, "Chat"),
        (3.0, 3.99, "Tools"),
        (4.0, 4.99, "Security"),
        (5.0, 5.9, "Init"),
        (6.0, 6.9, "Status"),
        (7.0, 7.9, "Clean"),
        (8.0, 8.99, "Completions"),
        (9.0, 9.99, "Skills"),
        (10.0, 10.99, "Auth"),
        (11.0, 11.99, "Channels"),
        (12.0, 12.99, "Cron"),
        (13.0, 13.99, "Gateway"),
        (14.0, 14.99, "Serve"),
        (15.0, 15.99, "Docs"),
        (16.0, 16.99, "Office"),
        (17.0, 17.99, "Account"),
        (18.0, 18.99, "Admin"),
        (19.0, 19.99, "Tools"),
        (20.0, 20.99, "Memory"),
        (21.0, 24.99, "Config"),
        (25.0, 25.99, "Loop"),
        (26.0, 26.99, "Security"),
        (27.0, 27.99, "Gateway"),
        (28.0, 28.99, "ToolPolicy"),
    ]
    for lo, hi, cat in category_map:
        if lo <= id_num <= hi:
            return cat
    return "Other"


def parse_serve_from_log(log_dir: Path) -> Tuple[List[dict], List[dict]]:
    """从 runner 日志中解析 Serve + Stdio 测试结果。

    Serve 日志格式（在 01_runner_*.log 中）:
      [SERVE] INFO [PASS 8.1] Server Startup
      [SERVE] INFO [FAIL 8.1] Server Startup
      [SERVE] INFO [SKIP 8.15] WS session/messages_page

    Stdio 日志格式（在 logs/stdio_test_*.log 中）:
      [PASS 30.5] Stdio Session Open
      [FAIL 30.1] Stdio Connectivity: RPC ...
    """
    serve_results = []
    stdio_results = []
    seen_serve = set()
    seen_stdio = set()

    # ── 解析 Serve 结果（从 01_runner_*.log） ──
    for log_file in sorted(log_dir.glob("01_runner_*.log")):
        content = log_file.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            m = re.search(
                r"\[SERVE\]\s+INFO\s+\[(PASS|FAIL|SKIP)\s+(\d+\.\d+)\]\s+(.+)",
                line,
            )
            if m:
                status = m.group(1)
                test_id = m.group(2)
                name = re.sub(r"^[✅⏭️❌]\s*", "", m.group(3)).strip()
                key = (test_id, name)
                if key not in seen_serve:
                    seen_serve.add(key)
                    serve_results.append({
                        "test_id": test_id,
                        "name": name,
                        "status": status,
                        "details": "",
                    })

    # ── 解析 Stdio 结果（从 logs/stdio_test_*.log） ──
    for log_file in sorted(log_dir.glob("**/stdio_test_*.log")):
        content = log_file.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            m = re.search(
                r"\[(PASS|FAIL|SKIP)\s+(\d+\.\d+)\]\s+(.+?)(?::\s*(.+))?$",
                line,
            )
            if m:
                status = m.group(1)
                test_id = m.group(2)
                name = re.sub(r"^[✅⏭️❌]\s*", "", m.group(3)).strip()
                details = (m.group(4) or "").strip()
                key = (test_id, name)
                if key not in seen_stdio:
                    seen_stdio.add(key)
                    stdio_results.append({
                        "test_id": test_id,
                        "name": name,
                        "status": status,
                        "details": details,
                    })

    return serve_results, stdio_results


def parse_bot_from_logs(log_dir: Path) -> List[dict]:
    """从 runner 日志中解析 Bot 测试结果。

    Bot 日志格式（在 01_runner_*.log 中）:
      [BOT_TG] INFO [PYTEST] bot_mock_test/test_telegram.py::TestClass::test_new_default
      [BOT_TG] INFO [PYTEST] PASSED [ 1%]
      [BOT_TG] INFO [PYTEST] bot_mock_test/test_telegram.py::TestClass::test_new_named
      [BOT_TG] INFO [PYTEST] FAILED [ 3%]

    pytest 摘要:
      [BOT_TG] INFO [PYTEST] 23 passed, 34 deselected in 406.51s (0:06:46)
    """
    results = []
    seen = set()

    for log_file in sorted(log_dir.glob("01_runner_*.log")):
        current_test_name = None
        current_channel = None

        for line in log_file.read_text(encoding="utf-8", errors="replace").splitlines():
            # 提取 channel
            ch_m = re.search(r"\[BOT_([A-Za-z0-9_-]+)\]", line)
            if ch_m:
                current_channel = ch_m.group(1).lower().replace("_", "-")

            # 捕获 test 名称行: "...::TestClass::test_new_default"
            tn_m = re.search(r"::\w+::(test_\w+)", line)
            if tn_m:
                current_test_name = tn_m.group(1)

            # 匹配 PASSED/FAILED（ANSI 转义序列中的 \x1b 不干扰）
            status_m = re.search(r"(PASSED|FAILED)", line)
            if status_m and current_test_name and current_channel:
                status = "PASS" if status_m.group(1) == "PASSED" else "FAIL"
                key = (current_channel, current_test_name)
                if key not in seen:
                    seen.add(key)
                    results.append({
                        "channel": current_channel,
                        "test_id": current_test_name,
                        "name": current_test_name,
                        "status": status,
                    })

    return results


def collect_all_logs(log_dir: Path, output_dir: Path) -> int:
    """收集所有日志文件到报告输出目录。

    Returns:
        复制的日志文件数量
    """
    log_output = output_dir / "logs"
    log_output.mkdir(parents=True, exist_ok=True)

    count = 0
    for log_file in sorted(log_dir.glob("*.log")):
        try:
            shutil.copy2(log_file, log_output / log_file.name)
            count += 1
        except (shutil.Error, OSError) as e:
            logger.warning(f"  复制日志失败: {log_file.name}: {e}")

    # 同时也复制子目录中的日志
    for sub_dir in log_dir.iterdir():
        if sub_dir.is_dir():
            for log_file in sub_dir.glob("*.log"):
                rel_path = log_file.relative_to(log_dir)
                target = log_output / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(log_file, target)
                    count += 1
                except (shutil.Error, OSError) as e:
                    logger.warning(f"  复制日志失败: {rel_path}: {e}")

    return count


def get_module_serve_results(log_dir: Path) -> Optional[dict]:
    """从 Serve 的独立报告 JSON 中读取结果。"""
    serve_report = log_dir.parent / "module_reports" / "serve"
    if serve_report.exists():
        json_files = list(serve_report.glob("*.json"))
        if json_files:
            try:
                data = json.loads(json_files[0].read_text())
                return data
            except Exception:
                pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# 报告生成器
# ══════════════════════════════════════════════════════════════════════════════


class OctosReportGenerator:
    """统一报告生成器 —— 从日志文件解析结果并生成报告。"""

    def __init__(
        self,
        log_dir: Path,
        output_dir: Path,
    ):
        self.log_dir = log_dir
        self.output_dir = output_dir
        self.modules: Dict[str, dict] = {}
        self.binary_path = self._find_binary()

    def _find_binary(self) -> str:
        """尝试从日志中获取二进制路径。"""
        for log_file in sorted(self.log_dir.glob("01_runner_*.log")):
            content = log_file.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"Using existing octos binary: (.+)", content)
            if m:
                return m.group(1).strip()
        return "unknown"

    def _get_octos_version(self) -> str:
        """从 octos 二进制获取版本信息。"""
        binary = self._find_binary()
        if binary and binary != "unknown":
            try:
                result = subprocess.run(
                    [binary, "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception:
                pass
        return "unknown"

    def _get_test_date(self) -> str:
        """从日志文件时间戳推断测试日期。"""
        log_files = list(self.log_dir.glob("01_runner_*.log"))
        if log_files:
            # 使用最早日志文件的 mtime
            earliest = min(log_files, key=lambda p: p.stat().st_mtime)
            dt = datetime.fromtimestamp(earliest.stat().st_mtime)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def add_module(
        self,
        name: str,
        results: List[dict],
        error: str = "",
    ):
        """添加一个模块的测试结果。"""
        total = len(results)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = sum(1 for r in results if r["status"] == "FAIL")
        skipped = sum(1 for r in results if r["status"] == "SKIP")
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
        logger.info(
            f"  [{name}] {passed}/{total} passed ({pass_rate}%), "
            f"{failed} failed, {skipped} skipped"
        )

    def generate_markdown(self) -> str:
        """生成完整 Markdown 报告。

        结构：
          1. 报告头（版本、日期、总体摘要）
          2. 各模块详细结果
          3. 失败测试详情
          4. 覆盖矩阵
        """
        summary = self._get_overall_summary()
        version = self._get_octos_version()
        lines = []
        lines.append("# Octos 统一测试报告\n")

        # ── 0. 报告头 ──
        lines.append("| 项目 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| **Octos 版本** | `{version}` |")
        lines.append(f"| **测试日期** | {self._get_test_date()} |")
        lines.append(f"| **报告生成** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |")
        lines.append(f"| **日志目录** | `{self.log_dir}` |")
        lines.append("")

        # ── 1. 总体摘要 ──
        lines.append("---\n")
        lines.append("## 1. 总体摘要\n")
        lines.append(
            f"> **总计 {summary['total']} 个测试，"
            f"通过 {summary['passed']}，"
            f"失败 {summary['failed']}，"
            f"跳过 {summary['skipped']}，"
            f"通过率 {summary['passed_pct']}%**\n"
        )

        overall_ok = summary["failed"] == 0
        status_text = "✅ 全部通过" if overall_ok else "❌ 部分失败"
        lines.append(f"> **状态**: {status_text}\n")
        lines.append("")

        lines.append("| 模块 | 总计 | 通过 | 失败 | 跳过 | 通过率 | 评估 |")
        lines.append("|------|------|------|------|------|--------|------|")
        for name, mod in sorted(self.modules.items()):
            if mod["passed_pct"] >= 95:
                rating = "🟢 良好"
            elif mod["passed_pct"] >= 80:
                rating = "🟡 一般"
            elif mod["passed_pct"] >= 50:
                rating = "🟠 不足"
            else:
                rating = "🔴 严重不足"
            status_icon = "✅" if mod["failed"] == 0 else "❌"
            err_suffix = f" ({mod['error'][:40]})" if mod['error'] else ""
            lines.append(
                f"| {name} | {mod['total']} | {mod['passed']} | "
                f"{mod['failed']} | {mod['skipped']} | {mod['passed_pct']}% | "
                f"{status_icon} {rating}{err_suffix} |"
            )
        lines.append(
            f"| **总计** | **{summary['total']}** | **{summary['passed']}** | "
            f"**{summary['failed']}** | **{summary['skipped']}** | "
            f"**{summary['passed_pct']}%** | **{status_text}** |"
        )
        lines.append("")

        # 失败概要
        failed_mods = [(n, m) for n, m in sorted(self.modules.items()) if m["failed"] > 0]
        if failed_mods:
            lines.append("**失败模块**:\n")
            for name, mod in failed_mods:
                failed_names = [
                    r.get("name", r.get("test_id", "?"))
                    for r in mod["results"] if r.get("status") == "FAIL"
                ]
                lines.append(f"- **{name}**: {mod['failed']} 个失败")
                for fn in failed_names[:5]:
                    lines.append(f"  - `{fn}`")
                if len(failed_names) > 5:
                    lines.append(f"  - ... 及其他 {len(failed_names) - 5} 个")
            lines.append("")

        # ── 2. 各模块详细结果 ──
        lines.append("---\n")
        lines.append("## 2. 各模块详细结果\n")

        module_display = {
            "cli": "2.1 CLI 测试",
            "serve": "2.2 Serve 测试",
            "stdio": "2.3 Stdio 传输测试",
            "bot": "2.4 Bot 测试",
        }

        for name, mod in sorted(self.modules.items()):
            display = module_display.get(name, name)
            lines.append(f"### {display}\n")
            lines.append(
                f"**总计**: {mod['total']} | **通过**: {mod['passed']} | "
                f"**失败**: {mod['failed']} | **跳过**: {mod['skipped']} | "
                f"**通过率**: {mod['passed_pct']}%\n"
            )

            if not mod["results"]:
                lines.append("*无测试用例数据*\n")
                continue

            if name == "bot":
                # Bot 按通道分组
                channels = {}
                for r in mod["results"]:
                    ch = r.get("channel", "unknown")
                    channels.setdefault(ch, []).append(r)
                lines.append("| 通道 | 通过 | 失败 | 总计 | 通过率 | 状态 |")
                lines.append("|------|------|------|------|--------|------|")
                for ch, res_list in sorted(channels.items()):
                    ch_pass = sum(1 for r in res_list if r["status"] == "PASS")
                    ch_fail = sum(1 for r in res_list if r["status"] == "FAIL")
                    ch_total = len(res_list)
                    ch_rate = round(ch_pass * 100 / ch_total, 1) if ch_total > 0 else 0
                    ch_icon = "✅" if ch_fail == 0 else "❌"
                    lines.append(
                        f"| {ch} | {ch_pass} | {ch_fail} | {ch_total} | "
                        f"{ch_rate}% | {ch_icon} |"
                    )
                lines.append("")

                # 每个通道的详细信息
                for ch, res_list in sorted(channels.items()):
                    failures = [r for r in res_list if r["status"] == "FAIL"]
                    if failures:
                        lines.append(f"**{ch} 失败详情**:\n")
                        for r in failures:
                            lines.append(f"- `{r['test_id']}`: {r.get('details', r['name'])}")
                        lines.append("")
            else:
                # 普通模块：展示详细表格
                sample = mod["results"][0]
                has_category = "category" in sample
                has_duration = sample.get("duration_sec", 0) > 0

                if has_category:
                    lines.append("| 编号 | 分类 | 名称 | 状态 |")
                    lines.append("|------|------|------|------|")
                    for r in mod["results"]:
                        lines.append(
                            f"| {r['test_id']} | {r.get('category', '-')} | "
                            f"{r['name']} | {r['status']} |"
                        )
                else:
                    lines.append("| 编号 | 名称 | 状态 |")
                    lines.append("|------|------|------|")
                    for r in mod["results"]:
                        lines.append(
                            f"| {r['test_id']} | {r['name']} | {r['status']} |"
                        )
                lines.append("")

        # ── 3. 失败测试详情 ──
        lines.append("---\n")
        lines.append("## 3. 失败测试详情\n")
        any_failures = any(mod["failed"] > 0 for mod in self.modules.values())
        if any_failures:
            for name, mod in sorted(self.modules.items()):
                if mod["error"]:
                    lines.append(f"### {name} 模块错误\n")
                    lines.append(f"```\n{mod['error']}\n```\n")
                failed_r = [r for r in mod["results"] if r.get("status") == "FAIL"]
                if failed_r:
                    lines.append(f"### {name} 测试失败\n")
                    for r in failed_r:
                        tid = r.get("test_id", "?")
                        rname = r.get("name", "?")
                        details = r.get("details", "")
                        if details:
                            lines.append(f"- **[{tid}] {rname}**: {details}")
                        else:
                            lines.append(f"- **[{tid}] {rname}**")
                    lines.append("")
        else:
            lines.append("*无失败测试 🎉*\n")

        # ── 4. 覆盖矩阵 ──
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
            elif mod["passed_pct"] >= 50:
                rating = "🟠 不足"
            else:
                rating = "🔴 严重不足"
            lines.append(
                f"| {name} | {mod['total']} | {mod['passed_pct']}% | {rating} |"
            )
        lines.append("")

        # ── Footer ──
        lines.append("---\n")
        lines.append(f"*日志收集路径: `{self.output_dir}/logs/`*\n")
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
            "generator": "generate_report.py",
            "octos_version": self._get_octos_version(),
            "test_date": self._get_test_date(),
            "binary_path": self.binary_path,
            "log_dir": str(self.log_dir),
            "summary": summary,
            "modules": modules_data,
        }

    def _get_overall_summary(self) -> dict:
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

    def save_report(self) -> Path:
        """保存 .md + .json 报告并收集日志，返回 .md 路径。"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        md_path = self.output_dir / f"OCTOS_TEST_REPORT_{ts}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self.generate_markdown())
        logger.info(f"📄 报告已保存: {md_path}")

        json_path = self.output_dir / f"OCTOS_TEST_REPORT_{ts}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.generate_json(), f, ensure_ascii=False, indent=2)
        logger.info(f"📄 JSON 已保存: {json_path}")

        # 收集所有日志
        log_count = collect_all_logs(self.log_dir, self.output_dir)
        logger.info(f"📁 日志已收集: {log_count} 个文件 → `{self.output_dir}/logs/`")

        return md_path

    def print_summary(self):
        """打印终端摘要。"""
        summary = self._get_overall_summary()
        version = self._get_octos_version()
        print("")
        print("=" * 70)
        print("📊 OCTOS UNIFIED TEST REPORT")
        print("=" * 70)
        print(f"   Octos: {version}")
        print(f"   Date:  {self._get_test_date()}")
        print("")
        for name, mod in sorted(self.modules.items()):
            icon = "✅" if mod["failed"] == 0 else "❌"
            err = f" ({mod['error'][:60]})" if mod["error"] else ""
            print(f"   • {name:<10}: {icon}  {mod['passed']}/{mod['total']} passed{err}")
        print("")
        overall_ok = summary["failed"] == 0
        overall_icon = "✅ ALL PASSED" if overall_ok else "❌ SOME FAILED"
        print(f"🎯 Overall: {overall_icon}")
        print(
            f"   Total: {summary['total']}, Passed: {summary['passed']}, "
            f"Failed: {summary['failed']}, Pass Rate: {summary['passed_pct']}%"
        )
        print("")


# ══════════════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════════════


def run_tests_and_report():
    """运行所有测试并自动生成报告。"""
    from test_run import (
        build_octos,
        prepare_test_environment,
        run_cli_tests,
        run_serve_tests,
        run_bot_test,
    )

    logger.info("=" * 60)
    logger.info("🚀 开始运行完整测试套件")
    logger.info("=" * 60)

    if not build_octos():
        logger.error("构建 octos 二进制失败")
        sys.exit(1)

    prepare_test_environment()
    test_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_dir = REPORT_DIR_DEFAULT

    all_passed = True

    # ── CLI 测试 ──
    logger.info("")
    logger.info("─" * 40)
    logger.info("📋 运行 CLI 测试")
    logger.info("─" * 40)
    try:
        cli_passed, cli_errors, cli_details = run_cli_tests(
            return_details=True,
            output_dir=str(Path("/tmp/octos_test") / "module_reports"),
        )
        if not cli_passed:
            all_passed = False
            logger.error(f"❌ CLI 测试失败: {cli_errors}")
    except Exception as e:
        all_passed = False
        logger.error(f"❌ CLI 测试异常: {e}")
        import traceback
        traceback.print_exc()

    # ── Serve + Stdio 测试 ──
    logger.info("")
    logger.info("─" * 40)
    logger.info("🔌 运行 Serve 测试")
    logger.info("─" * 40)
    try:
        serve_passed, serve_errors, serve_details, stdio_details = run_serve_tests(
            return_details=True
        )
        if not serve_passed:
            all_passed = False
            logger.error(f"❌ Serve 测试失败: {serve_errors}")
    except Exception as e:
        all_passed = False
        logger.error(f"❌ Serve 测试异常: {e}")

    # ── Bot Telegram 测试 ──
    logger.info("")
    logger.info("─" * 40)
    logger.info("🤖 运行 Telegram Bot 测试")
    logger.info("─" * 40)
    try:
        bot_passed, bot_failed, bot_passed_tests = run_bot_test("telegram")
        if not bot_passed:
            all_passed = False
            logger.error(f"❌ Telegram Bot 测试失败: {bot_failed}")
    except Exception as e:
        all_passed = False
        logger.error(f"❌ Telegram Bot 测试异常: {e}")

    # ── 生成报告 ──
    logger.info("")
    logger.info("─" * 40)
    logger.info("📊 生成统一报告")
    logger.info("─" * 40)

    reporter = OctosReportGenerator(
        log_dir=LOG_DIR_DEFAULT,
        output_dir=output_dir,
    )

    # 添加 CLI 结果
    try:
        reporter.add_module("cli", cli_details)
    except NameError:
        pass

    # 添加 Serve 结果
    try:
        reporter.add_module("serve", serve_details)
        reporter.add_module("stdio", stdio_details)
    except NameError:
        pass

    # 添加 Bot 结果（从日志解析）
    bot_results = parse_bot_from_logs(LOG_DIR_DEFAULT)
    if bot_results:
        reporter.add_module("bot", bot_results)

    report_path = reporter.save_report()
    reporter.print_summary()

    print("")
    print(f"📄 完整报告: {report_path}")
    print(f"📁 日志归档: {output_dir / 'logs'}")
    print("")

    return 0 if all_passed else 1


def main():
    parser = argparse.ArgumentParser(
        description="Octos 测试报告生成器 — 从日志解析测试结果并生成统一报告",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=str(LOG_DIR_DEFAULT),
        help="日志目录路径 (默认: /tmp/octos_test/logs)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(REPORT_DIR_DEFAULT),
        help="报告输出目录 (默认: test-results/)",
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="运行所有测试后生成报告",
    )

    args = parser.parse_args()

    if args.run_tests:
        sys.exit(run_tests_and_report())

    # 从日志生成报告
    log_dir = Path(args.log_dir)
    output_dir = Path(args.output_dir)

    if not log_dir.exists():
        logger.error(f"日志目录不存在: {log_dir}")
        logger.error("请先运行测试: uv run python test_run.py --test cli")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("📊 从日志生成测试报告")
    logger.info(f"   日志目录: {log_dir}")
    logger.info(f"   输出目录: {output_dir}")
    logger.info("=" * 60)

    reporter = OctosReportGenerator(log_dir=log_dir, output_dir=output_dir)

    # 解析 CLI 结果
    cli_results = parse_cli_logs(log_dir)
    logger.info(f"📋 CLI: 解析到 {len(cli_results)} 条结果")
    if cli_results:
        reporter.add_module("cli", cli_results)

    # 解析 Serve 结果
    serve_results, stdio_results = parse_serve_from_log(log_dir)
    logger.info(f"🔌 Serve: 解析到 {len(serve_results)} 条结果")
    logger.info(f"🔌 Stdio: 解析到 {len(stdio_results)} 条结果")
    if serve_results:
        reporter.add_module("serve", serve_results)
    if stdio_results:
        reporter.add_module("stdio", stdio_results)

    # 解析 Bot 结果
    bot_results = parse_bot_from_logs(log_dir)
    logger.info(f"🤖 Bot: 解析到 {len(bot_results)} 条结果")
    if bot_results:
        reporter.add_module("bot", bot_results)

    if not reporter.modules:
        logger.warning("未解析到任何测试结果")
        logger.warning("请确认日志目录包含有效的测试日志文件")
        sys.exit(1)

    report_path = reporter.save_report()
    reporter.print_summary()

    print("")
    print(f"📄 完整报告: {report_path}")
    print(f"📁 日志归档: {output_dir / 'logs'}")
    print("")


if __name__ == "__main__":
    main()
