#!/usr/bin/env python3
"""
WhatsApp Mock Server - FastAPI + WebSocket 实现，模拟 whatsapp-bridge

模拟 WhatsApp Baileys bridge 的 WebSocket 协议，用于测试 octos WhatsApp Bot 集成。

端口: 5006 (默认)
端点:
  - GET /health - 健康检查
  - POST /_inject - 注入测试事件（通过 WebSocket 推送）
  - GET /_sent_messages - 获取 bot 发送的消息
  - POST /_clear - 清理状态

WebSocket:
  - ws://127.0.0.1:5006/ws - WhatsApp bridge WebSocket 连接
    - 入站（bridge → octos）：
      {"type":"message","sender":"1234567890@s.whatsapp.net","chatId":"1234567890","content":"Hello","messageId":"...","timestamp":...}
    - 出站（octos → bridge）：
      {"type":"send","to":"1234567890@s.whatsapp.net","text":"Hi there"}
      或 {"type":"typing","to":"1234567890@s.whatsapp.net"}
"""

import time
import uuid
import json
import logging
import sys
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn
from starlette.websockets import WebSocketState
from starlette.requests import Request

logger = logging.getLogger("mock_whatsapp")


class MockWhatsAppServer:
    """Mock WhatsApp bridge server with FastAPI and WebSocket."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5006):
        self.host = host
        self.port = port
        self._sent_messages: list[dict] = []
        self._injected_events: list[dict] = []
        self._ws_connections: list[WebSocket] = []

        self.app = FastAPI(title="WhatsApp Mock Server")
        self._setup_routes()

    def _generate_message_id(self) -> str:
        return f"wa_mock_{uuid.uuid4().hex[:16]}"

    async def _broadcast_to_websockets(self, message: dict):
        """Broadcast message to all connected WebSocket clients."""
        disconnected = []
        for ws in self._ws_connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(json.dumps(message))
                    logger.info(f"📤 Sent event via WebSocket: {message.get('type', 'unknown')}")
            except Exception as e:
                logger.error(f"❌ Failed to send to WebSocket: {e}")
                disconnected.append(ws)

        for ws in disconnected:
            if ws in self._ws_connections:
                self._ws_connections.remove(ws)

    def _setup_routes(self):
        app = self.app

        @app.get("/health")
        async def health():
            """Health check endpoint."""
            return JSONResponse({
                "status": "ok",
                "service": "whatsapp-mock-server",
                "ws_connections": len(self._ws_connections),
            })

        @app.post("/_inject")
        async def inject_event(request: Request):
            """
            Inject a test event — simulates WhatsApp bridge pushing a message.

            Body:
            {
                "text": "Hello",
                "sender": "1234567890@s.whatsapp.net",
                "chat_id": "1234567890",       # optional, defaults to sender's phone part
                "message_type": "message"       # optional: "message" (default), "image", "audio"
            }
            """
            raw = await request.body()
            body = json.loads(raw)
            text = body.get("text", "")
            sender = body.get("sender", "test_user@s.whatsapp.net")

            # Determine chat_id: use provided, or fall back to phone part of JID
            chat_id = body.get("chat_id")
            if not chat_id:
                chat_id = sender.split("@")[0]

            message_type = body.get("message_type", "message")
            # 支持外部传入 message_id（去重测试需要）
            message_id = body.get("message_id") or self._generate_message_id()

            if message_type == "image":
                event = {
                    "type": "message",
                    "sender": sender,
                    "chatId": chat_id,
                    "content": text,
                    "messageId": message_id,
                    "timestamp": int(time.time() * 1000),
                    "media": [{"url": "https://mock.example.com/test.jpg", "mimetype": "image/jpeg"}],
                }
            elif message_type == "audio":
                event = {
                    "type": "message",
                    "sender": sender,
                    "chatId": chat_id,
                    "content": "",
                    "messageId": message_id,
                    "timestamp": int(time.time() * 1000),
                    "mediaUrl": "https://mock.example.com/test.ogg",
                    "mimetype": "audio/ogg",
                }
            else:
                event = {
                    "type": "message",
                    "sender": sender,
                    "chatId": chat_id,
                    "content": text,
                    "messageId": message_id,
                    "timestamp": int(time.time() * 1000),
                }

            self._injected_events.append(event)
            logger.info(f"📥 Injected event: type={message_type} sender={sender}")

            await self._broadcast_to_websockets(event)
            return JSONResponse({"status": "injected", "message_id": message_id})

        @app.get("/_sent_messages")
        async def get_sent_messages():
            """Get all messages sent by the bot (via WebSocket from octos)."""
            return JSONResponse(self._sent_messages)

        @app.post("/_clear")
        async def clear_state():
            """Clear all stored state."""
            self._sent_messages.clear()
            self._injected_events.clear()
            return JSONResponse({"status": "cleared"})

        @app.post("/_ws_disconnect")
        async def ws_disconnect():
            """Simulate network disconnection: close all WebSocket connections."""
            import starlette.websockets as _ws_state
            count = 0
            for ws in list(self._ws_connections):
                try:
                    if ws.client_state != _ws_state.WebSocketState.DISCONNECTED:
                        await ws.close(code=1001, reason="Test disconnect")
                        count += 1
                except Exception:
                    pass
            self._ws_connections.clear()
            logger.info(f"🔌 Disconnected {count} WebSocket connections")
            return JSONResponse({"disconnected": count})

        @app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket):
            await ws.accept()
            self._ws_connections.append(ws)
            logger.info(f"🔗 WebSocket client connected (total: {len(self._ws_connections)})")

            # Send a "ready" status event to indicate the bridge is connected
            await ws.send_text(json.dumps({"type": "status", "jid": "bot@s.whatsapp.net", "status": "connected"}))

            try:
                while True:
                    raw = await ws.receive_text()
                    msg = json.loads(raw)
                    msg_type = msg.get("type", "")

                    if msg_type == "send":
                        self._sent_messages.append(msg)
                        logger.info(f"📩 Bot sent message to {msg.get('to')}: {msg.get('text', '')[:60]}")
                    elif msg_type == "typing":
                        logger.info(f"✏️ Bot typing indicator to {msg.get('to')}")
                    else:
                        logger.info(f"❓ Unknown message type from bot: {msg_type}")

            except WebSocketDisconnect:
                logger.info("🔌 WebSocket client disconnected")
            except Exception as e:
                logger.error(f"⚠️ WebSocket error: {e}")
            finally:
                if ws in self._ws_connections:
                    self._ws_connections.remove(ws)
                logger.info(f"WebSocket cleaned up (total: {len(self._ws_connections)})")

    def start_background(self, log_file: Optional[str] = None):
        """Start the mock server in the background (used by test_run.py)."""
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
    logging.basicConfig(level=logging.INFO)
    server = MockWhatsAppServer()
    print(f"Starting WhatsApp Mock Server on ws://{server.host}:{server.port}/ws")
    server.start_background()
