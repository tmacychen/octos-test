#!/usr/bin/env python3
"""
WeCom (企业微信自建应用) Mock Server - FastAPI 实现

模拟 WeCom 服务器的 REST API 和加密回调，用于测试 octos wecom 通道。

架构:
  Mock Server (port 5009)  ── REST API ──→  octos gateway
  octos webhook (port 9323)  ←── 加密回调 ──  Mock Server (_inject 时)

端点:
  - GET  /health             - 健康检查
  - GET  /cgi-bin/gettoken   - 获取 access_token
  - POST /cgi-bin/message/send - 发送消息（捕获 octos 的回复）
  - POST /_inject            - 注入测试事件（加密后 POST octos webhook）
  - GET  /_sent_messages     - 获取 octos 发送的消息
  - POST /_clear             - 清理状态
  - GET  /_subscribe_state   - 获取订阅状态
"""

import time
import uuid
import sys
import json
import logging
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from starlette.requests import Request
import uvicorn
import httpx

from wecom_crypto import (
    build_text_xml,
    encrypt_wecom_message,
    verify_wecom_signature,
    decode_aes_key,
)

logger = logging.getLogger("mock_wecom")


class MockWeComServer:
    """Mock WeCom (企业微信自建应用) server with FastAPI."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5009,
        corp_id: str = "test_corp_id",
        agent_id: str = "test_agent",
        verification_token: str = "test_verification_token",
        encoding_aes_key: str = "5sYHlCoSGoM55cptBeBF48DRmOZbeYowtPcgwjRQSxc",
    ):
        self.host = host
        self.port = port
        self.corp_id = corp_id
        self.agent_id = agent_id
        self.verification_token = verification_token
        self.encoding_aes_key = encoding_aes_key
        self.aes_key = decode_aes_key(encoding_aes_key)
        self._sent_messages: list[dict] = []
        self._injected_events: list[dict] = []
        self._token = f"mock_access_token_{uuid.uuid4().hex[:16]}"
        self._octos_webhook_url: Optional[str] = None

        self.app = FastAPI(title="WeCom Mock Server")
        self._setup_routes()

    def _setup_routes(self):
        app = self.app

        @app.get("/health")
        async def health():
            return JSONResponse({
                "status": "ok",
                "service": "wecom-mock-server",
                "sent_messages": len(self._sent_messages),
            })

        # ── WeCom REST API 端点 ────────────────────────────────────────────

        @app.get("/cgi-bin/gettoken")
        async def get_token(
            corpid: str = Query(None),
            corpsecret: str = Query(None),
        ):
            logger.info(f"🔑 Token request: corpid={corpid}")
            return JSONResponse({
                "errcode": 0,
                "errmsg": "ok",
                "access_token": self._token,
                "expires_in": 7200,
            })

        @app.post("/cgi-bin/message/send")
        async def send_message(request: Request):
            try:
                body = await request.json()
                body_str = json.dumps(body, ensure_ascii=False)
                self._sent_messages.append({
                    "body": body,
                    "timestamp": time.time(),
                })
                logger.info(
                    f"💬 Message captured: touser={body.get('touser', '')}, "
                    f"content={str(body.get('markdown', body.get('text', {})))[:80]}"
                )
                return JSONResponse({
                    "errcode": 0,
                    "errmsg": "ok",
                    "invaliduser": "",
                })
            except Exception as e:
                logger.error(f"Error in send_message: {e}")
                return JSONResponse({"errcode": -1, "errmsg": str(e)})

        @app.get("/cgi-bin/media/get")
        async def media_get(
            access_token: str = Query(None),
            media_id: str = Query(None),
        ):
            return JSONResponse({
                "errcode": 0,
                "errmsg": "ok",
                "media_id": media_id or "mock_media_id",
            })

        @app.post("/cgi-bin/media/upload")
        async def media_upload(
            access_token: str = Query(None),
            type: str = Query(None),
        ):
            media_id = f"mock_media_{uuid.uuid4().hex[:16]}"
            return JSONResponse({
                "errcode": 0,
                "errmsg": "ok",
                "type": type or "image",
                "media_id": media_id,
                "created_at": str(int(time.time())),
            })

        # ── 测试辅助端点 ────────────────────────────────────────────────────

        @app.get("/_sent_messages")
        async def get_sent_messages():
            return JSONResponse({
                "messages": self._sent_messages,
                "total": len(self._sent_messages),
            })

        @app.post("/_clear")
        async def clear_state():
            self._sent_messages.clear()
            self._injected_events.clear()
            logger.info("Cleared all mock server state")
            return JSONResponse({"success": True})

        @app.get("/_config")
        async def get_config():
            return JSONResponse({
                "corp_id": self.corp_id,
                "agent_id": self.agent_id,
                "verification_token": self.verification_token,
                "encoding_aes_key": self.encoding_aes_key,
                "aes_key_hex": self.aes_key.hex(),
                "octos_webhook_url": self._octos_webhook_url,
            })

        @app.post("/_inject")
        async def inject_event(request: Request):
            """
            Inject a test event by simulating a WeCom server callback.

            This encrypts the message XML and POSTs it to the octos webhook
            endpoint, exactly as the real WeCom server would.

            Body format:
            {
                "text": "hello",             # 消息内容
                "sender": "user123",         # FromUserName
                "webhook_url": "http://127.0.0.1:9323/wecom/webhook",  # octos webhook
            }
            """
            import json as _json
            try:
                raw = await request.body()
                body = _json.loads(raw)
                text = body.get("text", "")
                sender = body.get("sender", "test_user")
                webhook_url = body.get("webhook_url")
                if webhook_url:
                    self._octos_webhook_url = webhook_url

                if not webhook_url and not self._octos_webhook_url:
                    raise HTTPException(
                        status_code=400,
                        detail="webhook_url required on first call"
                    )

                actual_webhook = webhook_url or self._octos_webhook_url

                # Build XML message
                msg_id = str(uuid.uuid4())
                xml = build_text_xml(sender, text, msg_id=msg_id)
                logger.info(f"📄 XML payload:\n{xml}")

                # Encrypt
                ciphertext, base64_encrypted = encrypt_wecom_message(
                    xml, self.aes_key, self.corp_id
                )
                timestamp = str(int(time.time()))
                nonce = uuid.uuid4().hex[:8]

                # Compute signature
                msg_signature = verify_wecom_signature(
                    self.verification_token, timestamp, nonce, base64_encrypted
                )

                # POST to octos webhook (as form data or query params)
                callback_params = {
                    "msg_signature": msg_signature,
                    "timestamp": timestamp,
                    "nonce": nonce,
                }

                logger.info(
                    f"📤 POST to {actual_webhook} with "
                    f"msg_signature={msg_signature[:12]}..., "
                    f"timestamp={timestamp}, nonce={nonce}"
                )

                # WeCom expects XML body with <Encrypt> field
                xml_body = f"""<xml>
