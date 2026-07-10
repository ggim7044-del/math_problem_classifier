# -*- coding: utf-8 -*-
"""
utils/logger.py

GUI 로그창 출력과 error_log.txt 파일 기록을 동시에 처리하는 로거 모듈입니다.

- Logger는 QObject를 상속받아 Signal을 발생시킵니다.
  -> 다른 스레드(worker)에서 로그를 기록해도, Signal/Slot 메커니즘을 통해
     안전하게 메인 스레드의 GUI 위젯에 반영할 수 있습니다.
- 일반 로그(info)는 GUI에만 출력됩니다.
- 에러 로그(error)는 GUI 출력 + error_log.txt 파일에도 기록됩니다.
"""

import os
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from config.settings import ERROR_LOG_PATH


class Logger(QObject):
    """
    프로그램 전역에서 사용할 로거 클래스.
    Signal을 통해 GUI(로그창)에 실시간으로 메시지를 전달합니다.
    """

    # GUI 로그창에 출력할 메시지 Signal (str: 출력할 메시지)
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()

    def _timestamp(self) -> str:
        """현재 시각을 로그에 표시하기 위한 문자열로 반환합니다."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def info(self, message: str):
        """
        일반 정보 로그를 GUI 로그창에 출력합니다.
        (파일 기록은 하지 않음)
        """
        formatted = f"[{self._timestamp()}] [INFO] {message}"
        self.log_signal.emit(formatted)

    def warning(self, message: str):
        """
        경고 로그를 GUI 로그창에 출력합니다.
        """
        formatted = f"[{self._timestamp()}] [WARN] {message}"
        self.log_signal.emit(formatted)

    def error(self, message: str, source_file: str = ""):
        """
        에러 로그를 GUI 로그창에 출력하고, error_log.txt 파일에도 기록합니다.

        Args:
            message: 에러 내용
            source_file: 에러가 발생한 원본 HWP 파일명 (선택)
        """
        prefix = f"[{source_file}] " if source_file else ""
        formatted = f"[{self._timestamp()}] [ERROR] {prefix}{message}"

        # GUI 로그창에 출력
        self.log_signal.emit(formatted)

        # error_log.txt 파일에 append 모드로 기록
        self._write_error_log(formatted)

    def _write_error_log(self, formatted_message: str):
        """
        error_log.txt 파일에 에러 메시지를 append 방식으로 기록합니다.
        파일이 없으면 새로 생성됩니다.
        """
        try:
            os.makedirs(os.path.dirname(ERROR_LOG_PATH) or ".", exist_ok=True)
            with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(formatted_message + "\n")
        except Exception as e:
            # 로그 파일 기록 자체가 실패하는 경우, GUI에만 알림
            # (무한 루프 방지를 위해 error()를 재귀 호출하지 않음)
            self.log_signal.emit(
                f"[{self._timestamp()}] [ERROR] error_log.txt 기록 실패: {e}"
            )
