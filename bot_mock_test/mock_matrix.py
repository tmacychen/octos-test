#!/usr/bin/env python3
"""
Matrix Mock Server for Testing

Simulates a Matrix Homeserver's Appservice API and Client-Server API
so that octos Matrix channel can connect and exchange messages without
real Matrix credentials.

Architecture
~~~~~~~~~~~~
::

  octos bot (MatrixChannel)
    │
    ├── PUT /_matrix/app/v1/transactions/{txnId}
    │      ← Homeserver pushes events to appservice
    │
    ├── POST /_matrix/client/v3/rooms/{roomId}/send/m.room.message/{txnId}
    │      → Appservice sends messages to rooms
    │
    ├── POST /_matrix/client/v3/register
    │      → Appservice registers virtual users
    │
    └── GET /_matrix/client/v3/rooms/{roomId}/joined_members
           → Get room members

Control endpoints (not part of Matrix API):
  POST /_inject          inject a user message event
  GET  /_sent_messages   return all messages sent by the bot
  POST /_clear           clear stored messages & state

Extensibility hooks for future Matrix-specific features:
  - Bot management: /_inject_bot_command
  - Swarm supervisor: /_inject_swarm_event
  - Room routing: /_inject_room_invite
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from threading import Thread

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

DEFAULT_ROOM_ID = "!test:localhost"
DEFAULT_SENDER = "@user:localhost"
DEFAULT_HOMESERVER = "localhost"


@dataclass
class SentMessage:
    """A message sent by the bot via Client-Server API."""
    room_id: str
    content: dict
    event_id: str = ""
    msgtype: str = "m.text"


@dataclass
class InjectedMessage:
    """A message injected by test scripts to be dispatched as m.room.message."""
    text: str
    room_id: str = DEFAULT_ROOM_ID
    sender: str = DEFAULT_SENDER
    msgtype: str = "m.text"
    formatted_body: Optional[str] = None
    event_id: Optional[str] = None  # 可选，用于去重测试


@dataclass
class RegisteredUser:
    """A virtual user registered by the appservice."""
    user_id: str
    device_id: str = ""
    access_token: str = ""


# ---------------------------------------------------------------------------
# Mock server
# ---------------------------------------------------------------------------

class MockMatrixServer:
    """
    Mock Matrix Homeserver.

    Provides:
    - **Appservice API** endpoints that octos MatrixChannel receives events from
    - **Client-Server API** endpoints that octos uses to send messages
    - **Control endpoints** for test injection and inspection
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5002):
        self.host = host
        self.port = port
        self.app = FastAPI(title="Matrix Mock Homeserver")

        self._setup_routes()

        # State
        self._sent_messages: List[SentMessage] = []
        self._injected_messages: List[InjectedMessage] = []
        self._transactions: List[Dict[str, Any]] = []
        self._registered_users: Dict[str, RegisteredUser] = {}
        self._room_members: Dict[str, List[str]] = {}  # room_id -> [user_ids]

        # Bot info - use env vars for tokens to match gateway config
        self._bot_user_id = os.environ.get("MOCK_BOT_USER_ID", "@bot:localhost")
        self._as_token = os.environ.get("MOCK_AS_TOKEN", "test_token")
        self._hs_token = os.environ.get("MOCK_HS_TOKEN", "test_secret")

        # Transaction counter
        self._txn_counter = 0

        # Appservice endpoint (where octos listens for events)
        # In real setup, octos starts its own HTTP server; here we store
        # events and let octos poll or we push directly
        self._appservice_endpoint: Optional[str] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_txn_id(self) -> str:
        self._txn_counter += 1
        return str(self._txn_counter)

    def _generate_event_id(self) -> str:
        return f"${uuid.uuid4().hex[:16]}"

    def _setup_routes(self):
        app = self.app

        # ====== Health check ======

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        # ====== Appservice API (Homeserver → Appservice) ======

        @app.put("/_matrix/app/v1/transactions/{txn_id}")
        async def receive_transaction(txn_id: str, request: Request):
            """Homeserver pushes events to appservice.

            In real Matrix, the homeserver calls this on the appservice.
            In tests, we use this endpoint to verify octos receives events.
            """
            body = await request.json()
            self._transactions.append({
                "txn_id": txn_id,
                "events": body.get("events", []),
            })
            return JSONResponse({})

        # ====== Client-Server API (Appservice → Homeserver) ======

        @app.put("/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}")
        @app.post("/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}")
        async def send_room_message(room_id: str, txn_id: str, request: Request):
            """Appservice sends a message to a room."""
            body = await request.json()
            event_id = self._generate_event_id()

            logger.info(f"📨 Bot send_room_message: room={room_id}, txn_id={txn_id}, body={body}")

            # Auto-join the room if bot is not already a member
            if room_id not in self._room_members:
                self._room_members[room_id] = [DEFAULT_SENDER, self._bot_user_id]
            elif self._bot_user_id not in self._room_members[room_id]:
                self._room_members[room_id].append(self._bot_user_id)

            sent = SentMessage(
                room_id=room_id,
                content=body,
                event_id=event_id,
                msgtype=body.get("msgtype", "m.text"),
            )
            self._sent_messages.append(sent)

            logger.debug(f"🤖 Bot sent message to {room_id}: {body.get('body', '')[:50]}")

            return JSONResponse({
                "event_id": event_id,
            })

        @app.put("/_matrix/client/v3/rooms/{room_id}/send/m.room.member/{txn_id}")
        @app.post("/_matrix/client/v3/rooms/{room_id}/send/m.room.member/{txn_id}")
        async def send_room_member(room_id: str, txn_id: str, request: Request):
            """Appservice sends a membership event (invite, join, etc.)."""
            body = await request.json()
            event_id = self._generate_event_id()
            return JSONResponse({"event_id": event_id})

        @app.post("/_matrix/client/v3/register")
        async def register_user(request: Request):
            """Appservice registers a virtual user."""
            body = await request.json()
            user_id = body.get("username", f"bot_{uuid.uuid4().hex[:8]}")
            if not user_id.startswith("@"):
                user_id = f"@{user_id}:{DEFAULT_HOMESERVER}"

            user = RegisteredUser(
                user_id=user_id,
                device_id=uuid.uuid4().hex[:10],
                access_token=uuid.uuid4().hex,
            )
            self._registered_users[user_id] = user

            logger.debug(f"👤 Registered virtual user: {user_id}")

            return JSONResponse({
                "user_id": user_id,
                "device_id": user.device_id,
                "access_token": user.access_token,
            })

        @app.get("/_matrix/client/v3/rooms/{room_id}/joined_members")
        async def get_joined_members(room_id: str):
            """Get joined members of a room."""
            members = self._room_members.get(room_id, [DEFAULT_SENDER, self._bot_user_id])
            return JSONResponse({
                "joined": {m: {"display_name": m.split(":")[0].lstrip("@")} for m in members}
            })

        @app.get("/_matrix/client/v3/account/whoami")
        async def whoami(request: Request):
            """Return current user info."""
            return JSONResponse({
                "user_id": self._bot_user_id,
                "device_id": "mock_device",
            })

        # ====== Control endpoints (not part of Matrix API) ======

        @app.post("/_inject")
        async def inject_message(request: Request):
            """Inject a user message event.

            This simulates the homeserver pushing a m.room.message event
            to the appservice.
            """
            body = await request.json()
            injected = InjectedMessage(
                text=body.get("text", ""),
                room_id=body.get("room_id", DEFAULT_ROOM_ID),
                sender=body.get("sender", DEFAULT_SENDER),
                msgtype=body.get("msgtype", "m.text"),
                formatted_body=body.get("formatted_body"),
                event_id=body.get("event_id"),
            )
            self._injected_messages.append(injected)

            # Construct a Matrix event
            event = {
                "type": "m.room.message",
                "room_id": injected.room_id,
                "sender": injected.sender,
                "event_id": injected.event_id or self._generate_event_id(),
                "origin_server_ts": int(time.time() * 1000),
                "content": {
                    "msgtype": injected.msgtype,
                    "body": injected.text,
                },
            }
            if injected.formatted_body:
                event["content"]["formatted_body"] = injected.formatted_body
                event["content"]["format"] = "org.matrix.custom.html"

            # Store the event as a transaction for octos to poll
            txn_id = self._next_txn_id()
            self._transactions.append({
                "txn_id": txn_id,
                "events": [event],
            })

            # 🔥 CRITICAL: Push to octos appservice endpoint if configured
            # In real setup, homeserver pushes to appservice; in tests,
            # we can either poll or push directly
            if self._appservice_endpoint:
                try:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        logger.info(f"🔔 Pushing event to appservice: {txn_id}")
                        resp = await client.put(
                            f"{self._appservice_endpoint}/_matrix/app/v1/transactions/{txn_id}",
                            json={"events": [event]},
                            headers={"Authorization": f"Bearer {self._hs_token}"},
                            timeout=5,
                        )
                        logger.info(f"🔔 Appservice push response: {resp.status_code}")
                except Exception as e:
                    logger.warning(f"Failed to push to appservice: {e}")

            return JSONResponse({"success": True, "txn_id": txn_id, "event": event})

        @app.get("/_sent_messages")
        async def get_sent_messages():
            """Return all messages sent by the bot."""
            return JSONResponse([
                {
                    "room_id": m.room_id,
                    "content": m.content,
                    "event_id": m.event_id,
                    "msgtype": m.msgtype,
                    "text": m.content.get("body", ""),
                }
                for m in self._sent_messages
            ])

        @app.post("/_clear")
        async def clear_state():
            """Clear all stored state."""
            self._sent_messages.clear()
            self._injected_messages.clear()
            self._transactions.clear()
            self._registered_users.clear()
            self._room_members.clear()
            self._txn_counter = 0
            return JSONResponse({"success": True})

        @app.get("/_transactions")
        async def get_transactions():
            """Return all received transactions (for debugging)."""
            return JSONResponse(self._transactions)

        # ====== Extensibility hooks for future features ======

        @app.post("/_inject_bot_command")
        async def inject_bot_command(request: Request):
            """Inject a bot management command (/createbot, /deletebot, /listbots).

            Simulates the Matrix appservice receiving slash commands from users.
            The command is injected as a regular message event that will be
            processed by octos's handle_slash_command logic.
            """
            body = await request.json()
            command = body.get("command", "")
            room_id = body.get("room_id", DEFAULT_ROOM_ID)
            sender = body.get("sender", DEFAULT_SENDER)

            if not command.startswith("/"):
                return JSONResponse({"error": "Command must start with /"}, status_code=400)

            # Inject the command as a regular message event
            injected = InjectedMessage(
                text=command,
                room_id=room_id,
                sender=sender,
                msgtype="m.text",
            )
            self._injected_messages.append(injected)

            # Construct a Matrix event
            event = {
                "type": "m.room.message",
                "room_id": room_id,
                "sender": sender,
                "event_id": self._generate_event_id(),
                "origin_server_ts": int(time.time() * 1000),
                "content": {
                    "msgtype": "m.text",
                    "body": command,
                },
            }

            # Store the event as a transaction for octos to process
            txn_id = self._next_txn_id()
            self._transactions.append({
                "txn_id": txn_id,
                "events": [event],
            })

            # Push to octos appservice endpoint if configured
            if self._appservice_endpoint:
                try:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        logger.info(f"🔔 Pushing bot command to appservice: {command}")
                        resp = await client.put(
                            f"{self._appservice_endpoint}/_matrix/app/v1/transactions/{txn_id}",
                            json={"events": [event]},
                            headers={"Authorization": f"Bearer {self._hs_token}"},
                            timeout=5,
                        )
                        logger.info(f"🔔 Appservice push response: {resp.status_code}")
                except Exception as e:
                    logger.warning(f"Failed to push to appservice: {e}")

            return JSONResponse({
                "success": True,
                "txn_id": txn_id,
                "command": command,
                "note": "Bot command injected as message event"
            })

        @app.post("/_inject_room_invite")
        async def inject_room_invite(request: Request):
            """Inject a room invite event.

            Simulates a user being invited to a Matrix room. Updates room
            membership and optionally pushes an m.room.member event to octos.
            """
            body = await request.json()
            room_id = body.get("room_id", DEFAULT_ROOM_ID)
            user_id = body.get("user_id", DEFAULT_SENDER)
            inviter = body.get("inviter", self._bot_user_id)

            # Update room members
            if room_id not in self._room_members:
                self._room_members[room_id] = []
            if user_id not in self._room_members[room_id]:
                self._room_members[room_id].append(user_id)

            # Optionally create a membership event
            if body.get("push_event", False):
                event = {
                    "type": "m.room.member",
                    "room_id": room_id,
                    "sender": inviter,
                    "state_key": user_id,
                    "event_id": self._generate_event_id(),
                    "origin_server_ts": int(time.time() * 1000),
                    "content": {
                        "membership": "invite",
                        "displayname": user_id.split(":")[0].lstrip("@"),
                    },
                }

                txn_id = self._next_txn_id()
                self._transactions.append({
                    "txn_id": txn_id,
                    "events": [event],
                })

                # Push to octos if configured
                if self._appservice_endpoint:
                    try:
                        import httpx
                        async with httpx.AsyncClient() as client:
                            await client.put(
                                f"{self._appservice_endpoint}/_matrix/app/v1/transactions/{txn_id}",
                                json={"events": [event]},
                                headers={"Authorization": f"Bearer {self._hs_token}"},
                                timeout=5,
                            )
                    except Exception as e:
                        logger.warning(f"Failed to push invite event: {e}")

            return JSONResponse({
                "success": True,
                "room_id": room_id,
                "user_id": user_id,
                "members": self._room_members.get(room_id, [])
            })

        @app.post("/_inject_swarm_event")
        async def inject_swarm_event(request: Request):
            """Inject a swarm harness event (M7.3 supervisor feature).

            Simulates a sub-agent sending a typed harness event to the swarm room.
            This tests the route_subagent_event functionality.
            """
            body = await request.json()
            session_id = body.get("session_id", "test-session")
            agent_label = body.get("agent_label", "claude-code")
            event_type = body.get("event_type", "progress")  # progress, error, complete, etc.
            room_id = body.get("room_id", f"!swarm_{session_id}:localhost")

            # Generate puppet user ID
            puppet_user_id = f"@octos_swarm_{session_id}_{agent_label}:localhost"

            # Create harness event payload
            event_payload = {
                "schema": "octos.harness.event.v1",
                "kind": event_type,
                "agent_label": agent_label,
                "session_id": session_id,
                "event": body.get("event_data", {
                    "phase": "fetch_sources",
                    "message": "Fetching data...",
                    "progress": 0.5,
                }),
            }

            # Format as Matrix message
            summary = f"{event_type} {event_payload['event'].get('phase', '')}"
            envelope_pretty = json.dumps(event_payload, indent=2)

            sent = SentMessage(
                room_id=room_id,
                content={
                    "msgtype": "m.text",
                    "body": summary,
                    "formatted_body": f"<pre>{envelope_pretty}</pre>",
                    "format": "org.matrix.custom.html",
                },
                event_id=self._generate_event_id(),
                msgtype="m.text",
            )
            self._sent_messages.append(sent)

            logger.info(f"🕸️ Swarm event routed: {session_id}/{agent_label} - {event_type}")

            return JSONResponse({
                "success": True,
                "event_id": sent.event_id,
                "puppet_user_id": puppet_user_id,
                "room_id": room_id,
            })

        @app.post("/_inject_supervisor_reply")
        async def inject_supervisor_reply(request: Request):
            """Inject a supervisor reply to a swarm room (M7.3 supervisor feature).

            Simulates a human supervisor replying to a specific puppet in the swarm room.
            This tests the handle_supervisor_reply functionality.
            """
            body = await request.json()
            room_id = body.get("room_id", f"!swarm_test:localhost")
            sender = body.get("sender", "@alice:localhost")
            message = body.get("message", "")
            target_puppet = body.get("target_puppet", "")  # Optional: explicitly target a puppet

            # If target_puppet specified, add mention to message
            if target_puppet and not target_puppet.startswith("@"):
                target_puppet = f"@{target_puppet}:localhost"
            
            if target_puppet and target_puppet not in message:
                message = f"{target_puppet} {message}"

            # Inject as regular message
            injected = InjectedMessage(
                text=message,
                room_id=room_id,
                sender=sender,
                msgtype="m.text",
            )
            self._injected_messages.append(injected)

            event = {
                "type": "m.room.message",
                "room_id": room_id,
                "sender": sender,
                "event_id": self._generate_event_id(),
                "origin_server_ts": int(time.time() * 1000),
                "content": {
                    "msgtype": "m.text",
                    "body": message,
                },
            }

            txn_id = self._next_txn_id()
            self._transactions.append({
                "txn_id": txn_id,
                "events": [event],
            })

            # Push to octos if configured
            if self._appservice_endpoint:
                try:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        await client.put(
                            f"{self._appservice_endpoint}/_matrix/app/v1/transactions/{txn_id}",
                            json={"events": [event]},
                            headers={"Authorization": f"Bearer {self._hs_token}"},
                            timeout=5,
                        )
                except Exception as e:
                    logger.warning(f"Failed to push supervisor reply: {e}")

            logger.info(f"👤 Supervisor reply injected: {sender} → {room_id}")

            return JSONResponse({
                "success": True,
                "txn_id": txn_id,
                "message": message,
                "target_puppet": target_puppet,
            })

    # ------------------------------------------------------------------
    # Public API for programmatic use
    # ------------------------------------------------------------------

    def get_sent_messages(self) -> List[SentMessage]:
        return self._sent_messages.copy()

    def get_transactions(self) -> List[Dict[str, Any]]:
        return self._transactions.copy()

    def set_appservice_endpoint(self, endpoint: str):
        """Set the octos appservice endpoint for push delivery."""
        self._appservice_endpoint = endpoint

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    def start(self) -> Thread:
        """Start the mock server in a background thread."""
        return self.start_background()

    def start_background(self, log_file=None, appservice_endpoint=None):
        """Start the server in a background thread.

        Args:
            log_file: Path to log file (optional)
            appservice_endpoint: URL of the octos appservice endpoint for push delivery.
                                 If not provided, checks OCTOS_APPSERVICE_URL env var.
        """
        if appservice_endpoint is None:
            appservice_endpoint = os.environ.get("OCTOS_APPSERVICE_URL")

        if appservice_endpoint:
            self.set_appservice_endpoint(appservice_endpoint)
            logger.info(f"🎯 Appservice endpoint configured: {appservice_endpoint}")

        if log_file:
            from pathlib import Path
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

        def run():
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="warning",
                timeout_keep_alive=60,
                limit_concurrency=100,
            )

        thread = Thread(target=run, daemon=True)
        thread.start()
        logger.info(f"🚀 Mock Matrix server started on http://{self.host}:{self.port}")
        return thread


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Matrix Mock Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=5002, help="Port to bind")
    args = parser.parse_args()

    server = MockMatrixServer(host=args.host, port=args.port)
    server.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Mock Matrix server stopped")
