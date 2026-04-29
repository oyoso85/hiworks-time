import sys
import os

# src/ 폴더를 import 경로에 추가 (PyInstaller 빌드 시에도 동작)
sys.path.insert(0, os.path.dirname(__file__))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

import startup
from widget import DesktopWidget


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 다이얼로그 닫아도 위젯 유지

    if not startup.is_registered():
        startup.register()

    widget = DesktopWidget()
    widget.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
