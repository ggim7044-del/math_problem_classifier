# -*- coding: utf-8 -*-
"""
core/hwp_writer.py

중단원_난이도별 결과 HWP 문서를 관리하고 저장하는 모듈입니다.
"""

import os
import re
from typing import Dict, Optional, List

from config.settings import OUTPUT_HWP_DIR, VALID_DIFFICULTIES
from core.backup_manager import create_backup
from core.hwp_session import HwpSession
from core.models import ProblemBlock


def extract_source_from_text(text: str) -> Optional[str]:
    """
    텍스트 앞부분에서 '[학교명_연도_학년_학기_시험]' 형식의 출처 정보를 추출합니다.
    예외 파일(경계오류 등)을 다시 처리할 때 본문에 남은 출처를 복원하는 데 사용됩니다.
    """
    if not text:
        return None
    # 상위 5개 문단 안에서 검색
    lines = text.strip().split('\n')[:5]
    # 패턴 예시: [금옥여고_2025_1_1_기말] 또는 [금옥여고_2025]
    pattern = re.compile(r"\[\s*([가-힣a-zA-Z0-9]+_\d{4}(?:_[a-zA-Z0-9가-힣]+)*)\s*\]")
    for line in lines:
        match = pattern.search(line)
        if match:
            return f"[{match.group(1)}]"
    return None


class HwpWriterError(Exception):
    pass


