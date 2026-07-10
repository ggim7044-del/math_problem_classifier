# -*- coding: utf-8 -*-
"""
main.py

프로그램의 진입점(entry point)입니다.
PySide6 애플리케이션을 실행하고 메인 윈도우를 화면에 띄웁니다.
"""

import sys

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
