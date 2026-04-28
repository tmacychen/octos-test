# Bot Test Flaky Retry Feature - SPEC

## Motivation

Bot integration tests (Telegram/Discord) are sensitive to:
- Mock server state corruption after certain tests
- Gateway process crashes due to memory issues
- Race conditions in concurrent test scenarios

When a test fails but subsequent tests pass, this indicates the failure may be "flaky" - caused by transient state corruption that later clears. This feature automatically detects this pattern and retries from the failing test.

## Design

### Detection Algorithm

1. Run all tests in order, tracking which passed and which failed
2. If failures detected:
   - Find the first failing test's position in execution order
   - Check if ANY test passed AFTER that position
   - If yes → flaky pattern detected, retry from first failure
   - If no → genuine failure, report immediately

### Flaky Pattern Example

```
Test order: A → B → C → D → E
Run 1:      PASS PASS FAIL PASS PASS
                               ↑ first failure is C
                               ↑ tests D, E passed after
Result: FLaky → retry C, D, E
```

### Non-Flaky Pattern Example

```
Test order: A → B → C → D → E
Run 1:      PASS PASS FAIL
                              ↑ first failure is C
                              ↑ no tests after C
Result: Genuine failure → report C
```

## Flow

```
run_bot_test_with_flaky_retry(module)
  │
  ├─ get_test_order(module) → [A, B, C, D, E]
  │
  ├─ run_bot_test(module) → passed=False, failed=[C], passed=[A,B]
  │
  ├─ detect_flaky_failure(failed=[C], passed=[A,B], all=[A,B,C,D,E])
  │     └─ first_failure_idx=2, passed_after=False → return False
  │
  └─ Not flaky, return (False, [C])
```

```
If flaky detected:
  │
  ├─ get_tests_to_rerun([C], [A,B,C,D,E]) → [C, D, E]
  │
  ├─ run_bot_test(module, "C or D or E")
  │
  └─ Return result (retry)
```

## Retry Behavior

- **Only one retry attempt** - if retry also fails, report immediately
- **Restart services** - cleanup and restart mock server + octos gateway before retry
- **Resume from first failure** - tests before first failure are not re-run

## CLI Changes

No new flags. Flaky retry is automatic when the pattern is detected.

```
uv run python test_run.py --test bot telegram  # flaky retry auto-enabled
```

## Key Functions

| Function | Purpose |
|----------|---------|
| `get_test_order(module)` | Get deterministic test execution order |
| `detect_flaky_failure(failed, passed, all_tests)` | Detect flaky pattern |
| `get_tests_to_rerun(failed, all_tests)` | Get tests from first failure onwards |
| `run_bot_test_with_flaky_retry(module)` | Main wrapper with flaky retry logic |

## Acceptance Criteria

1. When failure is followed by later passes, services restart and tests resume from first failure
2. When failure has no later passes, report immediately without retry
3. Retry only happens once
4. Tests before first failure are NOT re-run
5. Clear logging indicates flaky detection and retry
