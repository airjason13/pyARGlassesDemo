import asyncio
import signal

from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QApplication
from PyQt5.QtCore import Qt, QTimer
from unix_server import UnixServer
from unix_client import UnixClient

from global_def import *

class CMainWindow(QMainWindow):
    def __init__(self, async_loop):
        super().__init__()
        log.debug("MainWindow up!")
        self.async_loop = async_loop
        self.initUI()
        self.unix_server = UnixServer(UNIX_DEMO_APP_SERVER_URI, self.unix_server_recv_cb)
        self.msg_unix_client = UnixClient(path=UNIX_MSG_SERVER_URI)
        QTimer.singleShot(0, lambda: asyncio.create_task(self.unix_server.start()))
        QTimer.singleShot(0, lambda: asyncio.create_task(self.msg_unix_client.connect()))

        signal.signal(signal.SIGINT, self.stop_server)

        # === 測試用 新增：每 5 秒觸發一次 test_send_unix_msg ===
        self.timer = QTimer(self)
        self.timer.setInterval(5000)  # 5 秒
        self.timer.timeout.connect(self._periodic_unix_msg)
        self.timer.start()


    # def _periodic_unix_msg(self, data: bytes):
    def _periodic_unix_msg(self):
        """
        QTimer 觸發時呼叫，安排 coroutine 到 asyncio 事件迴圈
        """
        log.debug("")
        asyncio.run_coroutine_threadsafe(
            self.test_send_unix_msg("Demo App Alive"),
            self.async_loop
        )

    async def test_send_unix_msg(self, unix_msg):
        log.debug("test_unix_loop")
        if unix_msg is not None:
            await self.msg_unix_client.send(unix_msg)

    # def init_msg_unix_client(self):
    #    self.msg_unix_client = UnixClient(path=UNIX_MSG_SERVER_URI)

    def unix_server_recv_cb(self, msg):
        log.debug("msg: %s", msg)
        self.label.setText("這是 PyQt5 Demo 全螢幕無邊框主視窗" + "\n" + msg)

    def initUI(self):
        # 設定視窗為全螢幕、無邊框、無標題列
        # self.setWindowFlags(Qt.FramelessWindowHint)
        # self.showFullScreen()

        # 中央 Widget
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: black;")
        layout = QVBoxLayout()

        # 簡單放一個標籤測試
        self.label = QLabel("這是 PyQt5 Demo 全螢幕無邊框主視窗")
        self.label.setStyleSheet("color: green;")
        self.label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.label)
        central_widget.setLayout(layout)

        self.setCentralWidget(central_widget)

    async def stop_server(self):
        """關閉 UnixServer"""
        await self.unix_server.stop()
        asyncio.get_event_loop().stop()

    def keyPressEvent(self, event):
        """按下 Esc 鍵退出程式"""
        if event.key() == Qt.Key_Escape:
            asyncio.create_task(self.shutdown_and_quit())


    # ---- 關閉流程：非同步 ----
    async def shutdown_and_quit(self):
        try:
            await self.unix_server.stop()  # 修正成 unix_server
        finally:
            app = QApplication.instance()
            if app is not None:
                app.quit()  # 結束 Qt 應用，qasync 的事件圈也會跟著結束

    def closeEvent(self, event):
        # 確保在關閉時也會收斂 server；非阻塞丟給事件圈
        asyncio.create_task(self.unix_server.stop())
        event.accept()