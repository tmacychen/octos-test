#!/usr/bin/env python3
"""Self-contained LINE integration verification (bypasses test_run.py teardown).

Starts mock_line + octos gateway in their own sessions, injects a '/new' event
through the mock, and verifies octos parses it and the bot replies to the mock.
Kills both process groups at the end so the harness never wedges.
"""
import json
import os
import re
import signal
import subprocess
import sys
import time

BINARY = "/Volumes/AppleData/octos/target/release/octos"
BOT_TEST_DIR = "/Volumes/AppleData/octos-test/bot_mock_test"
VENV_PY = "/Volumes/AppleData/octos-test/.venv/bin/python"
PORT = 5007
WEBHOOK_PORT = 8647
API_KEY = "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"
OUT = "/Volumes/AppleData/octos-test/verify_line"
os.makedirs(OUT, exist_ok=True)


def run(args, env, logpath):
    f = open(logpath, "w")
    p = subprocess.Popen(args, env=env, stdout=f, stderr=f, start_new_session=True)
    return p, f


def kill(p):
    try:
        pgid = os.getpgid(p.pid)
        os.killpg(pgid, signal.SIGKILL)
    except Exception as e:
        print(f"kill err {e}")


config = {
    "id": "test_line_bot",
    "name": "Test LINE Bot",
    "enabled": True,
    "created_at": "2026-07-13T00:00:00.000Z",
    "updated_at": "2026-07-13T00:00:00.000Z",
    "config": {
        "version": 1,
        "llm": {
            "primary": {
                "family_id": "nvidia",
                "model_id": "meta/llama-3.1-70b-instruct",
                "route": {
                    "api_key_env": "NVIDIA_API_KEY",
                    "base_url": "https://integrate.api.nvidia.com/v1",
                },
            },
            "fallbacks": [],
        },
        "channels": [{
            "type": "line",
            "channel_secret_env": "LINE_CHANNEL_SECRET",
            "channel_access_token_env": "LINE_CHANNEL_ACCESS_TOKEN",
            "webhook_port": WEBHOOK_PORT,
            "allowed_senders": "U_test_user,U_line_test_1,U_line_test_2,U_line_test_3,U_line_dedup,U_line_media,U_line_mention,U_line_session,U_line_config,U_line_llm,U_line_abort,U_line_split,U_line_user_a,U_line_user_b,U_line_llm_content",
        }],
        "gateway": {
            "max_history": 5,
            "max_concurrent_sessions": 10,
            "system_prompt": "x",
        },
    },
}
config_file = os.path.join(OUT, "profile.json")
with open(config_file, "w") as f:
    json.dump(config, f)

# Start mock
mock_env = {
    **os.environ,
    "LINE_API_BASE_URL": f"http://127.0.0.1:{PORT}",
    "PYTHONPATH": BOT_TEST_DIR,
}
mock_p, mock_f = run(
    [VENV_PY, os.path.join(BOT_TEST_DIR, "mock_line.py")],
    mock_env,
    os.path.join(OUT, "mock.log"),
)

# Wait for mock health
healthy = False
for _ in range(20):
    try:
        import httpx
        if httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=2).status_code == 200:
            healthy = True
            break
    except Exception:
        pass
    time.sleep(0.5)
print(f"MOCK_HEALTHY={healthy}")
if not healthy:
    print("MOCK FAILED TO START")
    print(open(mock_f.name).read()[-2000:])
    kill(mock_p)
    sys.exit(1)

# Start octos
octos_env = {
    **os.environ,
    "LINE_CHANNEL_SECRET": "test_secret",
    "LINE_CHANNEL_ACCESS_TOKEN": "test_token",
    "LINE_API_BASE_URL": f"http://127.0.0.1:{PORT}",
    "NVIDIA_API_KEY": API_KEY,
}
octos_p, octos_f = run(
    [BINARY, "gateway", "--profile", config_file, "--data-dir", OUT],
    octos_env,
    os.path.join(OUT, "octos.log"),
)

# Wait for ready + webhook listening
ready = False
deadline = time.time() + 60
while time.time() < deadline:
    if octos_p.poll() is not None:
        print("OCTOS EXITED EARLY")
        break
    try:
        c = open(octos_f.name).read()
    except Exception:
        c = ""
    if re.search(r"gateway.*ready|Gateway ready|\[gateway\] ready", c) and "LINE webhook server listening" in c:
        ready = True
        break
    time.sleep(1)
print(f"OCTOS_READY={ready}")

# Inject
event = {
    "type": "message",
    "replyToken": "reply_1",
    "source": {"type": "user", "userId": "U_line_session"},
    "message": {"id": "msg_1", "type": "text", "text": "/new"},
}
try:
    r = httpx.post(
        f"http://127.0.0.1:{PORT}/_inject?webhook_port={WEBHOOK_PORT}",
        json={"event": event, "channel_secret": "test_secret"},
        timeout=30,
    )
    print(f"INJECT_STATUS={r.status_code} body={r.text[:200]}")
except Exception as e:
    print(f"INJECT_ERROR={e!r}")

# Poll for parse + reply
parse_ok = False
reply_ok = False
deadline2 = time.time() + 90
while time.time() < deadline2:
    c = open(octos_f.name).read()
    if "LINE: parsed event" in c:
        parse_ok = True
    try:
        sm = httpx.get(f"http://127.0.0.1:{PORT}/_sent_messages", timeout=5).json()
        if sm:
            reply_ok = True
            print(f"REPLY_MSGS={str(sm)[:400]}")
    except Exception:
        pass
    if parse_ok and reply_ok:
        break
    time.sleep(1)
print(f"PARSE_OK={parse_ok} REPLY_OK={reply_ok}")

kill(octos_p)
kill(mock_p)
print("DONE")
