"""
adapters/protocols/websocket.py
WebSocket client adapter for ORIGAMI — real-time bidirectional communication.
Supports: auto-reconnect, message queuing, heartbeat, event dispatch.

Dependencies:
    pip install websockets
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

# Handler type: async functions that receive a parsed message dict
MessageHandler = Callable[[dict[str, Any]], Coroutine]


class WebSocketError(Exception):
    """Raised on unrecoverable WebSocket failures."""


class WebSocketClient:
    """
    Async WebSocket client with auto-reconnect, heartbeat, and event routing.

    Usage:
        client = WebSocketClient("ws://localhost:8000/ws")

        @client.on("robot_status")
        async def handle_status(msg):
            print("Robot status:", msg)

        await client.connect()
        await client.send({"type": "subscribe", "topic": "robot_status"})
        await client.listen()   # blocks until disconnected

    The 'type' field in each message is used for event routing.
    """

    def __init__(
        self,
        url: str,
        max_retries: int = 5,
        retry_delay: float = 2.0,
        heartbeat_interval: float = 30.0,
        reconnect: bool = True,
        ping_message: Optional[dict] = None,
    ) -> None:
        """
        Args:
            url: WebSocket server URL (ws:// or wss://).
            max_retries: Maximum reconnection attempts (0 = unlimited).
            retry_delay: Seconds between reconnection attempts.
            heartbeat_interval: Seconds between ping messages (0 = disabled).
            reconnect: Automatically reconnect on disconnect.
            ping_message: JSON payload to send as heartbeat (defaults to {"type": "ping"}).
        """
        self.url = url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.heartbeat_interval = heartbeat_interval
        self.reconnect = reconnect
        self.ping_message = ping_message or {"type": "ping"}

        self._ws = None
        self._handlers: dict[str, list[MessageHandler]] = defaultdict(list)
        self._global_handlers: list[MessageHandler] = []
        self._send_queue: asyncio.Queue = asyncio.Queue()
        self._connected = False
        self._should_stop = False
        self._retry_count = 0

    # ------------------------------------------------------------------
    # Event Registration
    # ------------------------------------------------------------------

    def on(self, event_type: str) -> Callable:
        """
        Decorator to register a handler for a specific message type.

        Usage:
            @client.on("robot_status")
            async def handler(msg: dict): ...
        """
        def decorator(func: MessageHandler) -> MessageHandler:
            self._handlers[event_type].append(func)
            return func
        return decorator

    def on_any(self, func: MessageHandler) -> MessageHandler:
        """Register a handler for ALL incoming messages."""
        self._global_handlers.append(func)
        return func

    # ------------------------------------------------------------------
    # Connection Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Establish the WebSocket connection."""
        try:
            import websockets
        except ImportError:
            raise WebSocketError("websockets not installed. Run: pip install websockets")

        logger.info("Connecting to WebSocket: %s", self.url)
        self._ws = await websockets.connect(
            self.url,
            ping_interval=None,  # we manage heartbeat ourselves
        )
        self._connected = True
        self._retry_count = 0
        logger.info("WebSocket connected to %s.", self.url)

    async def disconnect(self) -> None:
        """Gracefully close the connection."""
        self._should_stop = True
        self._connected = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("WebSocket disconnected.")

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    async def send(self, message: dict[str, Any]) -> None:
        """
        Send a JSON message to the server.

        Args:
            message: Dict to serialize and send.
        """
        if not self._connected or self._ws is None:
            raise WebSocketError("Not connected. Call connect() first.")
        payload = json.dumps(message)
        await self._ws.send(payload)
        logger.debug("WS sent: %s", payload[:200])

    async def send_queued(self, message: dict[str, Any]) -> None:
        """Queue a message for sending (thread-safe alternative)."""
        await self._send_queue.put(message)

    # ------------------------------------------------------------------
    # Main listen loop
    # ------------------------------------------------------------------

    async def listen(self) -> None:
        """
        Main event loop: receives messages, dispatches to handlers.
        Runs until disconnect() is called or max_retries is exceeded.
        """
        while not self._should_stop:
            try:
                await self._run_session()
            except Exception as exc:
                if self._should_stop:
                    break
                logger.warning("WebSocket disconnected: %s", exc)
                if not self.reconnect:
                    raise

                self._retry_count += 1
                if self.max_retries and self._retry_count > self.max_retries:
                    raise WebSocketError(
                        f"Max retries ({self.max_retries}) exceeded."
                    ) from exc

                delay = self.retry_delay * (2 ** min(self._retry_count - 1, 5))
                logger.info(
                    "Reconnecting in %.1fs (attempt %d/%s)...",
                    delay,
                    self._retry_count,
                    self.max_retries or "∞",
                )
                await asyncio.sleep(delay)
                await self.connect()

    async def _run_session(self) -> None:
        """Inner loop for a single connected session."""
        tasks = [
            asyncio.create_task(self._receive_loop()),
            asyncio.create_task(self._send_loop()),
        ]
        if self.heartbeat_interval > 0:
            tasks.append(asyncio.create_task(self._heartbeat_loop()))

        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_EXCEPTION
        )
        for task in pending:
            task.cancel()

        # Re-raise any exception from completed tasks
        for task in done:
            exc = task.exception()
            if exc:
                raise exc

    async def _receive_loop(self) -> None:
        """Continuously receive and dispatch messages."""
        async for raw in self._ws:
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Received non-JSON message: %s", str(raw)[:100])
                continue

            logger.debug("WS received: %s", str(message)[:200])
            await self._dispatch(message)

    async def _send_loop(self) -> None:
        """Drain the send queue and push messages to the server."""
        while True:
            message = await self._send_queue.get()
            await self.send(message)

    async def _heartbeat_loop(self) -> None:
        """Send periodic ping messages to keep the connection alive."""
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            try:
                await self.send(self.ping_message)
                logger.debug("WS heartbeat sent.")
            except Exception as exc:
                logger.warning("Heartbeat failed: %s", exc)
                raise  # Trigger reconnect

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, message: dict[str, Any]) -> None:
        """Route an incoming message to registered handlers."""
        # Global handlers
        for handler in self._global_handlers:
            try:
                await handler(message)
            except Exception as exc:
                logger.error("Global WS handler error: %s", exc)

        # Type-specific handlers
        event_type = message.get("type", "")
        for handler in self._handlers.get(event_type, []):
            try:
                await handler(message)
            except Exception as exc:
                logger.error("WS handler error for type %r: %s", event_type, exc)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None


# ------------------------------------------------------------------
# Simple synchronous wrapper for non-async contexts
# ------------------------------------------------------------------

class SyncWebSocketClient:
    """
    Blocking wrapper around WebSocketClient for use in synchronous code.

    Usage:
        client = SyncWebSocketClient("ws://localhost:8000/ws")
        client.start()  # blocks in background thread
        client.send_sync({"type": "hello"})
        client.stop()
    """

    def __init__(self, url: str, **kwargs) -> None:
        self._async_client = WebSocketClient(url, **kwargs)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread = None

    def on(self, event_type: str) -> Callable:
        return self._async_client.on(event_type)

    def start(self) -> None:
        """Start the WebSocket client in a background thread."""
        import threading

        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._async_client.connect())
            self._loop.run_until_complete(self._async_client.listen())

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        time.sleep(0.5)  # Allow connection to establish

    def send_sync(self, message: dict[str, Any]) -> None:
        """Send a message from synchronous context."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_client.send_queued(message), self._loop
            )

    def stop(self) -> None:
        """Stop the client."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_client.disconnect(), self._loop
            )