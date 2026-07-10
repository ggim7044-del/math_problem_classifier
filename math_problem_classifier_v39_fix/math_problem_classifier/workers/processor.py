# -*- coding: utf-8 -*-
"""
workers/processor.py

핵심 비즈니스 로직을 실행하고 HWP 문서를 관리하는 모듈입니다.
"""

import os
import shutil
from typing import List, Optional

from config.settings import OUTPUT_DIR, OUTPUT_HWP_DIR
from core.hwp_session import HwpSession
from core.problem_locator import ProblemLocator
from core.hwp_writer import DifficultyHwpWriter
from core.exception_writer import ExceptionWriter
from core.process_logger import ProcessLogger


class BatchProcessor:
    def __init__(self, logger=None, output_dir: str = OUTPUT_HWP_DIR):
        self.logger = logger
        self.output_dir = output_dir
        self.locator = ProblemLocator(logger=logger)
        self.proc_logger = ProcessLogger(OUTPUT_DIR)

    def process(self, file_paths: List[str], chapters: List[str]):
        """
        선택된 파일들을 처리하고 {중단원}_{난이도}별로 분류하여 저장 후 종료합니다.
        - 원본 HWP 파일을 output/원본_복사본/ 폴더에 복사한 후 해당 복사본을 대상으로 처리합니다.
        - 복사에 성공한 문제만 원본 복사본 HWP 파일에서 빨간색 글씨로 표시합니다.
        """
        session = None
        exc_log_writer = ExceptionWriter(logger=self.logger)

        try:
            if self.logger:
                self.logger.info("한글 세션을 시작합니다...")
            session = HwpSession(visible=True)

            writer = DifficultyHwpWriter(session, output_dir=self.output_dir, logger=self.logger)
            writer.open_all()

            # 원본 복사본 저장용 디렉토리 생성
            original_copy_dir = os.path.join(self.output_dir, "원본_복사본")
            os.makedirs(original_copy_dir, exist_ok=True)

            for path in file_paths:
                self.proc_logger.start_file(path)
                if self.logger:
                    self.logger.info(f"[처리중] {os.path.basename(path)}")

                copied_path = ""
                try:
                    # 1단계: 파일 복사 및 열기
                    self.proc_logger.update_step("파일 복사 및 열기")

                    filename = os.path.basename(path)
                    copied_path = os.path.join(original_copy_dir, filename)

                    if self.logger:
                        self.logger.info(f" 원본 파일을 '원본_복사본' 폴더로 복제 중... ({filename})")
                    shutil.copy2(path, copied_path)

                    session.open_document(copied_path)
                    source_doc = self._find_source_doc(session, copied_path)

                    if not source_doc:
                        raise Exception("복제된 문서 객체를 찾을 수 없습니다.")

                    # 2단계: 문제 탐색
                    self.proc_logger.update_step("문제 탐색")
                    problems, exceptions = self.locator.locate_problems(
                        session.hwp, source_file=path, valid_chapters=chapters
                    )

                    current_file_outputs = set()

                    # 3단계: 정상 문제 삽입 및 빨간색 표시
                    for prob in problems:
                        self.proc_logger.update_step("HWP 복사/붙여넣기", prob.problem_number)
                        # 정상적으로 대상 HWP 파일에 삽입 완료된 경우에만 원본 복사본에 빨간색 표시 진행
                        if writer.add_problem_block(prob, source_doc):
                            writer.mark_problem_red(prob, source_doc)
                            current_file_outputs.add(f"{prob.chapter}_{prob.difficulty}.hwp")

                    # 4단계: 예외 문제 기록 (HWP 삽입은 하지 않고 예외 기록에만 추가)
                    for item in exceptions:
                        exc = item["exc"]
                        exc_log_writer.add(exc)

                    # 성공 기록
                    self.proc_logger.add_success(path, len(problems), sorted(list(current_file_outputs)))
                    if self.logger:
                        self.logger.info(f"[완료] {os.path.basename(path)} (정상:{len(problems)}, 예외:{len(exceptions)})")

                except Exception as e:
                    error_msg = str(e)
                    self.proc_logger.add_failure(
                        path,
                        self.proc_logger.current_prob_num,
                        self.proc_logger.current_step,
                        error_msg
                    )
                    if self.logger:
                        self.logger.error(f"[실패] {os.path.basename(path)} - 단계: {self.proc_logger.current_step}, 오류: {error_msg}")

                finally:
                    # 원본 복사본 문서는 변경 내용(빨간색 표시)을 저장한 후 항상 닫기 시도
                    try:
                        if 'source_doc' in locals() and source_doc:
                            if copied_path:
                                writer._activate_doc(session.hwp, source_doc)
                                session.hwp.save_as(copied_path)
                            source_doc.Close(1)
                    except Exception as ce:
                        if self.logger:
                            self.logger.error(f"원본 복사본 저장 및 닫기 중 오류 발생: {ce}")

            # ── 최종 저장 및 요약 ──────────────────────────────────────────
            self.proc_logger.update_step("최종 결과 저장")
            try:
                writer.save_and_close_all()
            except Exception as e:
                if self.logger:
                    self.logger.error(f"최종 HWP 저장 단계에서 오류가 있었지만 계속 진행합니다: {e}")

            exc_log_writer.save()
            self.proc_logger.save_summary()

            if self.logger:
                self.logger.info("모든 작업이 완료되었습니다. output/process_result.txt를 확인하세요.")

        except Exception as e:
            # 치명적 오류 (COM 연결 끊김 등)
            last_msg = self.proc_logger.get_last_status_msg()
            if self.logger:
                self.logger.error(f"치명적 오류 발생!\n{last_msg}\n오류내용: {e}")
            raise
        finally:
            if session:
                try:
                    session.quit()
                except:
                    pass

    def _find_source_doc(self, session, path):
        target = path.replace('\\', '/').lower()
        count = session.hwp.XHwpDocuments.Count
        for i in range(count):
            doc = session.hwp.XHwpDocuments.Item(i)
            if doc.FullName.replace('\\', '/').lower() == target:
                return doc
        return None
