# Slack Bot Testing Guide

## Overview

This document describes the Slack bot testing framework for the octos project.

## Architecture

### Components

1. **Mock Slack Server** (`mock_slack.py`)
   - FastAPI-based mock server simulating Slack Events API
   - Runs on port 5003
   - Handles URL verification challenges
   - Receives and records events from octos gateway

2. **Slack Test Runner** (`runner_slack.py`)
   - Provides test automation utilities
   - Injects test events into Mock Server
   - Captures bot responses
   - Consistent interface with Telegram/Discord/Matrix runners

3. **Test Cases** (`test_slack.py`)
   - Integration tests for Slack bot functionality
   - Basic message handling
   - Session management commands

### Flow

```
Test Case → SlackTestRunner → Mock Server (port 5003) → octos gateway → LLM → Response
```

## Setup

### Prerequisites

1. **octos binary** with `slack` feature enabled:
   ```bash
   cargo build --release -p octos-cli --features slack,api
   ```

2. **Environment variables**:
   ```bash
   export SLACK_BOT_TOKEN=xoxb-your-bot-token
   export OPENAI_API_KEY=nvapi-your-nvidia-api-key
   ```

3. **Python dependencies**:
   ```bash
   cd bot_mock_test
   pip install -r requirements.txt
   ```

## Running Tests

### Using test_run.py (Recommended)

```bash
# Run all Slack tests
uv run python test_run.py --test bot slack

# Run specific test class
uv run python test_run.py --test bot slack TestSlackBasicMessages

# Run specific test method
uv run python test_run.py --test bot slack TestSlackSessionCommands.test_new_creates_session
```

### Using pytest directly

```bash
cd bot_mock_test
pytest test_slack.py -v
```

## Test Cases

### TestSlackBasicMessages

1. **test_simple_message**
   - Injects a simple text message
   - Verifies Mock Server receives the event
   - Waits for bot response (requires LLM)

2. **test_mock_server_health**
   - Checks Mock Server health endpoint
   - Verifies statistics tracking

### TestSlackSessionCommands

1. **test_new_creates_session**
   - Tests `/new` command to create a new session
   - Verifies session switch response

2. **test_help_command**
   - Tests `/help` command
   - Verifies help information is returned

## Configuration

### Mock Server Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/slack/events` | POST | Slack Events API webhook |
| `/_inject` | POST | Inject test events |
| `/_sent_messages` | GET | Get bot sent messages |
| `/_clear` | POST | Clear all state |
| `/_transactions` | GET | Get received transactions |
| `/_stats` | GET | Get server statistics |

### Event Format

Injected events follow Slack Events API format:

```json
{
  "token": "test_token",
  "team_id": "T012AB3CD",
  "api_app_id": "A012AB3CD",
  "event": {
    "type": "message",
    "text": "Hello!",
    "user": "U012AB3CD",
    "channel": "C012AB3CD",
    "ts": "1234567890.123456"
  },
  "type": "event_callback",
  "event_id": "Ev012AB3CD",
  "event_time": 1234567890
}
```

## Troubleshooting

### Mock Server not starting

Check if port 5003 is in use:
```bash
lsof -i :5003
```

Kill existing processes:
```bash
kill -9 $(lsof -ti :5003)
```

### Bot not responding

1. Verify octos binary has `slack` feature:
   ```bash
   strings /path/to/octos | grep -i slack
   ```

2. Check gateway logs:
   ```bash
   cat /tmp/octos_test/logs/02_gateway_slack_*.log
   ```

3. Verify environment variables are set:
   ```bash
   echo $SLACK_BOT_TOKEN
   echo $OPENAI_API_KEY
   ```

### Tests timing out

Increase timeout values in `test_slack.py`:
```python
TIMEOUT_COMMAND = 30  # Default: 20
TIMEOUT_LLM = 60      # Default: 50
```

## Comparison with Other Channels

| Feature | Telegram | Discord | Matrix | Slack |
|---------|----------|---------|--------|-------|
| Mock Server Port | 5000 | 5001 | 5002 | 5003 |
| Protocol | HTTP API | WebSocket | Appservice | Events API |
| Config Format | Config | Config | UserProfile | Config |
| Admin Commands | ✓ | ✓ | ✓ | ✓ |
| Session Management | ✓ | ✓ | ✓ | ✓ |

## Future Enhancements

- [ ] Add Slack-specific slash commands testing
- [ ] Test interactive components (buttons, menus)
- [ ] Test file uploads and attachments
- [ ] Test channel management commands
- [ ] Add performance and stress tests
- [ ] Test multi-channel scenarios

## References

- [Slack Events API Documentation](https://api.slack.com/apis/connections/events-api)
- [octos Gateway Documentation](../docs/)
- [Matrix Testing Guide](./README.md#matrix-testing)
