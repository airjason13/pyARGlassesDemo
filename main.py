import asyncio
import logging
import signal
import sys

from PyQt5.QtCore import QEventLoop
from PyQt5.QtWidgets import QApplication
from qasync import QEventLoop
from c_mainwindow import CMainWindow
from global_def import *

async def main():
    log.debug("GiS AR Glasses Demo")
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = CMainWindow(loop)
    window.show()  # 已經在 CMainWindow 裡面呼叫 showFullScreen

    with loop:
        loop.run_forever()

if __name__ == "__main__":
    # main()
    asyncio.run(main())