<ToUserName><![CDATA[{self.corp_id}]]></ToUserName>
<AgentID><![CDATA[{self.agent_id}]]></AgentID>
<Encrypt><![CDATA[{base64_encrypted}]]></Encrypt>
</xml>"""

                logger.info(f"🔐 Encrypted base64 ({len(base64_encrypted)} chars): {base64_encrypted[:60]}...")
                logger.info(f"🔐 XML body ({len(xml_body)} chars): {xml_body[:150]}...")
                logger.info(f"📤 POST params: {callback_params}")

                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        actual_webhook,
                        params=callback_params,
                        content=xml_body,
                        headers={"Content-Type": "text/xml"},
                    )
                    logger.info(
                        f"📥 Webhook response: {resp.status_code} {resp.text[:200]}"
                    )

                event_info = {
                    "sender": sender,
                    "text": text,
                    "msg_id": msg_id,
                    "webhook_url": actual_webhook,
                    "webhook_status": resp.status_code,
                    "webhook_response": resp.text[:200],
                }
                self._injected_events.append(event_info)

                return JSONResponse({
                    "success": resp.status_code == 200,
                    "event": event_info,
                    "callback_params": callback_params,
                })

            except Exception as e:
                logger.error(f"Error injecting event: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def start_background(self, log_file=None):
        """Start the server in background thread."""
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler = logging.FileHandler(log_file, mode='a')
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.INFO)
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setFormatter(formatter)
            stdout_handler.setLevel(logging.INFO)

            root_logger = logging.getLogger()
            root_logger.addHandler(file_handler)
            root_logger.addHandler(stdout_handler)
            root_logger.setLevel(logging.INFO)

        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False,
        )


if __name__ == "__main__":
    server = MockWeComServer(port=5009)
    server.start_background()