class DifficultyHwpWriter:
    """
    {중단원}_{난이도} 결과 HWP 문서들을 통합 관리합니다.
    """

    # 문제 사이 구분용 빈 줄 개수
    _BLANK_LINES_COUNT = 3

    def __init__(self, hwp_session: HwpSession, output_dir: str = OUTPUT_HWP_DIR, logger=None):
        self.hwp_session = hwp_session
        self.hwp = hwp_session.hwp
        self.output_dir = output_dir
        self.logger = logger

        # 문서 키: (문서객체, 파일경로, 내용유무)
        self._docs: Dict[str, dict] = {}
        # 각 결과 문서별로 이미 출처를 표시한 원본 파일 경로 목록을 저장하여 중복 표시를 방지합니다.
        # 형식: { "부등식_상": { "C:/path/to/source1.hwp", ... } }
        self._written_sources: Dict[str, set] = {}
        self._temp_doc = None  # 중복 제거 및 클리닝 작업을 위한 재사용 임시 문서
        self._opened = False

    def open_all(self):
        """필요한 디렉토리 구조를 생성합니다."""
        os.makedirs(os.path.join(self.output_dir, "정상"), exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "원본_복사본"), exist_ok=True)
        self._opened = True

    def _get_or_create_doc(self, key: str) -> object:
        """특정 키에 해당하는 문서 객체를 반환하거나 새로 생성합니다."""
        if key in self._docs:
            return self._docs[key]["doc"]

        sub_dir = "정상"
        filename = f"{key}.hwp"
        filepath = os.path.join(self.output_dir, sub_dir, filename)

        if os.path.exists(filepath):
            create_backup(filepath)
            self.hwp_session.open_document(filepath)
            doc = self._find_document_by_path(filepath)
            has_content = True
        else:
            doc = self.hwp_session.create_blank_document()
            has_content = False

        self._docs[key] = {"doc": doc, "path": filepath, "has_content": has_content}
        return doc

    def add_problem_block(self, block: ProblemBlock, source_doc) -> bool:
        """정상 문제를 {중단원}_{난이도} 파일에 추가합니다."""
        key = f"{block.chapter}_{block.difficulty}"
        doc = self._get_or_create_doc(key)
        return self._insert_to_doc(block, source_doc, doc, key)

    def mark_problem_red(self, block: ProblemBlock, source_doc) -> bool:
        """정상적으로 복사된 문항 영역을 원본 복사본 HWP에서 빨간색으로 표시합니다."""
        try:
            self._activate_doc(self.hwp, source_doc)
            # 영역 선택
            self.hwp.select_text(block.start_para, block.start_pos, block.end_para, block.end_pos, block.start_list)

            # 글자모양(CharShape) 액션을 사용하여 글자색을 빨간색으로 변경
            pset = self.hwp.HParameterSet.HCharShape
            self.hwp.HAction.GetDefault("CharShape", pset.HSet)
            try:
                pset.TextColor = self.hwp.RGBColor(255, 0, 0)
            except Exception:
                pset.TextColor = 255  # fallback to COLORREF red value
            self.hwp.HAction.Execute("CharShape", pset.HSet)

            # 선택 영역 해제
            self.hwp.Cancel()
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"원본 복사본 빨간색 표시 중 오류 발생: {e}")
            return False

    def _insert_to_doc(self, block: ProblemBlock, source_doc, target_doc, key: str) -> bool:
        """실제 HWP 삽입 로직 (출처 중복 방지 및 대괄호 중첩 해결 포함)"""
        try:
            # 1) 원본에서 블록 복사
            self._activate_doc(self.hwp, source_doc)
            self.hwp.select_text(block.start_para, block.start_pos, block.end_para, block.end_pos, block.start_list)
            block_data = self.hwp.GetTextFile(format="HWP", option="saveblock")
            self.hwp.Cancel()

            if not block_data:
                return False

            # 2) 출처 가공 및 복원 (파일명 파싱 실패 시 본문 텍스트에서 출처 추출)
            from core.filename_parser import parse_source_info
            source_label = parse_source_info(block.source_file)
            if "알수없음" in source_label or "경계오류" in source_label or "미지정" in source_label:
                text_source = extract_source_from_text(block.plain_text)
                if text_source:
                    source_label = text_source

            if not (source_label.startswith("[") and source_label.endswith("]")):
                source_label = f"[{source_label}]"

            # 3) 출처 중복 방지 로직 (문단 앞부분 5개 문단 내에서 해당 출처 문단을 찾아서 자동 제거)
            if self._has_source_in_text(block.plain_text, source_label):
                block_data = self._remove_source_line_from_block(block_data, source_label)

            # 4) 대상 문서 활성화 및 삽입
            self._activate_doc(self.hwp, target_doc)
            self.hwp.MoveDocEnd()

            if self._docs[key]["has_content"]:
                self.hwp.insert_text("\r" * self._BLANK_LINES_COUNT)

            # ── 묶음 출처 표시 로직 ──────────────────────────────────────
            # 해당 결과 문서(key)에 현재 원본 파일(block.source_file)의 출처를 아직 적지 않았다면
            # 최초 1회만 출처 헤더를 작성해 줍니다.
            if key not in self._written_sources:
                self._written_sources[key] = set()

            if block.source_file not in self._written_sources[key]:
                self.hwp.insert_text(source_label)
                self.hwp.insert_text("\r")
                self._written_sources[key].add(block.source_file)

            # 본문 삽입
            self.hwp.SetTextFile(block_data, format="HWP")
            self.hwp.MoveDocEnd()

            # 붙여넣은 직후 즉시 파일에 저장 (데이터 유실 방지 및 작업 안정성 확보)
            self.hwp.save_as(self._docs[key]["path"])

            self._docs[key]["has_content"] = True
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"삽입 중 오류 발생 ({key}): {e}")
            raise # Processor에서 단계를 추적할 수 있도록 예외 상신

    def _has_source_in_text(self, plain_text: str, source_label: str) -> bool:
        """복사하려는 블록의 앞 5개 문단 내에 출처 레이블과 동일한 내용이 포함되어 있는지 확인합니다."""
        if not plain_text:
            return False
        clean_label = source_label.replace("[", "").replace("]", "").strip()
        lines = plain_text.strip().split('\n')[:5]
        for line in lines:
            clean_line = line.replace("[", "").replace("]", "").strip()
            if clean_line == clean_label:
                return True
        return False

    def _get_temp_doc(self):
        """클리닝 전용 임시 문서를 생성하거나 반환합니다."""
        if self._temp_doc is None:
            self._temp_doc = self.hwp_session.create_blank_document()
        return self._temp_doc

    def _remove_source_line_from_block(self, hwp_data: str, source_label: str) -> str:
        """HWP 데이터의 상위 5개 문단을 검사하여 출처 표기 문단과 일치하는 것을 지워줍니다 (임시 문서 재사용)."""
        try:
            temp_doc = self._get_temp_doc()
            self._activate_doc(self.hwp, temp_doc)
            self.hwp.clear()  # 기존 임시 문서 내용 비우기
            self.hwp.SetTextFile(hwp_data, format="HWP")

            clean_label = source_label.replace("[", "").replace("]", "").strip()
            self.hwp.MoveDocBegin()

            # 상위 5개 문단 탐색
            for _ in range(5):
                self.hwp.MoveSelParaEnd()
                text = self.hwp.get_selected_text() or ""
                self.hwp.Cancel()

                clean_text = text.replace("[", "").replace("]", "").strip()
                if clean_text == clean_label:
                    self.hwp.HAction.Run("DeletePara")
                    break

                if not self.hwp.MoveParaDown():
                    break

            new_data = self.hwp.GetTextFile(format="HWP", option="")
            return new_data
        except Exception:
            return hwp_data # 실패 시 원본 반환

    def _is_source_duplicated(self, plain_text: str, source_label: str) -> bool:
        """원본 텍스트의 시작 부분이 추가하려는 출처와 동일한지 확인 (하위 호환성 유지)"""
        if not plain_text:
            return False

        first_line = plain_text.strip().split('\n')[0].strip()
        clean_first = first_line.replace("[", "").replace("]", "").strip()
        clean_label = source_label.replace("[", "").replace("]", "").strip()

        return clean_first == clean_label

    def _remove_first_line_from_block(self, hwp_data: str) -> str:
        """HWP 데이터에서 첫 번째 문단을 제거한 데이터를 반환 (임시 문서 재사용)"""
        try:
            temp_doc = self._get_temp_doc()
            self._activate_doc(self.hwp, temp_doc)
            self.hwp.clear()  # 기존 임시 문서 내용 비우기
            self.hwp.SetTextFile(hwp_data, format="HWP")

            # 첫 번째 문단으로 이동하여 삭제
            self.hwp.MoveDocBegin()
            self.hwp.HAction.Run("DeletePara")

            # 남은 데이터 다시 추출
            new_data = self.hwp.GetTextFile(format="HWP", option="")
            return new_data
        except Exception:
            return hwp_data

    def _activate_doc(self, hwp, doc_obj) -> bool:
        """pyhwpx와 HWP ActiveX의 활성 문서를 동기화하여 안전하게 전환합니다."""
        try:
            target_id = doc_obj.DocumentID
            count = hwp.XHwpDocuments.Count
            for i in range(count):
                doc = hwp.XHwpDocuments.Item(i)
                if doc.DocumentID == target_id:
                    hwp.switch_to(i)
                    return True
        except Exception:
            pass

        try:
            target_path = os.path.normpath(doc_obj.FullName).lower() if doc_obj.FullName else ""
            if target_path:
                count = hwp.XHwpDocuments.Count
                for i in range(count):
                    doc = hwp.XHwpDocuments.Item(i)
                    if doc.FullName and os.path.normpath(doc.FullName).lower() == target_path:
                        hwp.switch_to(i)
                        return True
        except Exception:
            pass

        # COM Fallback
        try:
            doc_obj.SetActive_XHwpDocument()
        except Exception:
            pass
        return False

    def save_and_close_all(self):
        """
        모든 문서를 저장하고 닫습니다.
        """
        failed = []

        # 1) 사용된 재사용 임시 문서 닫기
        if self._temp_doc is not None:
            try:
                self._temp_doc.Close(1)
            except Exception:
                pass
            self._temp_doc = None

        # 2) 결과 문서들 저장 및 닫기 (문서별로 독립적으로 시도)
        for key, info in self._docs.items():
            doc = info["doc"]
            path = info["path"]
            saved = False

            # 일시적인 COM 서버 오류(RPC_E_SERVERFAULT 등)를 감안해 1회 재시도합니다.
            for attempt in (1, 2):
                try:
                    self._activate_doc(self.hwp, doc)
                    self.hwp.save_as(path)
                    saved = True
                    break
                except Exception as e:
                    if attempt == 1:
                        if self.logger:
                            self.logger.error(f"저장 재시도: {path} ({e})")
                        try:
                            import time
                            time.sleep(1)
                        except Exception:
                            pass
                    else:
                        if self.logger:
                            self.logger.error(f"저장 실패(재시도 후에도 실패, 해당 문서는 건너뜁니다): {path} ({e})")
                        failed.append((key, path, str(e)))

            # 저장 성공 여부와 무관하게 문서는 닫아서 이후 문서 처리에
            # 영향을 주지 않도록 합니다.
            try:
                doc.Close(1)
            except Exception:
                pass

        if failed and self.logger:
            self.logger.error(
                f"최종 저장 단계에서 {len(failed)}개 문서 저장에 실패했습니다. "
                f"단, 각 문제 삽입 시점에 저장된 이전 버전은 남아있을 수 있습니다: "
                + ", ".join(p for _, p, _ in failed)
            )

    def _find_document_by_path(self, filepath: str) -> Optional[object]:
        normalized_target = os.path.normpath(filepath).lower()
        try:
            count = self.hwp.XHwpDocuments.Count
            for i in range(count):
                doc = self.hwp.XHwpDocuments.Item(i)
                if os.path.normpath(doc.FullName).lower() == normalized_target:
                    return doc
        except Exception:
            pass
        return None
