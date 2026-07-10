# -*- coding: utf-8 -*-
"""
workers/batch_worker.py

GUI 응답성을 유지하기 위해 별도 스레드에서 HWP 처리를 수행하는 Worker 클래스입니다.
"""

from PySide6.QtCore import QThread, Signal
from workers.processor import BatchProcessor

class BatchWorker(QThread):
    """
    HWP 처리 작업을 수행하는 백그라운드 스레드
    """
    progress_signal = Signal(int, int)  # (현재, 전체)
    current_file_signal = Signal(str)    # 현재 처리 중인 파일명
    finished_signal = Signal(bool, str) # (성공여부, 메시지)

    def __init__(self, file_paths, chapters, logger):
        super().__init__()
        self.file_paths = file_paths
        self.chapters = chapters
        self.logger = logger
        self.processor = BatchProcessor(logger=logger)

    def run(self):
        try:
            # Processor의 process 메서드가 파일 리스트와 중단원 리스트를 한 번에 처리하도록 호출
            # (Processor 내부에서 루프를 돌며 진행 상황을 로거를 통해 알림)
            self.processor.process(self.file_paths, self.chapters)

            self.finished_signal.emit(True, "모든 작업이 완료되었습니다.")
        except Exception as e:
            self.finished_signal.emit(False, str(e))
