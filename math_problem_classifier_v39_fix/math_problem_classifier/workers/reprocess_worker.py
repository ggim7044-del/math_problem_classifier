# -*- coding: utf-8 -*-
"""
workers/reprocess_worker.py

예외 파일(output/오류/*.hwp)을 선택해 다시 분류를 시도하는 워커입니다.
재처리에 성공한 문제는 output/오류/재처리완료/{중단원}_{난이도}.hwp 에 저장됩니다.
"""

from PySide6.QtCore import QThread, Signal

from config.settings import REPROCESS_OUTPUT_DIR
from workers.processor import BatchProcessor


class ReprocessWorker(QThread):
    """
    예외 HWP 파일들을 재처리하는 백그라운드 스레드.

    원본 BatchProcessor를 재사용하되, 출력 경로를 REPROCESS_OUTPUT_DIR 로 지정합니다.
    성공한 문제: output/오류/재처리완료/{중단원}_{난이도}.hwp
    여전히 예외인 문제: 별도 처리 없이 로그에만 기록
    """

    progress_signal = Signal(int, int)   # (현재, 전체)
    current_file_signal = Signal(str)    # 현재 처리 중인 파일명
    finished_signal = Signal(bool, str)  # (성공여부, 메시지)

    def __init__(self, file_paths: list, chapters: list, logger):
        super().__init__()
        self.file_paths = file_paths
        self.chapters = chapters
        self.logger = logger

    def run(self):
        try:
            processor = BatchProcessor(
                logger=self.logger,
                output_dir=REPROCESS_OUTPUT_DIR,
            )
            processor.process(self.file_paths, self.chapters)
            self.finished_signal.emit(True, "재처리가 완료됐습니다.")
        except Exception as e:
            self.finished_signal.emit(False, str(e))
