#!/usr/bin/env python3
"""
Slack Mock Server - FastAPI + WebSocket 实现的 Slack Socket Mode Mock 服务

模拟 Slack Socket Mode (WebSocket) 和 Web API，用于测试 octos Slack bot 集成。

端口: 5003 (默认)
端点:
  - POST /api/apps.connections.open - Slack API: 获取 WebSocket URL
  - POST /api/chat.postMessage - Slack API: 发送消息
  - GET /health - 健康检查
  - POST /_inject - 注入测试事件（通过 WebSocket 推送）
  - GET /_sent_messages - 获取 bot 发送的消息
  - POST /_clear - 清理状态

WebSocket:
  - ws://127.0.0.1:5003/ws - Slack Socket Mode WebSocket 连接
"""

import time
import uuid
import sys
import logging
import asyncio
from typing import Optional, Dict, List
from pathlib import Path
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from starlette.websockets import WebSocketState

# Configure logging
logger = logging.getLogger("mock_slack")


class MockSlackServer:
    """Mock Slack server with FastAPI and WebSocket support for Socket Mode."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 5003):
        self.host = host
        self.port = port
        self._sent_messages: list[dict] = []
        self._injected_events: list[dict] = []
        self._transactions: list[dict] = []
        self._txn_counter = 0
        
        # WebSocket connections (octos clients)
        self._ws_connections: List[WebSocket] = []
        
        # Create FastAPI app
        self.app = FastAPI(title="Slack Mock Server")
        self._setup_routes()
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        return f"E{uuid.uuid4().hex[:16]}"
    
    def _next_txn_id(self) -> str:
        """Generate next transaction ID."""
        self._txn_counter += 1
        return f"T{self._txn_counter:06d}"
    
    async def _broadcast_to_websockets(self, message: dict):
        """Broadcast a message to all connected WebSocket clients."""
        import json
        disconnected = []
        
        for ws in self._ws_connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(json.dumps(message))
                    logger.info(f"📤 Sent event to WebSocket client: {message.get('type', 'unknown')}")
            except Exception as e:
                logger.error(f"❌ Failed to send to WebSocket: {e}")
                disconnected.append(ws)
        
        # Remove disconnected clients
        for ws in disconnected:
            if ws in self._ws_connections:
                self._ws_connections.remove(ws)
    
    def _setup_routes(self):
        """Set up FastAPI routes."""
        app = self.app
        
        @app.get("/health")
        async def health():
            """Health check endpoint."""
            return JSONResponse({
                "status": "ok", 
                "service": "slack-mock-server",
                "ws_connections": len(self._ws_connections)
            })
        
        @app.post("/api/auth.test")
        async def auth_test(request: Request):
            """
            Slack API: Test authentication and get bot user info.
            
            This is called by octos to verify the bot token and get the bot user ID.
            """
            try:
                # Check authorization header
                auth = request.headers.get("authorization", "")
                if not auth.startswith("Bearer "):
                    raise HTTPException(status_code=401, detail="Missing Bearer token")
                
                token = auth[7:]  # Remove "Bearer " prefix
                
                # In mock mode, accept any token starting with "xoxb-"
                if not token.startswith("xoxb-"):
                    logger.warning(f"⚠ Invalid bot token format: {token[:10]}...")
                
                logger.info(f"🔑 auth.test called with token: {token[:10]}...")
                
                # Return mock auth test response with user_id
                response = {
                    "ok": True,
                    "url": "https://testworkspace.slack.com/",
                    "team": "Test Workspace",
                    "user": "testbot",
                    "team_id": "T012AB3CD",
                    "user_id": "U0BOTUSERID",  # ← Critical: must include user_id
                    "bot_id": "B012AB3CD",
                    "is_enterprise_install": False,
                }
                
                logger.info(f"✅ Returning auth.test response with user_id=U0BOTUSERID")
                return JSONResponse(response)
            
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"❌ Error in auth.test: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/api/apps.connections.open")
        async def apps_connections_open(request: Request):
            """
            Slack API: Get WebSocket URL for Socket Mode.
            
            This is called by octos to establish a Socket Mode connection.
            Returns a WebSocket URL that points to our mock server.
            """
            try:
                # Log all request details for debugging
                auth = request.headers.get("authorization", "")
                logger.info(f"🔑 apps.connections.open received - Authorization: {auth[:20] if auth else 'MISSING'}...")
                
                # Check authorization header
                if not auth.startswith("Bearer "):
                    logger.warning(f"⚠ Missing Bearer token in apps.connections.open")
                    return JSONResponse({"ok": False, "error": "invalid_auth"}, status_code=200)
                
                token = auth[7:]  # Remove "Bearer " prefix
                logger.info(f"🔑 apps.connections.open token: {token[:10]}...")
                
                # In mock mode, accept any token starting with "xapp-"
                if not token.startswith("xapp-"):
                    logger.warning(f"⚠ Invalid app token format: {token[:10]}...")
                    return JSONResponse({"ok": False, "error": "invalid_auth"}, status_code=200)
                
                logger.info(f"✅ Token validated successfully")
                
                # Return WebSocket URL pointing to our server
                ws_url = f"ws://{self.host}:{self.port}/ws"
                
                response = {
                    "ok": True,
                    "url": ws_url,
                }
                
                logger.info(f"✅ Returning WebSocket URL: {ws_url}")
                return JSONResponse(response)
            
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"❌ Error in apps.connections.open: {e}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/api/chat.postMessage")
        async def chat_post_message(request: Request):
            """
            Slack API: Send a message to a channel.
            
            This is called by octos to send bot responses.
            We record the message for test verification.
            """
            try:
                # Check authorization header
                auth = request.headers.get("authorization", "")
                if not auth.startswith("Bearer "):
                    logger.warning(f"⚠ Missing Bearer token in chat.postMessage")
                    raise HTTPException(status_code=401, detail="invalid_auth")
                
                token = auth[7:]  # Remove "Bearer " prefix
                
                # In mock mode, accept any token starting with "xoxb-"
                if not token.startswith("xoxb-"):
                    logger.warning(f"⚠ Invalid bot token format: {token[:10]}...")
                    raise HTTPException(status_code=401, detail="invalid_auth")
                
                logger.info(f"🔑 chat.postMessage called with token: {token[:10]}...")
                
                # Parse form data or JSON
                content_type = request.headers.get("content-type", "")
                if "application/json" in content_type:
                    body = await request.json()
                else:
                    form_data = await request.form()
                    body = dict(form_data)
                
                channel = body.get("channel", "unknown")
                text = body.get("text", "")
                
                logger.info(f"💬 Bot sent message to channel={channel}: {text[:100]}")
                
                # Record the message
                message_record = {
                    "channel": channel,
                    "text": text,
                    "timestamp": time.time(),
                    "token_prefix": token[:10],
                }
                self._sent_messages.append(message_record)
                
                # Generate a fake message TS (timestamp)
                ts = str(time.time())
                
                response = {
                    "ok": True,
                    "channel": channel,
                    "ts": ts,
                    "message": {
                        "text": text,
                        "ts": ts,
                    }
                }
                
                return JSONResponse(response)
            
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"❌ Error in chat.postMessage: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """
            Slack Socket Mode WebSocket endpoint.
            
            octos connects here after calling apps.connections.open.
            We send events through this connection.
            """
            await websocket.accept()
            self._ws_connections.append(websocket)
            logger.info(f"🔌 WebSocket client connected. Total connections: {len(self._ws_connections)}")
            
            try:
                while True:
                    # Receive messages from octos (acks, etc.)
                    data = await websocket.receive_text()
                    
                    # Log but don't process (in real Slack, this would be acks)
                    logger.debug(f"📨 Received from WebSocket: {data[:100]}")
            
            except WebSocketDisconnect:
                logger.info("🔌 WebSocket client disconnected")
            except Exception as e:
                logger.error(f"❌ WebSocket error: {e}")
            finally:
                if websocket in self._ws_connections:
                    self._ws_connections.remove(websocket)
                logger.info(f"🔌 WebSocket connection closed. Remaining: {len(self._ws_connections)}")
        
        @app.post("/_inject")
        async def inject_event(request: Request):
            """
            Inject a test event into the mock server.
            
            The event will be pushed to all connected WebSocket clients (octos).
            """
            try:
                body = await request.json()
                text = body.get("text", "")
                channel = body.get("channel", "C012AB3CD")
                user = body.get("user", "U012AB3CD")
                
                # 支持外部传入 event_id（去重测试）
                event_id = body.get("event_id") or self._generate_event_id()
                
                # Create a Slack Socket Mode envelope
                envelope = {
                    "envelope_id": event_id,
                    "payload": {
                        "token": "test_token",
                        "team_id": "T012AB3CD",
                        "api_app_id": "A012AB3CD",
                        "event": {
                            "type": "message",
                            "text": text,
                            "user": user,
                            "channel": channel,
                            "ts": str(time.time()),
                            "event_ts": str(time.time()),
                        },
                        "type": "event_callback",
                        "event_id": event_id,
                        "event_time": int(time.time()),
                        "authorizations": [
                            {
                                "enterprise_id": None,
                                "team_id": "T012AB3CD",
                                "user_id": user,
                                "is_bot": False,
                                "is_enterprise_install": False,
                            }
                        ],
                    },
                    "type": "events_api",
                    "accepts_response_payload": False,
                }
                
                # Store the injected event
                self._injected_events.append(envelope)
                
                logger.info(f"🔔 Injected event: channel={channel}, text={text[:50]}")
                
                # Broadcast to all connected WebSocket clients
                await self._broadcast_to_websockets(envelope)
                
                return JSONResponse({
                    "success": True,
                    "event_id": envelope["envelope_id"],
                    "note": "Event injected and broadcast to WebSocket clients"
                })
            
            except Exception as e:
                logger.error(f"❌ Error injecting event: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/_sent_messages")
        async def get_sent_messages():
            """Get all messages sent by the bot."""
            return JSONResponse(self._sent_messages)
        
        @app.post("/_clear")
        async def clear_state():
            """Clear all stored state."""
            self._sent_messages.clear()
            self._injected_events.clear()
            self._transactions.clear()
            self._txn_counter = 0
            logger.info("🗑 Cleared all mock server state")
            return JSONResponse({"success": True})
        
        @app.get("/_transactions")
        async def get_transactions():
            """Get all received transactions (for debugging)."""
            return JSONResponse(self._transactions)
        
        @app.get("/_stats")
        async def get_stats():
            """Get mock server statistics."""
            return JSONResponse({
                "sent_messages": len(self._sent_messages),
                "injected_events": len(self._injected_events),
                "transactions": len(self._transactions),
                "ws_connections": len(self._ws_connections),
            })
    
    def start_background(self, log_file=None):
        """Start the server in a background thread."""
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Configure logging to both file and stdout
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            # File handler
            file_handler = logging.FileHandler(log_file, mode='a')
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.INFO)
            
            # Stdout handler
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setFormatter(formatter)
            stdout_handler.setLevel(logging.INFO)
            
            # Configure root logger
            root_logger = logging.getLogger()
            root_logger.addHandler(file_handler)
            root_logger.addHandler(stdout_handler)
            root_logger.setLevel(logging.INFO)
            
            # Configure uvicorn loggers
            uvicorn_logger = logging.getLogger("uvicorn")
            uvicorn_logger.addHandler(file_handler)
            uvicorn_logger.addHandler(stdout_handler)
            uvicorn_logger.setLevel(logging.INFO)
            
            uvicorn_access_logger = logging.getLogger("uvicorn.access")
            uvicorn_access_logger.addHandler(file_handler)
            uvicorn_access_logger.addHandler(stdout_handler)
            uvicorn_access_logger.setLevel(logging.INFO)
            
            uvicorn_error_logger = logging.getLogger("uvicorn.error")
            uvicorn_error_logger.addHandler(file_handler)
            uvicorn_error_logger.addHandler(stdout_handler)
            uvicorn_error_logger.setLevel(logging.INFO)
        
        # Start uvicorn server
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False,
        )


if __name__ == "__main__":
    server = MockSlackServer(port=5003)
    server.start_background()
