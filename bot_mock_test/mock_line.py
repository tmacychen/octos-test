#!/usr/bin/env python3
"""
LINE Mock Server - FastAPI 实现的 LINE Messaging API Mock 服务

模拟 LINE Messaging API，用于测试 octos LINE bot 集成。

端口: 5007 (默认)
端点:
  - POST /v2/bot/message/push - LINE API: 推送消息
  - GET /v2/bot/info - LINE API: Bot 信息
  - GET /health - 健康检查
  - POST /_inject - 向 bot webhook 注入事件
  - GET /_sent_messages - 获取 bot 发送的消息
  - POST /_clear - 清理状态
"""

import asyncio
import hashlib
import hmac
import json
import logging
import sys
import time
import base64
import httpx
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
import uvicorn
from threading import Thread

logger = logging.getLogger("mock_line")


def _log_inject(msg: str):
    """Persist inject/forward results to a file for offline diagnosis."""
    try:
        with open("/tmp/mock_line_inject.log", "a") as f:
            f.write(f"{time.time():.3f} {msg}\n")
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
# Mock LINE API Server
# ══════════════════════════════════════════════════════════════════════════════

class MockLineServer:
    """Mock LINE Messaging API server for testing."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5007):
        self.host = host
        self.port = port
        self._sent_messages: list[dict] = []
        self._bot_info = {
            "userId": "U_mock_bot",
            "displayName": "TestBot",
            "pictureUrl": "https://example.com/bot.png",
            "language": "zh",
        }
        self.app = FastAPI(title="LINE Mock API")
        self._setup_routes()

    def _setup_routes(self):
        app = self.app

        @app.post("/v2/bot/message/push")
        async def push_message(request: Request):
            """Mock LINE push message API - records sent messages."""
            data = await request.json()
            to = data.get("to", "")
            messages = data.get("messages", [])
            for msg in messages:
                entry = {"to": to, **msg, "timestamp": time.time()}
                self._sent_messages.append(entry)
                logger.debug(f"Bot pushed message to {to}: {msg.get('type')}")
            return {"sentMessages": [{"id": f"msg_{int(time.time())}"} for _ in messages]}

        @app.post("/v2/bot/message/reply")
        async def reply_message(request: Request):
            """Mock LINE reply message API."""
            data = await request.json()
            reply_token = data.get("replyToken", "")
            messages = data.get("messages", [])
            for msg in messages:
                entry = {"replyToken": reply_token, **msg, "timestamp": time.time()}
                self._sent_messages.append(entry)
            return {"sentMessages": [{"id": f"msg_{int(time.time())}"} for _ in messages]}

        @app.get("/v2/bot/info")
        async def bot_info():
            """Mock LINE bot info API."""
            logger.debug("Bot info requested")
            return self._bot_info

        @app.post("/v2/bot/message/upload")
        async def upload_content(request: Request):
            """Mock LINE content upload API."""
            return {"contentId": f"content_{int(time.time())}"}

        @app.get("/v2/bot/message/{message_id}/content")
        async def get_content(message_id: str):
            """Mock LINE content download API."""
            return b"mock file content"

        # ── Test control endpoints ──

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.post("/_inject")
        async def inject_event(request: Request):
            """Inject a webhook event by POSTing to the bot's webhook endpoint.
            
            The gateway runs its own webhook server on LINE_WEBHOOK_PORT (8646).
            This endpoint forwards the event to that webhook.
            """
            data = await request.json()
            webhook_port = int(request.query_params.get("webhook_port", "8646"))
            bot_webhook_url = f"http://127.0.0.1:{webhook_port}/line/webhook"

            # Build webhook payload (events array)
            event = data.get("event", {})
            events = [event] if event else []
            payload = {"destination": "U_mock_bot", "events": events}

            # Sign the payload with channel_secret for signature verification
            channel_secret = data.get("channel_secret", "test_secret")
            body_str = json.dumps(payload, separators=(",", ":"))
            signature = hmac.new(
                channel_secret.encode(),
                body_str.encode(),
                hashlib.sha256,
            ).digest()
            sig_b64 = base64.b64encode(signature).decode()

            last_err = None
            for attempt in range(4):
                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.post(
                            bot_webhook_url,
                            content=body_str,
                            headers={
                                "Content-Type": "application/json",
                                "X-Line-Signature": sig_b64,
                            },
                        )
                    if resp.status_code == 200:
                        logger.debug(f"Injected event: {event.get('type')}")
                        _log_inject(f"OK status={resp.status_code} url={bot_webhook_url}")
                        return {"ok": True, "status": resp.status_code}
                    else:
                        logger.warning(f"Webhook returned {resp.status_code}: {resp.text}")
                        _log_inject(f"WEBHOOK_RETURNED status={resp.status_code} body={resp.text[:200]} url={bot_webhook_url}")
                        return {"ok": False, "status": resp.status_code, "error": resp.text}
                except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                    last_err = e
                    logger.warning(f"Inject attempt {attempt + 1} to {bot_webhook_url} failed: {e}")
                    _log_inject(f"ATTEMPT {attempt + 1} FAIL {type(e).__name__}: {e} url={bot_webhook_url}")
                    if attempt < 3:
                        await asyncio.sleep(1.5)
                        continue
                    _log_inject(f"CONNECT_ERROR after retries {e} url={bot_webhook_url}")
                    return {"ok": False, "error": str(e)}
                except Exception as e:
                    logger.warning(f"Inject exception: {e}")
                    _log_inject(f"EXCEPTION {type(e).__name__}: {e} url={bot_webhook_url}")
                    return {"ok": False, "error": str(e)}

        @app.get("/_sent_messages")
        async def get_sent_messages():
            """Return all messages sent by the bot."""
            return self._sent_messages

        @app.post("/_clear")
        async def clear_state():
            """Clear mock state."""
            self._sent_messages.clear()
            return {"ok": True}

    def start_background(self, log_file=None):
        """Start the server in a background thread."""
        def run():
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="warning",
                timeout_keep_alive=60,
            )
        thread = Thread(target=run, daemon=True)
        thread.start()
        logger.info(f"LINE Mock server started at http://{self.host}:{self.port}")
        return thread


def main():
    server = MockLineServer()
    server.start_background()
    try:
        import time as _time
        while True:
            _time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
