#!/usr/bin/env python3
"""
Octos CLI Test Module - Python implementation of cli_test.sh.

This module provides CLI test execution with the same logic as cli_test.sh,
but integrated into the Python test runner ecosystem.
"""

import fnmatch
import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple


class CLITestResult:
    """Represents a single CLI test result."""

    def __init__(self, test_id: str, category: str, name: str, status: str):
        self.test_id = test_id
        self.category = category
        self.name = name
        self.status = status  # "PASS" or "FAIL"

    def to_markdown_row(self) -> str:
        """Convert to markdown table row."""
        return f"| {self.test_id} | {self.category} | {self.name} | {self.status} |"


class CLITestRunner:
    """CLI test runner that mimics cli_test.sh behavior."""

    def __init__(
        self,
        binary_path: Path,
        test_dir: Path,
        log_dir: Path,
        output_dir: Optional[Path] = None,
        verbose: bool = False,
        scope: Optional[str] = None,
        ids_filter: Optional[str] = None,
        batch_size: Optional[int] = None,
        batch_index: Optional[int] = None,
    ):
        self.binary_path = binary_path
        self.test_dir = test_dir
        self.log_dir = log_dir
        self.output_dir = output_dir or (test_dir.parent / "test-results")
        self.verbose = verbose
        self.scope = scope or "all"
        self.ids_filter = ids_filter
        self.batch_size = batch_size
        self.batch_index = batch_index

        # Parsed filter state
        self._scope_categories: Optional[Set[str]] = self._parse_scope(scope)
        self._id_patterns: Optional[List[str]] = self._parse_ids(ids_filter)

        # Logger setup (must be before _load_test_cases)
        self.logger = logging.getLogger("octos.cli")

        # Load test cases
        self.config_file = Path(__file__).parent / "full_cases.json"
        self.test_cases = self._load_test_cases()

        # Counters
        self.total = 0
        self.passed = 0
        self.failed = 0

        # Results storage
        self.results: List[CLITestResult] = []

        # Timestamps
        self.test_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.report_date = datetime.now().strftime("%Y-%m-%d_%H%M")
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Current state
        self.current_category = ""
        self.category_test_dir: Optional[Path] = None

    def _load_test_cases(self) -> dict:
        """Load test cases from JSON config file."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Test config not found: {self.config_file}")

        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.logger.info(
            f"Loaded {len(data.get('tests', []))} test cases from {self.config_file}"
        )
        return data

    def _parse_scope(self, scope: Optional[str]) -> Optional[Set[str]]:
        """Parse scope string into a set of categories.

        Supports comma-separated categories, e.g. 'Chat,Security'.
        Returns None if scope is 'all' or not set.
        """
        if not scope or scope == "all":
            return None
        return {cat.strip() for cat in scope.split(",") if cat.strip()}

    def _parse_ids(self, ids_filter: Optional[str]) -> Optional[List[str]]:
        """Parse IDs filter string into a list of patterns.

        Supports:
        - Exact IDs: '20.1,20.2,21.1'
        - Wildcards: '20.*,21.*'
        - Ranges: '20.1-28.4' (includes all IDs between start and end)
        - Mixed: '20.*,25.1-25.3,28.1'
        """
        if not ids_filter:
            return None

        patterns = []
        for part in ids_filter.split(","):
            part = part.strip()
            if not part:
                continue

            # Check if it's a range (contains '-' and no '*')
            if "-" in part and "*" not in part:
                range_parts = part.split("-")
                if len(range_parts) == 2:
                    patterns.append(
                        ("range", range_parts[0].strip(), range_parts[1].strip())
                    )
                else:
                    patterns.append(("glob", part))
            else:
                patterns.append(("glob", part))

        return patterns if patterns else None

    def _id_matches(self, test_id: str) -> bool:
        """Check if a test ID matches the filter patterns."""
        if not self._id_patterns:
            return True

        for pattern_type, *args in self._id_patterns:
            if pattern_type == "glob":
                if fnmatch.fnmatch(test_id, args[0]):
                    return True
            elif pattern_type == "range":
                start_id, end_id = args[0], args[1]
                if start_id <= test_id <= end_id:
                    return True

        return False

    def _should_run_test(
        self, test_id: str, category: str, test_index: int, total_tests: int
    ) -> bool:
        """Determine if a test should be executed based on all filters.

        All active filters are ANDed together.
        """
        # Category filter
        if self._scope_categories is not None:
            if category not in self._scope_categories:
                return False

        # ID filter
        if self._id_patterns is not None:
            if not self._id_matches(test_id):
                return False

        # Batch filter
        if self.batch_size is not None and self.batch_index is not None:
            batch_start = self.batch_index * self.batch_size
            batch_end = batch_start + self.batch_size
            if not (batch_start <= test_index < batch_end):
                return False

        return True

    def _get_logger_for_category(self, category: str) -> logging.Logger:
        """Get or create logger for specific category."""
        logger_name = f"octos.cli.{category.lower()}"
        logger = logging.getLogger(logger_name)

        # Add file handler if not already present
        if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
            log_file = self.log_dir / f"cli_test_{category}_{self.timestamp}.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)

            formatter = logging.Formatter(
                "%(asctime)s [%(name)s] %(levelname)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _run_command(self, cmd_args: str, timeout: int = 60) -> Tuple[int, str, str]:
        """Execute octos command and capture output."""
        full_cmd = [str(self.binary_path)] + cmd_args.split()

        try:
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ},
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    def _validate_result(
        self, actual: str, exit_code: int, expected: str, validation: str
    ) -> bool:
        """Validate test result based on validation type.

        Supports '|' as OR operator in expected string.
        Example: "Created|.octos" means output should contain "Created" OR ".octos"
        """
        if validation == "contains":
            # Split by '|' to support multiple possible matches (OR logic)
            expected_parts = [
                part.strip() for part in expected.split("|") if part.strip()
            ]
            # Return True if ANY part is found in actual output
            return any(part in actual for part in expected_parts)
        elif validation == "not_contains":
            # For not_contains, split by '|' and ensure NONE of the parts are found
            expected_parts = [
                part.strip() for part in expected.split("|") if part.strip()
            ]
            return all(part not in actual for part in expected_parts)
        elif validation == "exitcode":
            return exit_code == int(expected)
        else:
            return False

    def run_cli_test(
        self,
        test_id: str,
        category: str,
        name: str,
        cmd_args: str,
        expected: str,
        validation: str = "contains",
        timeout: int = 60,
    ) -> CLITestResult:
        """Run a single CLI test case."""
        self.total += 1

        category_logger = self._get_logger_for_category(category)
        category_logger.info(f"[EXEC] octos {cmd_args}")
        category_logger.info(f"[TEST_DIR] {self.category_test_dir}")

        # Execute command
        exit_code, stdout, stderr = self._run_command(cmd_args, timeout)
        actual = stdout + stderr

        # Validate
        passed = self._validate_result(actual, exit_code, expected, validation)

        # Update counters
        if passed:
            self.passed += 1
            status = "PASS"
        else:
            self.failed += 1
            status = "FAIL"

        # Store result
        result = CLITestResult(test_id, category, name, status)
        self.results.append(result)

        # Log details
        category_logger.info(f"[EXITCODE] {exit_code}")
        if stdout:
            category_logger.info(f"[STDOUT] {stdout[:500]}")  # Truncate long output
        if stderr:
            category_logger.warning(f"[STDERR] {stderr[:500]}")
        category_logger.info(f"[STATUS] {status}")

        # Verbose output
        if self.verbose:
            print(f"\n[EXEC] octos {cmd_args}")
            print(f"[EXITCODE] {exit_code}")
            if stdout:
                print(f"[STDOUT]\n{stdout}")
            if stderr:
                print(f"[STDERR]\n{stderr}")

        # Print result
        color = "\033[0;32m" if passed else "\033[0;31m"
        reset = "\033[0m"
        print(f"{color}[{status}]{reset} {test_id} {name}")

        return result

    def run_file_check(
        self,
        test_id: str,
        category: str,
        name: str,
        path: str,
        should_exist: bool = True,
    ) -> CLITestResult:
        """Check if a file/directory exists."""
        self.total += 1

        category_logger = self._get_logger_for_category(category)
        category_logger.info(f"[FILE CHECK] Test directory: {self.category_test_dir}")
        category_logger.info(f"[FILE CHECK] Checking path: {path}")

        # Small delay to ensure previous command completed
        time.sleep(0.1)

        # Retry logic
        exists = False
        max_retries = 5
        for attempt in range(max_retries):
            if Path(path).exists():
                exists = True
                category_logger.info(
                    f"[FILE CHECK] File exists: YES (attempt {attempt + 1})"
                )
                break
            else:
                if attempt < max_retries - 1:
                    category_logger.info(
                        f"[FILE CHECK] File not found, retrying ({attempt + 1}/{max_retries})..."
                    )
                    time.sleep(0.2)

        if not exists:
            category_logger.warning(
                f"[FILE CHECK] File exists: NO (after {max_retries} attempts)"
            )
            # Debug info
            parent_dir = Path(path).parent
            if parent_dir.exists():
                category_logger.info(
                    f"[FILE CHECK] Parent directory exists: {parent_dir}"
                )
                category_logger.info(
                    f"[FILE CHECK] Contents: {list(parent_dir.iterdir())}"
                )
            else:
                category_logger.warning(
                    f"[FILE CHECK] Parent directory does NOT exist: {parent_dir}"
                )

        # Validate
        passed = exists == should_exist

        if passed:
            self.passed += 1
            status = "PASS"
        else:
            self.failed += 1
            status = "FAIL"

        # Store result
        result = CLITestResult(test_id, category, name, status)
        self.results.append(result)

        # Log
        category_logger.info(f"[FILE CHECK] {path}")
        category_logger.info(f"[STATUS] {status}")

        # Verbose output
        if self.verbose:
            print(f"\n[FILE CHECK] {path}")
            print(f"[STATUS] {status}")

        # Print result
        color = "\033[0;32m" if passed else "\033[0;31m"
        reset = "\033[0m"
        print(f"{color}[{status}]{reset} {test_id} {name}")

        return result

    def _cleanup_category_dir(self):
        """Cleanup current category test directory."""
        if self.category_test_dir and self.category_test_dir.exists():
            self.logger.info(
                f"[CLEANUP] Removing test directory: {self.category_test_dir}"
            )
            import shutil

            shutil.rmtree(self.category_test_dir, ignore_errors=True)

    def run_all_tests(self) -> bool:
        """Run all tests from JSON config."""
        tests = self.test_cases.get("tests", [])
        skipped = 0

        # Build filter summary
        filter_parts = []
        if self._scope_categories is not None:
            filter_parts.append(
                f"categories={','.join(sorted(self._scope_categories))}"
            )
        if self._id_patterns is not None:
            filter_parts.append(f"ids={self.ids_filter}")
        if self.batch_size is not None:
            filter_parts.append(f"batch={self.batch_index}/{self.batch_size}")
        filter_summary = " | ".join(filter_parts) if filter_parts else "all"

        print(f"\n{'=' * 60}")
        print(f"Octos CLI Automated Test")
        print(f"{'=' * 60}")
        print(f"Test Time: {self.test_date}")
        print(f"Binary: {self.binary_path}")
        print(f"Config: {self.config_file.name}")
        print(f"Filter: {filter_summary}")
        print(f"Base Test Directory: {self.test_dir}")
        print()

        for i, test in enumerate(tests):
            test_id = test["id"]
            category = test["category"]
            name = test["name"]
            command = test["command"]
            expected = test.get("expected", "")
            validation = test.get("validation", "contains")
            timeout = test.get("timeout", 60)
            test_type = test.get("type", "cli")
            file_path = test.get("path", "")
            should_exist = test.get("should_exist", True)

            # Apply all filters
            if not self._should_run_test(test_id, category, i, len(tests)):
                skipped += 1
                continue

            # Create isolated test directory per category
            if category != self.current_category:
                # Cleanup previous category
                self._cleanup_category_dir()

                self.current_category = category
                self.category_test_dir = self.test_dir / f"{category}_{self.timestamp}"
                self.category_test_dir.mkdir(parents=True, exist_ok=True)

                self.logger.info(
                    f"[SETUP] Created test directory for {category}: {self.category_test_dir}"
                )
                print(f"\n\033[0;33m[{category}]\033[0m")

            # Replace variables in command/path
            command = command.replace("{testDir}", str(self.category_test_dir))
            command = command.replace("{tempDir}", str(self.test_dir / "temp"))

            # Remove escaped quotes that are used for JSON formatting
            command = command.replace('\\"', "")

            if file_path:
                file_path = file_path.replace("{testDir}", str(self.category_test_dir))
                file_path = file_path.replace("{tempDir}", str(self.test_dir / "temp"))
                # Remove escaped quotes from file paths too
                file_path = file_path.replace('\\"', "")

            # Run test
            if test_type == "file_check":
                self.run_file_check(test_id, category, name, file_path, should_exist)
            else:
                self.run_cli_test(
                    test_id, category, name, command, expected, validation, timeout
                )

        # Final cleanup
        self._cleanup_category_dir()

        if skipped > 0:
            print(f"\n\033[0;90mSkipped {skipped} tests (scope: {self.scope})\033[0m")

        return self.failed == 0

    def generate_report(self) -> Path:
        """Generate Markdown report similar to cli_test.sh format."""
        # Print generating message (matching cli_test.sh)
        print(f"\n{'=' * 60}")
        print(f"\033[0;36mGenerating Brief Report...\033[0m")
        self.logger.info("=" * 60)
        self.logger.info("Generating Brief Report...")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.output_dir / f"CLI_TEST_REPORT_{self.report_date}.md"

        pass_rate = (self.passed * 100 // self.total) if self.total > 0 else 0

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Octos CLI Test Report\n\n")
            f.write("## Summary\n\n")
            f.write(f"- **Test Date**: {self.test_date}\n")
            f.write(f"- **Scope**: {self.scope}\n")
            f.write(f"- **Total**: {self.total}\n")
            f.write(f"- **Passed**: {self.passed}\n")
            f.write(f"- **Failed**: {self.failed}\n")
            f.write(f"- **Pass Rate**: {pass_rate}%\n\n")

            f.write("## Failed Tests\n\n")
            if self.failed == 0:
                f.write("✅ All tests passed!\n")
            else:
                f.write("| ID | Category | Test Name |\n")
                f.write("|----|----------|-----------|\n")
                for result in self.results:
                    if result.status == "FAIL":
                        f.write(
                            result.to_markdown_row().replace(" | FAIL |", " |") + "\n"
                        )

            f.write("\n---\n")
            f.write(f"*Generated at {self.test_date}*\n")

        self.logger.info(f"Report saved to: {report_path}")
        return report_path

    def print_summary(self, report_path: Path):
        """Print summary to stdout similar to cli_test.sh format."""
        pass_rate = (self.passed * 100 // self.total) if self.total > 0 else 0

        # Define log file path (matching cli_test.sh behavior)
        log_file = self.log_dir / "cli_test.log"

        print(f"\n{'=' * 60}")
        print(f"\033[1mTest Summary\033[0m")
        print(f"{'=' * 60}")
        print(f"  Scope:     {self.scope}")
        print(f"  Total:     {self.total}")
        print(f"  Passed:    \033[0;32m{self.passed}\033[0m")
        print(f"  Failed:    \033[0;31m{self.failed}\033[0m")
        print(f"  Pass Rate: {pass_rate}%")
        print()
        print(f"  Report:    \033[0;32m{report_path}\033[0m")
        print(f"  Log:       \033[0;90m{log_file}\033[0m")
        print(f"{'=' * 60}")

        self.logger.info(f"Report saved to: {report_path}")
        self.logger.info(f"Log saved to: {log_file}")
        self.logger.info("=" * 60)
        self.logger.info(
            f"SUMMARY: Total={self.total} Passed={self.passed} "
            f"Failed={self.failed} PassRate={pass_rate}%"
        )


def run_cli_tests(
    binary_path: Path,
    test_dir: Path,
    log_dir: Path,
    verbose: bool = False,
    output_dir: Optional[Path] = None,
    scope: Optional[str] = None,
    ids_filter: Optional[str] = None,
    batch_size: Optional[int] = None,
    batch_index: Optional[int] = None,
) -> Tuple[bool, List[str]]:
    """
    Main entry point for CLI tests.

    Args:
        binary_path: Path to octos binary
        test_dir: Base test directory (/tmp/octos_test)
        log_dir: Log directory (/tmp/octos_test/logs)
        verbose: Enable verbose output
        output_dir: Output directory for reports
        scope: Test scope filter (comma-separated categories, or 'all')
        ids_filter: Test ID filter (e.g. '20.*,21.1-21.3', or None)
        batch_size: Number of tests per batch
        batch_index: Zero-based index of the batch to run

    Returns:
        Tuple of (all_passed, error_messages)
    """
    runner = CLITestRunner(
        binary_path=binary_path,
        test_dir=test_dir,
        log_dir=log_dir,
        output_dir=output_dir,
        verbose=verbose,
        scope=scope,
        ids_filter=ids_filter,
        batch_size=batch_size,
        batch_index=batch_index,
    )

    # Run tests
    all_passed = runner.run_all_tests()

    # Generate report
    report_path = runner.generate_report()

    # Print summary
    runner.print_summary(report_path)

    # Collect error messages
    errors = []
    for result in runner.results:
        if result.status == "FAIL":
            errors.append(
                f"CLI test {result.test_id} ({result.category}): {result.name}"
            )

    return all_passed, errors


if __name__ == "__main__":
    """Allow running CLI tests directly from command line."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Octos CLI Test Runner")
    parser.add_argument(
        "-b", "--binary", type=Path, required=True, help="Path to octos binary"
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for reports",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "-s",
        "--scope",
        type=str,
        default="all",
        help="Test scope filter: comma-separated categories, e.g. 'Chat,Security' (default: all)",
    )
    parser.add_argument(
        "--ids",
        type=str,
        default=None,
        help="Test ID filter: e.g. '20.*,21.1-21.3,25.1' (default: all)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=None, help="Number of tests per batch slice"
    )
    parser.add_argument(
        "--batch-index",
        type=int,
        default=0,
        help="Zero-based index of the batch to run (requires --batch-size)",
    )

    args = parser.parse_args()

    # Setup paths
    test_dir = Path("/tmp/octos_test")
    log_dir = test_dir / "logs"
    test_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [CLI] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "cli_test.log"),
        ],
    )

    # Run tests
    success = run_cli_tests(
        binary_path=args.binary,
        test_dir=test_dir,
        log_dir=log_dir,
        verbose=args.verbose,
        output_dir=args.output_dir,
        scope=args.scope,
        ids_filter=args.ids,
        batch_size=args.batch_size,
        batch_index=args.batch_index,
    )

    sys.exit(0 if success else 1)
