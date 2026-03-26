from PyQt5.QtWidgets import QWidget


class NsightPage(QWidget):
    name = 'Nsight'

    def __init__(self, _main_window, _central_qwidget, media_engine, **kwargs):
        super(NsightPage, self).__init__(**kwargs)