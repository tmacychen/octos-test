#!/usr/bin/env python3
"""
Twilio Mock Server - FastAPI 实现的 Twilio API Mock 服务

模拟 Twilio REST API 和 Webhook，用于测试 octos Twilio bot 集成。

端口: 5011 (默认)
端点:
  - POST /2010-04-01/Accounts/{sid}/Messages.json - Twilio API: 发送消息
  - GET /health - 健康检查
  - POST /_inject - 向 bot webhook 注入事件
  - GET /_sent_messages - 获取 bot 发送的消息
  - POST /_clear - 清理状态
"""

import hashlib
import hmac
import base64
import json
import logging
import sys
import time
import httpx
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from threading import Thread

logger = logging.getLogger("mock_twilio")


class MockTwilioServer:
    """Mock Twilio API server for testing."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5011):
        self.host = host
        self.port = port
        self._sent_messages: list[dict] = []
        self.app = FastAPI(title="Twilio Mock API")
        self._setup_routes()

    @staticmethod
    def compute_signature(auth_token: str, url: str, params: list) -> str:
        """Compute X-Twilio-Signature: HMAC-SHA1(auth_token, url + sorted_params)."""
        sorted_params = sorted(params, key=lambda p: p[0])
        data = url
        for key, value in sorted_params:
            data += key + value
        signature = hmac.new(
            auth_token.encode(),
            data.encode(),
            hashlib.sha1,
        ).digest()
        return base64.b64encode(signature).decode()

    def _setup_routes(self):
        app = self.app

        # ── Twilio API endpoints ──

        @app.post("/2010-04-01/Accounts/{account_sid}/Messages.json")
        async def send_message(account_sid: str, request: Request):
            """Twilio API: 发送消息 — 记录 bot 回复"""
            # Verify Basic Auth
            auth = request.headers.get("authorization", "")
            if not auth.startswith("Basic "):
                raise HTTPException(status_code=401, detail="Unauthorized")

            content_type = request.headers.get("content-type", "")
            if "application/x-www-form-urlencoded" in content_type:
                form = await request.form()
                body = dict(form)
            else:
                body = await request.json()

            to = body.get("To", "")
            from_number = body.get("From", "")
            text = body.get("Body", "")

            logger.info(f"Bot sent SMS to {to}: {text[:80]}")

            message_record = {
                "to": to,
                "sender": from_number,
                "chat_id": to,
                "text": text,
                "timestamp": time.time(),
            }
            self._sent_messages.append(message_record)

            return JSONResponse({
                "sid": f"SM{uuid_hex()}",
                "account_sid": account_sid,
                "to": to,
                "from": from_number,
                "body": text,
                "status": "queued",
                "date_sent": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })

        # ── Test control endpoints ──

        @app.get("/health")
        async def health():
            return {"status": "ok", "service": "twilio-mock-server"}

        @app.post("/_inject")
        async def inject_event(request: Request):
            """向 bot webhook 注入一条 Twilio SMS 消息。

            mock server 主动 HTTP POST 到 octos 的 Twilio webhook 端点。
            """
            data = await request.json()
            webhook_port = int(data.get("webhook_port", "8649"))
            auth_token = data.get("auth_token", "test_auth_token")

            from_number = data.get("from_number", "+15550000001")
            to_number = data.get("to_number", "+15559999999")
            body_text = data.get("body", "")
            message_sid = data.get("message_sid") or f"SM{uuid_hex()}"
            num_media = data.get("num_media", 0)

            # Build form params
            params = [
                ("From", from_number),
                ("To", to_number),
                ("Body", body_text),
                ("MessageSid", message_sid),
                ("NumMedia", str(num_media)),
                ("AccountSid", "ACtest"),
                ("SmsSid", message_sid),
                ("SmsStatus", "received"),
            ]

            # Compute X-Twilio-Signature
            webhook_url = f"http://127.0.0.1:{webhook_port}/twilio/webhook"
            signature = self.compute_signature(auth_token, webhook_url, params)

            # Send as form-urlencoded to octos webhook
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        webhook_url,
                        data=dict(params),
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded",
                            "X-Twilio-Signature": signature,
                        },
                    )
                    if resp.status_code == 200:
                        logger.info(f"Injected SMS from {from_number}: {body_text[:50]}")
                        return {"ok": True, "status": resp.status_code}
                    else:
                        logger.warning(f"Webhook returned {resp.status_code}: {resp.text}")
                        return {"ok": False, "status": resp.status_code, "error": resp.text}
            except httpx.ConnectError as e:
                logger.warning(f"Cannot connect to bot webhook: {e}")
                return {"ok": False, "error": str(e)}

        @app.get("/_sent_messages")
        async def get_sent_messages():
            return self._sent_messages

        @app.post("/_clear")
        async def clear_state():
            self._sent_messages.clear()
            logger.info("Cleared all mock server state")
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
        logger.info(f"Twilio Mock server started at http://{self.host}:{self.port}")
        return thread


def uuid_hex() -> str:
    """Generate a short hex string for IDs."""
    import uuid as _uuid
    return _uuid.uuid4().hex[:24]


def main():
    server = MockTwilioServer()
    server.start_background()
    try:
        import time as _time
        while True:
            _time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
