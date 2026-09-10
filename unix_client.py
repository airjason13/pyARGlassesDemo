import asyncio
import os
import socket
from typing import Optional
from global_def import *


class UnixClient:
    def __init__(self, path: str = "/tmp/ipc_socket.sock"):
        self.path = path
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.snd_size = UNIX_SOCKET_BUFFER_SIZE # 4 * 1024 * 1024  # 4 MiB
        self.rcv_size = UNIX_SOCKET_BUFFER_SIZE # 4 * 1024 * 1024

        self._send_lock = asyncio.Lock()

    async def connect(self):
        log.debug("[UnixClient] Connecting...")
        self.reader = None
        self.writer = None
        try:
            self.reader, self.writer = await asyncio.open_unix_connection(self.path)
            sock = self.writer.get_extra_info("socket")
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.snd_size)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.rcv_size)
            log.debug(f"[UnixClient] Connected to {self.path}")
        except Exception as e:
            log.debug(f"[UnixClient] Failed to connect to {self.path}: {e}")

    async def reconnect(self):
        log.debug("[UnixClient] Reconnecting...")
        await self.close()
        log.debug("[UnixClient] Connect")
        await self.connect()

    async def send(self, msg: str):
        async with self._send_lock:
            try:
                if (
                        self.reader is None
                        or self.writer is None
                        or self.writer.is_closing()
                ):
                    await self.connect()

                if self.reader is None or self.writer is None:
                    log.error("[UnixClient] Not connected")
                    return -1

                encoded_msg = msg.encode("utf-8")

                log.debug(
                    f"[UnixClient] Send len: {len(encoded_msg)}"
                )

                self.writer.write(encoded_msg)

                await asyncio.wait_for(
                    self.writer.drain(),
                    timeout=3.0,
                )

                data = await asyncio.wait_for(
                    self.reader.read(self.rcv_size),
                    timeout=3.0,
                )

                if not data:
                    log.warning(
                        "[UnixClient] Connection closed by peer"
                    )
                    await self.close()
                    return -1

                log.debug(
                    f"[UnixClient] Received len: {len(data)}"
                )

                return 0

            except asyncio.TimeoutError:
                log.error("[UnixClient] Send/receive timeout")
                await self.close()
                return -1

            except asyncio.CancelledError:
                log.debug("[UnixClient] Send cancelled")
                raise

            except Exception:
                log.exception("[UnixClient] Send failed")
                await self.close()
                return -1

    async def close(self):
        if self.writer is not None:
            log.debug("[UnixClient] Closing")
            try:
                self.writer.close()
                # ✅ 加超時，且容忍 loop 已停止/錯誤情況
                await asyncio.wait_for(self.writer.wait_closed(), timeout=1.0)
            except (asyncio.TimeoutError, RuntimeError) as e:
                # RuntimeError: loop 已經停止或不是同一個 loop
                log.debug(f"[UnixClient] wait_closed skipped: {e}")
            except Exception as e:
                log.debug(f"[UnixClient] close error: {e}")
        self.writer = None
        self.reader = None
