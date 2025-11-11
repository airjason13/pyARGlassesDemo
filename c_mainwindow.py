import asyncio
import enum
import signal

from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QApplication, QStackedLayout
from PyQt5.QtCore import Qt, QTimer

from ui_pages.ui_eng_test_page import EngPage
from ui_pages.ui_playlist_page import PlaylistPage
from unix_server import UnixServer
from unix_client import UnixClient
from cmd_parser import CmdParser
from global_def import *
from ui_pages.ui_media_page import MediaPage
from ui_pages.ui_video_setting_page import VideoSettingPage

class PageListEnum(enum.IntEnum):
    Media = 0
    Playlist = 1
    Video_Setting = 2
    Eng = 3

Page_Select_Btn_Name_List = ["Media", "Playlist" ,"Video_Setting", "Eng"]
Page_List = [MediaPage, # 0
             PlaylistPage, # 1
             VideoSettingPage, # 2
             EngPage, # 3
             ]

# Page_Map = dict(zip(Page_Select_Btn_Name_List, Page_List))

class CMainWindow(QMainWindow):
    TEST_FLAG = False # For Eng Page Show socket cmd
    def __init__(self, async_loop):
        super().__init__()
        self.playlist_mgr = None
        self.label = None
        log.debug("MainWindow up!")
        self.async_loop = async_loop
        self.page_list = []
        self.current_page_idx = 0
        self.central_widget = None
        self.layout = None
        self.page_layout = None
        # self.initUI()
        self.init_ui()
        self.unix_server = UnixServer(UNIX_DEMO_APP_SERVER_URI)
        self.unix_server.unix_data_received.connect(self.unix_data_received_handler)
        self.msg_app_unix_client = UnixClient(path=UNIX_MSG_SERVER_URI)
        self.cmd_parser = CmdParser(self.msg_app_unix_client, self.page_list[PageListEnum.Media].get_media_engine())
        self.cmd_parser.unix_data_ready_to_send.connect(self.send_to_msg_server)
        QTimer.singleShot(0, lambda: asyncio.create_task(self.unix_server.start()))
        QTimer.singleShot(0, lambda: asyncio.create_task(self.msg_app_unix_client.connect()))

        signal.signal(signal.SIGINT, self.stop_server)


    def test_timer(self):
        pass
        # === 測試用 新增：每 5 秒觸發一次 test_send_unix_msg ===
        # self.timer = QTimer(self)
        # self.timer.setInterval(5000)  # 5 秒
        # self.timer.timeout.connect(self._periodic_unix_msg)
        # self.timer.start()

    def send_to_msg_server(self, send_data: str):
        log.debug("send_data:%s", send_data)
        # self.msg_app_unix_client.send(send_data)
        self._periodic_unix_msg(send_data)

    '''def direct_send_to_msg_server(self, send_data: str):
        log.debug("send_data:%s", send_data)
        asyncio.create_task(self.test_send_unix_msg(send_data))'''

    def _periodic_unix_msg(self, data:str):
        """
        QTimer 觸發時呼叫，安排 coroutine 到 asyncio 事件迴圈
        """
        log.debug("")
        asyncio.run_coroutine_threadsafe(
            self.test_send_unix_msg(data),
            self.async_loop
        )

    async def test_send_unix_msg(self, unix_msg:str):
        log.debug("test_unix_loop")
        if unix_msg is not None:
            await self.msg_app_unix_client.send(unix_msg)

    # def init_msg_unix_client(self):
    #    self.msg_unix_client = UnixClient(path=UNIX_MSG_SERVER_URI)

    def unix_data_received_handler(self, msg:str):
        log.debug("msg: %s", msg)
        # print recv cmd on Eng page
        if self.TEST_FLAG is True:
            for i in range(len(self.page_list)):
                if self.page_list[i].name == "Eng":
                    self.page_list[i].set_recv_cmd(msg)
                    self.page_layout.setCurrentIndex(i)
                    log.debug("Jump to Eng Page")

        self.cmd_parser.parse_cmds(msg)

    def init_pages(self):
        log.debug("init_pages")


    def init_ui(self):
        log.debug("init_ui")
        if FULL_SCREEN_UI:
            # 設定視窗為全螢幕、無邊框、無標題列, Press Esc to exit
            self.setWindowFlags(Qt.FramelessWindowHint)
            self.showFullScreen()

        self.central_widget = QWidget(self)
        self.central_widget.setStyleSheet("background-color: black;")

        self.setCentralWidget(self.central_widget)
        self.page_layout = QStackedLayout()

        for page_cls in Page_List:
            page = page_cls(self, self.central_widget)
            self.page_list.append(page)
            self.page_layout.addWidget(page)

        self.central_widget.setLayout(self.page_layout)
        self.page_layout.setCurrentIndex(0)
        # for p in self.page_list:
        #     log.debug(p.name)

        log.debug("self.page_layout.count() : %s", self.page_layout.count())

    ''' old initUI '''
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
        log.debug("keyPressEvent event.key : %s", event.key())
        if event.key() == Qt.Key_Escape:
            asyncio.create_task(self.shutdown_and_quit())
        elif event.key() == Qt.Key_P:
            next_index = (self.page_layout.currentIndex() + 1) % self.page_layout.count()
            log.debug("next, page_layout : %d", next_index)
            self.page_layout.setCurrentIndex(next_index)

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
