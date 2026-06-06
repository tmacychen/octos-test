#!/usr/bin/env python3
"""
QQ Bot Mock Server - FastAPI + WebSocket 实现的 QQ Bot Gateway Mock 服务

模拟 QQ Bot 官方 API v2（WebSocket Gateway + REST API），用于测试 octos QQ Bot 集成。

端口: 5010 (默认)
端点:
  - POST /app/getAppAccessToken - QQ Bot API: 获取 access_token
  - GET /gateway - QQ Bot API: 获取 WebSocket Gateway URL
  - POST /v2/groups/{group_openid}/messages - QQ Bot API: 发送群消息
  - POST /v2/users/{user_openid}/messages - QQ Bot API: 发送 C2C 消息
  - GET /health - 健康检查
  - POST /_inject - 注入测试事件（通过 WebSocket 推送）
  - GET /_sent_messages - 获取 bot 发送的消息
  - POST /_clear - 清理状态

WebSocket:
  - ws://127.0.0.1:5010/ws - QQ Bot Gateway WebSocket 连接
"""

import json
import time
import uuid
import sys
import logging
from typing import List, Optional
from pathlib import Path
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from starlette.websockets import WebSocketState

logger = logging.getLogger("mock_qq")


class MockQqServer:
    """Mock QQ Bot server with FastAPI and WebSocket support."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5010):
        self.host = host
        self.port = port
        self._sent_messages: list[dict] = []
        self._injected_events: list[dict] = []
        self._seq_counter = 0
        self._ws_connections: List[WebSocket] = []

        self.app = FastAPI(title="QQ Bot Mock Server")
        self._setup_routes()

    def _next_seq(self) -> int:
        self._seq_counter += 1
        return self._seq_counter

    async def _broadcast_to_websockets(self, message: dict):
        """Broadcast a message to all connected WebSocket clients."""
        disconnected = []
        for ws in self._ws_connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(json.dumps(message))
                    logger.info(f"Sent event to WS client: op={message.get('op')} t={message.get('t', '')}")
            except Exception as e:
                logger.error(f"Failed to send to WebSocket: {e}")
                disconnected.append(ws)
        for ws in disconnected:
            if ws in self._ws_connections:
                self._ws_connections.remove(ws)

    def _setup_routes(self):
        app = self.app

        # ── QQ Bot API endpoints ──

        @app.post("/app/getAppAccessToken")
        async def get_access_token(request: Request):
            """QQ Bot API: 获取 access_token"""
            body = await request.json()
            app_id = body.get("appId", "")
            client_secret = body.get("clientSecret", "")
            logger.info(f"getAppAccessToken called: appId={app_id[:8]}...")

            return JSONResponse({
                "access_token": "mock_access_token_12345",
                "expires_in": "7200",
            })

        @app.get("/gateway")
        async def get_gateway(request: Request):
            """QQ Bot API: 获取 WebSocket Gateway URL"""
            auth = request.headers.get("authorization", "")
            logger.info(f"gateway called: auth={auth[:20]}...")

            ws_url = f"ws://{self.host}:{self.port}/ws"
            return JSONResponse({"url": ws_url})

        @app.post("/v2/groups/{group_openid}/messages")
        async def send_group_message(group_openid: str, request: Request):
            """QQ Bot API: 发送群消息 — 记录 bot 回复"""
            body = await request.json()
            content = body.get("content", "")
            msg_type = body.get("msg_type", 0)
            msg_seq = body.get("msg_seq", 0)
            msg_id = body.get("msg_id")

            logger.info(f"Bot sent group msg to {group_openid}: {content[:80]}")

            message_record = {
                "chat_id": group_openid,
                "text": content,
                "msg_type": msg_type,
                "msg_seq": msg_seq,
                "msg_id": msg_id,
                "timestamp": time.time(),
            }
            self._sent_messages.append(message_record)

            return JSONResponse({
                "id": f"msg_{int(time.time())}",
                "timestamp": str(int(time.time())),
            })

        @app.post("/v2/users/{user_openid}/messages")
        async def send_c2c_message(user_openid: str, request: Request):
            """QQ Bot API: 发送 C2C 私聊消息 — 记录 bot 回复"""
            body = await request.json()
            content = body.get("content", "")
            msg_type = body.get("msg_type", 0)
            msg_seq = body.get("msg_seq", 0)
            msg_id = body.get("msg_id")

            logger.info(f"Bot sent C2C msg to {user_openid}: {content[:80]}")

            message_record = {
                "chat_id": user_openid,
                "sender_id": user_openid,
                "text": content,
                "msg_type": msg_type,
                "msg_seq": msg_seq,
                "msg_id": msg_id,
                "timestamp": time.time(),
            }
            self._sent_messages.append(message_record)

            return JSONResponse({
                "id": f"msg_{int(time.time())}",
                "timestamp": str(int(time.time())),
            })

        # ── WebSocket endpoint ──

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """QQ Bot Gateway WebSocket endpoint."""
            await websocket.accept()
            self._ws_connections.append(websocket)
            logger.info(f"WS client connected. Total: {len(self._ws_connections)}")

            # Send OpCode 10 (Hello) to start handshake
            hello_frame = {
                "op": 10,
                "d": {"heartbeat_interval": 41250},
            }
            await websocket.send_text(json.dumps(hello_frame))
            logger.info("Sent Hello (op=10) to client")

            try:
                while True:
                    data = await websocket.receive_text()
                    try:
                        frame = json.loads(data)
                        op = frame.get("op")

                        if op == 2:
                            # Identify — respond with READY
                            logger.info("Received Identify (op=2)")
                            ready_frame = {
                                "op": 0,
                                "s": self._next_seq(),
                                "t": "READY",
                                "d": {"session_id": f"session_{uuid.uuid4().hex[:8]}"},
                            }
                            await websocket.send_text(json.dumps(ready_frame))
                            logger.info("Sent READY dispatch")

                        elif op == 1:
                            # Heartbeat — respond with ACK
                            logger.debug("Received Heartbeat (op=1)")
                            ack_frame = {"op": 11}
                            await websocket.send_text(json.dumps(ack_frame))

                        elif op == 6:
                            # Resume — respond with RESUMED
                            logger.info("Received Resume (op=6)")
                            resumed_frame = {
                                "op": 0,
                                "s": self._next_seq(),
                                "t": "RESUMED",
                                "d": {},
                            }
                            await websocket.send_text(json.dumps(resumed_frame))

                    except json.JSONDecodeError:
                        logger.warning(f"Malformed WS frame: {data[:100]}")

            except WebSocketDisconnect:
                logger.info("WS client disconnected")
            except Exception as e:
                logger.error(f"WS error: {e}")
            finally:
                if websocket in self._ws_connections:
                    self._ws_connections.remove(websocket)
                logger.info(f"WS connection closed. Remaining: {len(self._ws_connections)}")

        # ── Test control endpoints ──

        @app.get("/health")
        async def health():
            return JSONResponse({
                "status": "ok",
                "service": "qq-bot-mock-server",
                "ws_connections": len(self._ws_connections),
            })

        @app.post("/_inject")
        async def inject_event(request: Request):
            """注入测试事件，通过 WebSocket 推送给 octos。"""
            body = await request.json()
            text = body.get("text", "")
            event_type = body.get("event_type", "GROUP_AT_MESSAGE_CREATE")
            group_openid = body.get("group_openid", "group_test_001")
            member_openid = body.get("member_openid", "member_test_001")
            user_openid = body.get("user_openid")
            message_id = body.get("message_id") or f"msg_{uuid.uuid4().hex[:12]}"

            # Build dispatch data based on event type
            if event_type == "C2C_MESSAGE_CREATE":
                d = {
                    "id": message_id,
                    "author": {
                        "id": user_openid or member_openid,
                        "user_openid": user_openid or member_openid,
                    },
                    "content": text,
                }
            else:
                # GROUP_AT_MESSAGE_CREATE
                d = {
                    "id": message_id,
                    "group_openid": group_openid,
                    "author": {"member_openid": member_openid},
                    "content": text,
                }

            dispatch_frame = {
                "op": 0,
                "s": self._next_seq(),
                "t": event_type,
                "d": d,
            }

            self._injected_events.append(dispatch_frame)
            logger.info(f"Injected event: {event_type} text={text[:50]}")

            # Broadcast to all WS clients
            await self._broadcast_to_websockets(dispatch_frame)

            return JSONResponse({
                "success": True,
                "event_id": message_id,
                "note": "Event injected and broadcast to WebSocket clients",
            })

        @app.get("/_sent_messages")
        async def get_sent_messages():
            return JSONResponse(self._sent_messages)

        @app.post("/_clear")
        async def clear_state():
            self._sent_messages.clear()
            self._injected_events.clear()
            self._seq_counter = 0
            logger.info("Cleared all mock server state")
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

        @app.get("/_stats")
        async def get_stats():
            return JSONResponse({
                "sent_messages": len(self._sent_messages),
                "injected_events": len(self._injected_events),
                "ws_connections": len(self._ws_connections),
            })

    def start_background(self, log_file=None):
        """Start the server (blocking, for use in subprocess)."""
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
    server = MockQqServer(port=5010)
    server.start_background()
