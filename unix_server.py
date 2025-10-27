import asyncio
import os
import socket
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

from global_def import *

# ---------------- Unix Socket Server ----------------
class UnixServer(QObject):
    unix_data_received = pyqtSignal(str, int)
    def __init__(self, path: str = UNIX_MSG_SERVER_URI):
        super().__init__()
        self.path = path
        self._server: Optional[asyncio.base_events.Server] = None
        self._task: Optional[asyncio.Task] = None
        self.snd_size = UNIX_SOCKET_BUFFER_SIZE # 4 * 1024 * 1024  # 4 MiB
        self.rcv_size = UNIX_SOCKET_BUFFER_SIZE # 4 * 1024 * 1024


    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        sock = writer.get_extra_info("socket")
        peer_info = "unknown"
        if sock:
            try:
                sock = self.writer.get_extra_info("socket")
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.snd_size)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.rcv_size)
                uid, gid = sock.getpeereid()
                peer_info = f"uid={uid}, gid={gid}"
            except AttributeError:
                import struct, socket as s
                creds = sock.getsockopt(s.SOL_SOCKET, s.SO_PEERCRED, struct.calcsize('3i'))
                pid, uid, gid = struct.unpack('3i', creds)
                peer_info = f"pid={pid}, uid={uid}, gid={gid}"

        log.debug("[UnixServer] + Connection from %s", peer_info)
        try:
            while True:
                data = await reader.read(UNIX_SOCKET_BUFFER_SIZE)
                if not data:
                    break
                msg = data.decode(errors="ignore")
                # print(f"[UnixServer]   Received: {msg}")
                log.debug("[UnixServer] + Received: %s", msg)


                writer.write(f"{msg} OK".encode())
                await writer.drain()
                self.unix_data_received.emit(msg, peer_info)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # print(f"[UnixServer] ! Error: {e}")
            log.debug(e)
        finally:
            # print(f"[UnixServer] - Close {addr}")
            log.debug("[UnixServer] + Close: %s", peer_info)
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