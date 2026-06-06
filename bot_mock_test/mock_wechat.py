#!/usr/bin/env python3
"""
微信 Mock Server - FastAPI + WebSocket 实现，模拟 wechat-bridge

模拟 wechat-bridge 的 WebSocket 协议，用于测试 octos 微信 Bot 集成。

端口: 5005 (默认)
端点:
  - GET /health - 健康检查
  - POST /_inject - 注入测试事件（通过 WebSocket 推送）
  - GET /_sent_messages - 获取 bot 发送的消息
  - POST /_clear - 清理状态

WebSocket:
  - ws://127.0.0.1:5005/ws - wechat-bridge WebSocket 连接
    - 入站（bridge → octos）：{"type":"message","sender":"xxx@im.wechat","content":"...","context_token":"...","message_id":"..."}
    - 出站（octos → bridge）：{"type":"send","to":"xxx@im.wechat","text":"...","context_token":"..."}
"""

import time
import uuid
import sys
import json
import logging
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from starlette.websockets import WebSocketState
from starlette.requests import Request

logger = logging.getLogger("mock_wechat")


class MockWeChatServer:
    """Mock WeChat bridge server with FastAPI and WebSocket."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5005):
        self.host = host
        self.port = port
        self._sent_messages: list[dict] = []
        self._injected_events: list[dict] = []
        self._ws_connections: list[WebSocket] = []

        self.app = FastAPI(title="WeChat Mock Server")
        self._setup_routes()

    def _generate_message_id(self) -> str:
        return f"mock_msg_{uuid.uuid4().hex[:16]}"

    def _generate_context_token(self) -> str:
        return f"ctx_{uuid.uuid4().hex[:24]}"

    async def _broadcast_to_websockets(self, message: dict):
        """广播消息到所有连接的 WebSocket 客户端。"""
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
                "service": "wechat-mock-server",
                "ws_connections": len(self._ws_connections),
            })

        @app.post("/_inject")
        async def inject_event(request: Request):
            """
            注入测试事件——模拟 wechat-bridge 推送微信消息。
            """
            import json as _json
            try:
                raw = await request.body()
                body = _json.loads(raw)
                text = body.get("text", "")
                sender = body.get("sender", "test_user@im.wechat")

                message_id = body.get("message_id") or self._generate_message_id()
                context_token = self._generate_context_token()

                event = {
                    "type": "message",
                    "sender": sender,
                    "content": text,
                    "context_token": context_token,
                    "message_id": message_id,
                }

                self._injected_events.append(event)
                logger.info(f"🔔 Injected WeChat event: sender={sender}, text={text[:50]}")

                # 通过 WebSocket 推送给 octos
                await self._broadcast_to_websockets(event)

                return JSONResponse({
                    "success": True,
                    "event": event,
                    "note": "Event injected and broadcast via WebSocket"
                })

            except Exception as e:
                logger.error(f"❌ Error injecting event: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/_sent_messages")
        async def get_sent_messages():
            """获取 bot 发送的所有消息。"""
            return JSONResponse(self._sent_messages)

        @app.post("/_clear")
        async def clear_state():
            """清理所有状态（保留 WebSocket 连接）。"""
            self._sent_messages.clear()
            self._injected_events.clear()
            # 不清理 WebSocket 连接，gateway 会自己管理重连
            logger.info("🗑 Cleared all mock server state (preserved WS connections)")
            return JSONResponse({"success": True})

        @app.post("/_ws_disconnect")
        async def ws_disconnect():
            """模拟网络断线：断开所有 WebSocket 连接。"""
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
        async def websocket_endpoint(websocket: WebSocket):
            """
            wechat-bridge WebSocket 端点。

            octos 连接到这里接收和发送微信消息。
            """
            await websocket.accept()
            self._ws_connections.append(websocket)
            logger.info(f"🔌 WebSocket client connected. Total: {len(self._ws_connections)}")

            try:
                while True:
                    data = await websocket.receive_text()
                    try:
                        msg = json.loads(data)
                        msg_type = msg.get("type", "")

                        if msg_type == "send":
                            # octos 发送回复给用户
                            to = msg.get("to", "")
                            text = msg.get("text", "")
                            context_token = msg.get("context_token", "")

                            record = {
                                "type": "send",
                                "to": to,
                                "text": text,
                                "context_token": context_token,
                                "timestamp": time.time(),
                            }
                            self._sent_messages.append(record)
                            logger.info(f"💬 Bot sent to {to}: {text[:80]}")

                        else:
                            logger.debug(f"📨 Unknown message type: {msg_type}")

                    except json.JSONDecodeError:
                        logger.warning(f"⚠ Invalid JSON received: {data[:100]}")

            except WebSocketDisconnect:
                logger.info("🔌 WebSocket client disconnected")
            except Exception as e:
                logger.error(f"❌ WebSocket error: {e}")
            finally:
                if websocket in self._ws_connections:
                    self._ws_connections.remove(websocket)
                logger.info(f"🔌 WebSocket closed. Remaining: {len(self._ws_connections)}")

    def start_background(self, log_file=None):
        """在后台线程启动服务器。"""
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
    server = MockWeChatServer(port=5005)
    server.start_background()
