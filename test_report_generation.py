#!/usr/bin/env python3
"""
测试报告生成综合测试

验证 UnifiedTestReporter 和所有模块的报告生成功能：
1. UnifiedTestReporter — Markdown/JSON 格式、内容正确性、异常安全
2. CLI 模块报告 — duration 字段、JSON 序列化
3. Serve 模块报告 — 同上
4. 端到端集成 — cmd_all 路径
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# ── 添加项目根到路径 ──
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

PASS = 0
FAIL = 0


def check(condition: bool, message: str):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {message}")
    else:
        FAIL += 1
        print(f"  ❌ {message}")


def test_01_unified_reporter_mock_data():
    """测试 1：UnifiedTestReporter 使用 mock 数据生成报告"""
    print("\n" + "=" * 60)
    print("测试 1: UnifiedTestReporter Mock 数据验证")
    print("=" * 60)

    from test_run import UnifiedTestReporter

    reporter = UnifiedTestReporter(
        binary_path="/test/octos",
        test_date="2026-06-19 12:00:00",
        output_dir=Path("/tmp/test_report_test"),
    )

    # ── CLI 模块数据 ──
    cli_results = [
        {"test_id": "5.1", "category": "Init", "name": "init defaults",
         "status": "PASS", "duration_sec": 0.02, "details": ""},
        {"test_id": "6.1", "category": "Status", "name": "status check",
         "status": "FAIL", "duration_sec": 0.01, "details": "TOOLS.md missing"},
        {"test_id": "1.1", "category": "CLI", "name": "--help",
         "status": "PASS", "duration_sec": 0.05, "details": ""},
    ]
    reporter.add_module("cli", cli_results, passed=2, failed=1, total=3)

    # ── Serve 模块数据 ──
    serve_results = [
        {"test_id": "8.1", "name": "Server Startup",
         "status": "PASS", "duration_sec": 0.5, "details": ""},
        {"test_id": "8.4", "name": "Auth Token Required",
         "status": "PASS", "duration_sec": 0.1, "details": ""},
        {"test_id": "8.10", "name": "WS session/open + turn/start",
         "status": "SKIP", "duration_sec": 0.0, "details": "No API key"},
    ]
    reporter.add_module("serve", serve_results, passed=2, failed=0, total=3, skipped=1)

    # ── Stdio 模块数据 ──
    stdio_results = [
        {"test_id": "30.1", "name": "Stdio Connectivity",
         "status": "PASS", "duration_sec": 0.3, "details": ""},
    ]
    reporter.add_module("stdio", stdio_results, passed=1, failed=0, total=1)

    # ── Bot 模块数据（带 channel 分组）──
    bot_results = [
        {"name": "test_basic_hello", "status": "PASS", "channel": "telegram"},
        {"name": "test_echo", "status": "PASS", "channel": "telegram"},
        {"name": "test_long_message", "status": "FAIL", "channel": "telegram",
         "details": "Timeout"},
        {"name": "test_discord_connect", "status": "PASS", "channel": "discord"},
        {"name": "test_discord_send", "status": "PASS", "channel": "discord"},
    ]
    reporter.add_module("bot", bot_results, passed=4, failed=1, total=5)

    # ── 生成 Markdown ──
    md = reporter.generate_markdown()

    # 验证报告结构
    check("# Octos 统一测试报告" in md, "报告标题正确")
    check("2026-06-19 12:00:00" in md, "测试日期正确")
    check("/test/octos" in md, "二进制路径正确")
    check("## 1. 总体结果" in md, "总体结果章节存在")
    check("| cli" in md, "CLI 模块在总体表格中")
    check("| serve" in md, "Serve 模块在总体表格中")
    check("| stdio" in md, "Stdio 模块在总体表格中")
    check("| bot" in md, "Bot 模块在总体表格中")
    check("## 2. 各模块详细结果" in md, "详细结果章节存在")
    check("2.1 CLI 测试" in md, "CLI 详细结果章节")
    check("2.2 Serve 测试" in md, "Serve 详细结果章节")
    check("2.3 Stdio 测试" in md, "Stdio 详细结果章节")
    check("2.4 Bot 测试" in md, "Bot 详细结果章节")

    # 验证 duration 显示
    check("0.02s" in md, "CLI duration 显示正确")
    check("0.50s" in md, "Serve duration 显示正确")

    # 验证失败测试详情
    check("## 3. 失败测试详情" in md, "失败测试详情章节存在")
    check("TOOLS.md missing" in md, "失败详情内容正确")
    check("[6.1] status check" in md, "失败测试编号正确")

    # 验证覆盖矩阵
    check("## 4. 功能覆盖矩阵" in md, "覆盖矩阵章节存在")

    # 验证 Bot 分组
    check("| telegram" in md, "Telegram 通道分组显示")
    check("| discord" in md, "Discord 通道分组显示")

    # ── 生成 JSON ──
    js = reporter.generate_json()

    check("report_type" in js, "JSON 有 report_type 字段")
    check(js["report_type"] == "octos_unified_test_report", "report_type 值正确")
    check("summary" in js, "JSON 有 summary 字段")
    check(js["summary"]["total"] == 12, f"JSON total=12, 实际={js['summary']['total']}")
    check(js["summary"]["passed"] == 9, f"JSON passed=9, 实际={js['summary']['passed']}")
    check(js["summary"]["failed"] == 2, f"JSON failed=2, 实际={js['summary']['failed']}")
    check("modules" in js, "JSON 有 modules 字段")
    check(len(js["modules"]) == 4, f"JSON 4 个模块, 实际={len(js['modules'])}")
    check("cli" in js["modules"], "JSON 包含 cli 模块")
    check("serve" in js["modules"], "JSON 包含 serve 模块")
    check("bot" in js["modules"], "JSON 包含 bot 模块")

    # 验证 duration 在 JSON 中
    for r in js["modules"]["cli"]["results"]:
        check("duration_sec" in r, f"CLI {r['test_id']} 有 duration_sec 字段")

    # ── 保存报告 ──
    md_path = reporter.save_report()
    check(md_path.exists(), f"MD 报告文件已生成: {md_path.name}")
    json_path = md_path.with_suffix(".json")
    check(json_path.exists(), f"JSON 报告文件已生成: {json_path.name}")

    # 验证 JSON 文件内容
    with open(json_path) as f:
        saved_json = json.load(f)
    check(saved_json["summary"]["total"] == 12, "保存的 JSON 内容正确")

    # 清理
    md_path.unlink(missing_ok=True)
    json_path.unlink(missing_ok=True)


def test_02_exception_safety():
    """测试 2：异常安全 —— 模块异常时报告仍能生成"""
    print("\n" + "=" * 60)
    print("测试 2: 异常安全验证")
    print("=" * 60)

    from test_run import UnifiedTestReporter

    reporter = UnifiedTestReporter(
        binary_path="/test/octos",
        test_date="2026-06-19 12:00:00",
        output_dir=Path("/tmp/test_report_test"),
    )

    # 正常模块
    reporter.add_module("cli", [], passed=0, failed=0, total=0)

    # 异常模块（模拟模块崩溃）
    reporter.add_module("serve", [], passed=0, failed=0, total=0,
                        error="Connection refused: Failed to start server")

    # 另一个正常模块
    reporter.add_module("bot", [], passed=0, failed=0, total=0)

    md = reporter.generate_markdown()
    js = reporter.generate_json()

    # 验证异常模块在报告中可识别
    check("Connection refused" in md, "异常信息在 Markdown 中显示")
    check("serve" in js["modules"], "异常模块在 JSON 中")
    check(js["modules"]["serve"]["error"] == "Connection refused: Failed to start server",
          "JSON 中异常信息正确")

    # 验证即使有异常，整体报告仍生成
    check(md.startswith("# Octos 统一测试报告"), "异常情况下报告标题正常")


def test_03_empty_modules():
    """测试 3：空模块边界情况"""
    print("\n" + "=" * 60)
    print("测试 3: 空模块边界情况")
    print("=" * 60)

    from test_run import UnifiedTestReporter

    reporter = UnifiedTestReporter(
        binary_path="/test/octos",
        test_date="2026-06-19 12:00:00",
        output_dir=Path("/tmp/test_report_test"),
    )

    # 空数据（没有任何模块）
    md = reporter.generate_markdown()
    js = reporter.generate_json()

    check(md.startswith("# Octos 统一测试报告"), "空模块时也能生成报告")
    check(js["summary"]["total"] == 0, "空模块时 total=0")
    check(js["summary"]["passed"] == 0, "空模块时 passed=0")


def test_04_cli_report_format():
    """测试 4：CLI 模块报告格式验证（直接调用模块代码）"""
    print("\n" + "=" * 60)
    print("测试 4: CLI 模块报告格式验证")
    print("=" * 60)

    from cli_test.test_cli import CLITestResult

    r1 = CLITestResult("5.1", "Init", "init defaults", "PASS", duration_sec=0.02)
    r2 = CLITestResult("6.1", "Status", "status check", "FAIL", duration_sec=0.01)

    # 验证 to_markdown_row
    md_row = r1.to_markdown_row()
    check("| 5.1 | Init | init defaults | PASS | 0.02s |" == md_row,
          f"CLI markdown 行格式正确: {md_row}")

    md_row2 = r2.to_markdown_row()
    check("FAIL" in md_row2 and "0.01s" in md_row2, "CLI 失败行包含状态和耗时")

    # 验证 to_dict
    d1 = r1.to_dict()
    check(d1["test_id"] == "5.1", "to_dict test_id 正确")
    check(d1["status"] == "PASS", "to_dict status 正确")
    check(d1["duration_sec"] == 0.02, "to_dict duration_sec 正确")

    # 验证 JSON 序列化完整性
    json_str = json.dumps(d1)
    check('"duration_sec"' in json_str, "JSON 序列化包含 duration_sec")


def test_05_serve_report_format():
    """测试 5：Serve 模块报告格式验证（直接调用模块代码）"""
    print("\n" + "=" * 60)
    print("测试 5: Serve 模块报告格式验证")
    print("=" * 60)

    from serve.test_serve import ServeTestResult

    r1 = ServeTestResult("8.1", "Server Startup", "PASS", duration_sec=0.5)
    r2 = ServeTestResult("8.10", "WS session/open", "SKIP",
                          details="No API key", duration_sec=0.0)

    # 验证 to_markdown_row
    md_row = r1.to_markdown_row()
    check("| 8.1 | Server Startup | PASS | 0.50s |" in md_row,
          f"Serve markdown 行格式正确: {md_row}")

    # 验证 SKIP 状态保留
    check("SKIP" in r2.to_markdown_row(), "SKIP 状态正确显示")

    # 验证 to_dict
    d1 = r1.to_dict()
    check(d1["test_id"] == "8.1", "to_dict test_id 正确")
    check(d1["duration_sec"] == 0.5, "to_dict duration_sec 正确")

    d2 = r2.to_dict()
    check(d2["status"] == "SKIP", "SKIP 状态在 to_dict 中")
    check(d2["details"] == "No API key", "SKIP 原因在 details 中")

    # 验证 JSON 序列化
    json_str = json.dumps(d1)
    check('"duration_sec"' in json_str, "JSON 序列化包含 duration_sec")


def test_06_unified_reporter_total_duration():
    """测试 6：UnifiedTestReporter 增加总耗时字段"""
    print("\n" + "=" * 60)
    print("测试 6: 报告总耗时")
    print("=" * 60)

    from test_run import UnifiedTestReporter

    reporter = UnifiedTestReporter(
        binary_path="/test/octos",
        test_date="2026-06-19 12:00:00",
        output_dir=Path("/tmp/test_report_test"),
    )

    results = [
        {"test_id": "1.1", "name": "test1", "status": "PASS", "duration_sec": 1.5},
        {"test_id": "1.2", "name": "test2", "status": "PASS", "duration_sec": 2.3},
    ]
    reporter.add_module("cli", results, passed=2, failed=0, total=2)

    md = reporter.generate_markdown()
    js = reporter.generate_json()

    # JSON 中是否包含总耗时
    check("summary" in js, "JSON 有 summary")

    # Markdown 中验证 duration 显示
    check("1.50s" in md, "1.5s 显示为 1.50s")
    check("2.30s" in md, "2.3s 显示为 2.30s")


def test_07_cmd_all_integration():
    """测试 7：cmd_all 集成测试（运行真实 CLI + Serve 模块）"""
    print("\n" + "=" * 60)
    print("测试 7: cmd_all 集成测试")
    print("=" * 60)

    OCTOS_BINARY = os.environ.get("OCTOS_BINARY", "")
    if not OCTOS_BINARY or not Path(OCTOS_BINARY).exists():
        print("  ⚠️  跳过: 未设置 OCTOS_BINARY")
        return

    from test_run import run_serve_tests, run_cli_tests, BINARY_PATH, LOG_DIR

    # 临时修改输出目录
    test_output = Path("/tmp/test_report_integration")
    test_output.mkdir(parents=True, exist_ok=True)

    # ── CLI 测试（限定 Init 分类）──
    print("\n  ── CLI 测试 (Init) ──")
    try:
        all_passed, errors = run_cli_tests(
            binary_path=BINARY_PATH,
            log_dir=LOG_DIR,
            categories=["Init"],
            output_dir=test_output,
        )
        check(all_passed, f"CLI Init 测试通过 (total={'(from log)'})")
        check(len(errors) == 0, f"CLI 无错误 (errors={len(errors)})")
    except Exception as e:
        check(False, f"CLI 测试异常: {e}")

    # ── CLI 测试（限定 Status 分类）──
    print("\n  ── CLI 测试 (Status) ──")
    try:
        all_passed, errors = run_cli_tests(
            binary_path=BINARY_PATH,
            log_dir=LOG_DIR,
            categories=["Status"],
            output_dir=test_output,
        )
        # Status 测试预期会有失败（文件缺失），验证框架仍能正常报告
        check(not all_passed, "CLI Status 预期失败（文件缺失）")
        check(len(errors) > 0, "CLI Status 有错误输出")
    except Exception as e:
        check(False, f"CLI Status 测试异常: {e}")

    # ── Serve 测试（仅 8.1）──
    print("\n  ── Serve 测试 (8.1) ──")
    try:
        serve_passed, serve_errors = run_serve_tests(
            verbose=False, test_ids=["8.1"]
        )
        check(serve_passed, "Serve 8.1 健康检查通过")
        check(len(serve_errors) == 0, f"Serve 无错误 (errors={serve_errors})")
    except Exception as e:
        check(False, f"Serve 8.1 测试异常: {e}")

    # ── 验证生成的报告 ──
    print("\n  ── 验证报告文件 ──")
    cli_reports = list(test_output.glob("CLI_TEST_REPORT_*.md"))
    cli_jsons = list(test_output.glob("CLI_TEST_REPORT_*.json"))
    check(len(cli_reports) >= 1, f"CLI MD 报告已生成 ({len(cli_reports)})")
    check(len(cli_jsons) >= 1, f"CLI JSON 报告已生成 ({len(cli_jsons)})")

    # 验证 JSON 报告内容
    if cli_jsons:
        with open(cli_jsons[-1]) as f:
            cli_json = json.load(f)
        check("summary" in cli_json, "CLI JSON 有 summary")
        check("results" in cli_json, "CLI JSON 有 results")
        for r in cli_json["results"]:
            check("duration_sec" in r, f"CLI {r.get('test_id','?')} 有 duration_sec")

    # 清理
    import shutil
    shutil.rmtree(test_output, ignore_errors=True)


def test_08_report_isolation():
    """测试 8：模块隔离 —— 每个模块独立运行不影响其他模块"""
    print("\n" + "=" * 60)
    print("测试 8: 模块隔离验证")
    print("=" * 60)

    from test_run import UnifiedTestReporter

    reporter = UnifiedTestReporter(
        binary_path="/test/octos",
        test_date="2026-06-19 12:00:00",
        output_dir=Path("/tmp/test_report_test"),
    )

    # 添加模块并验证各自计数独立
    reporter.add_module("cli", [{"test_id": "1", "status": "PASS"}], passed=1, failed=0, total=1)
    reporter.add_module("serve", [{"test_id": "2", "status": "FAIL"}], passed=0, failed=1, total=1)
    reporter.add_module("bot", [{"test_id": "3", "status": "SKIP"}], passed=0, failed=0, total=1, skipped=1)

    js = reporter.generate_json()
    check(js["modules"]["cli"]["passed"] == 1, "CLI passed=1")
    check(js["modules"]["serve"]["failed"] == 1, "Serve failed=1")
    check(js["modules"]["bot"]["skipped"] == 1, "Bot skipped=1")
    check(js["summary"]["total"] == 3, "汇总 total=3")
    check(js["summary"]["passed"] == 1, "汇总 passed=1")
    check(js["summary"]["failed"] == 1, "汇总 failed=1")
    check(js["summary"]["skipped"] == 1, "汇总 skipped=1")


def main():
    """运行所有测试"""
    global PASS, FAIL

    print("=" * 60)
    print("Octos 测试报告生成 — 综合验证")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 确保临时目录存在
    Path("/tmp/test_report_test").mkdir(parents=True, exist_ok=True)

    tests = [
        ("UnifiedTestReporter Mock 数据", test_01_unified_reporter_mock_data),
        ("异常安全", test_02_exception_safety),
        ("空模块边界", test_03_empty_modules),
        ("CLI 报告格式", test_04_cli_report_format),
        ("Serve 报告格式", test_05_serve_report_format),
        ("报告总耗时", test_06_unified_reporter_total_duration),
        ("模块隔离", test_08_report_isolation),
        ("cmd_all 集成测试", test_07_cmd_all_integration),
    ]

    for name, func in tests:
        try:
            func()
        except Exception as e:
            import traceback
            FAIL += 1
            print(f"  ❌ [{name}] 异常: {e}")
            traceback.print_exc()

    # 汇总
    total = PASS + FAIL
    rate = round(PASS * 100 / total, 1) if total > 0 else 0
    print()
    print("=" * 60)
    print(f"📊 测试结果: {PASS}/{total} 通过 ({rate}%)")
    print(f"   ✅ 通过: {PASS}")
    print(f"   ❌ 失败: {FAIL}")
    print("=" * 60)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
