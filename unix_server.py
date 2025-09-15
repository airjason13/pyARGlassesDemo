import asyncio
import os
from typing import Optional
from global_def import *

# ---------------- Unix Socket Server ----------------
class UnixServer:
    def __init__(self, path: str = UNIX_MSG_SERVER_URI, recv_callback=None):
        self.path = path
        self._server: Optional[asyncio.base_events.Server] = None
        self._task: Optional[asyncio.Task] = None
        self.recv_callback = recv_callback


    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        # print(f"[UnixServer] + Connection {addr}")
        log.debug("[UnixServer] + Connection %s", addr)
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                msg = data.decode(errors="ignore")
                # print(f"[UnixServer]   Received: {msg}")
                log.debug("[UnixServer] + Received: %s", msg)
                '''try signal/slot'''
                if self.recv_callback is not None:
                    self.recv_callback(msg)
                writer.write(f"{msg} OK".encode())
                await writer.drain()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # print(f"[UnixServer] ! Error: {e}")
            log.debug(e)
        finally:
            # print(f"[UnixServer] - Close {addr}")
            log.debug("[UnixServer] + Close: %s", addr)
            writer.close()
            await writer.wait_closed()

    async def start(self):
        # 確保不存在舊 socket 檔案
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass

        self._server = await asyncio.start_unix_server(self._handle_client, path=self.path)
        log.debug("[UnixServer] Serving at %s", self.path)
        self._task = asyncio.create_task(self._server.serve_forever())

    async def stop(self):
        if self._server is not None:
            # print("[UnixServer] Shutting down...")
            log.debug("[UnixServer] Shutting down...")
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        # 移除 socket 檔案
        try:
            os.unlink(self.path)
            log.debug("[UnixServer] Shutting down...unlink ok")
        except FileNotFoundError:
            pass