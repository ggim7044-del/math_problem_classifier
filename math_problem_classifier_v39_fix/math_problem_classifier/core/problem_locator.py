# -*- coding: utf-8 -*-
"""
core/problem_locator.py

HWP 문서 내부 컨트롤 구조를 이용한 문제 위치 탐색 및 태그 기반 분류 모듈.
"""

from typing import List, Tuple, Optional, Dict

from core.models import ProblemBlock, ExceptionProblem
from core.difficulty_extractor import extract_difficulty, extract_difficulty_raw, extract_chapter_raw


# 문제 블록 하나로 보기에는 너무 짧은 텍스트(순수 잡음/공백 등)를 걸러내기 위한 최소 글자 수.
_MIN_BLOCK_CHARS = 8


class ProblemLocatorError(Exception):
    pass


class ProblemLocator:

    _ENDNOTE_CTRL_ID = "en"

    def __init__(self, logger=None):
        self.logger = logger

    def locate_problems(
        self,
        hwp,
        source_file: str = "",
        valid_chapters: List[str] = None,
    ) -> Tuple[List[ProblemBlock], List[Dict]]:
        """
        문제를 탐색하고 분류합니다.

        새 알고리즘:
        1. 미주(en) 발견: 문서를 처음부터 끝까지 탐색하며 미주(en) 컨트롤 위치를 찾습니다.
        2. 종료 지점 찾기: 해당 미주 이후 탐색하며 [난이도] 상, [난이도] 중, [난이도] 하 세 문자열 중 하나를 종료 조건으로 찾습니다.
        3. 복사 범위: 미주(en)부터 난이도 줄 끝(문단 끝)까지입니다.
        4. 다시 반복: 다시 다음 미주(en)를 찾고 같은 작업을 반복합니다.

        - 연속 미주(en) 처리: 연속으로 미주가 나오는 경우, 앞의 미주들은 모두 무시하고 가장 마지막 미주부터 [난이도] 상/중/하 까지를 하나의 문제로 처리합니다.
        - 서술형 처리 제거: 서술형 처리는 별도로 하지 않고 알고리즘 흐름 그대로 지나갑니다.
        """
        # 1. 미주(en) 컨트롤 좌표 구하기
        en_coords = []
        try:
            controls = list(hwp.ctrl_list)
            for ctrl in controls:
                try:
                    cid = ctrl.CtrlID
                except Exception:
                    continue
                if cid == self._ENDNOTE_CTRL_ID:
                    try:
                        list_id, para, pos = hwp.get_ctrl_pos(ctrl, option=1)
                        en_coords.append({"list": list_id, "para": para, "pos": pos})
                    except Exception:
                        continue
        except Exception as e:
            self._log_error(f"ctrl_list 접근 실패: {e}", source_file)

        # 2. [난이도] 상/중/하 좌표 구하기
        diff_coords = []
        for query in ["[난이도] 상", "[난이도] 중", "[난이도] 하"]:
            diff_coords.extend(self._find_text_occurrences_single(hwp, query))

        # 3. 문서 순서대로 합쳐 시간 순(Stream) 이벤트 생성 및 정렬
        events = []
        for en in en_coords:
            events.append({"type": "en", "list": en["list"], "para": en["para"], "pos": en["pos"]})
        for diff in diff_coords:
            events.append({"type": "diff", "list": diff["list"], "para": diff["para"], "pos": diff["pos"]})

        # 문서상 실제 위치 순서로 정렬 (list, para, pos 순)
        events.sort(key=lambda e: (e["list"], e["para"], e["pos"]))

        # 4. 연속 미주 처리 및 매핑 경계 추출
        candidate_en = None
        boundaries = []  # List[Tuple[dict, dict]] -> (start_en_event, end_diff_event)

        for event in events:
            if event["type"] == "en":
                candidate_en = event  # 연속된 미주가 발견되면 이전 시작 후보를 덮어씀
            elif event["type"] == "diff":
                if candidate_en is not None:
                    boundaries.append((candidate_en, event))
                    candidate_en = None  # 매칭 후 후보 리셋하여 다음 미주 대기

        if not boundaries:
            raise ProblemLocatorError("문제 시작 위치를 찾지 못했습니다.")

        problems: List[ProblemBlock] = []
        exceptions: List[Dict] = []

        for idx, (start, end_diff) in enumerate(boundaries):
            # 난이도 태그 줄 끝(문단 끝)까지를 복사 영역으로 설정
            end_pos = self._get_para_end_pos(hwp, end_diff["list"], end_diff["para"])
            end = {
                "list": end_diff["list"],
                "para": end_diff["para"],
                "pos": end_pos
            }

            try:
                plain_text = self._get_plain_text_between(hwp, start, end)
            except Exception as e:
                self._log_error(f"{idx+1}번째 문제 텍스트 추출 실패: {e}", source_file)
                continue

            # 잡음 필터: 실제 내용이 거의 없는 블록은 건너뜁니다.
            if len(plain_text.strip()) < _MIN_BLOCK_CHARS:
                continue

            # 태그 추출 및 예외 판별
            difficulty = extract_difficulty(plain_text)
            raw_difficulty = extract_difficulty_raw(plain_text)
            raw_chapter = extract_chapter_raw(plain_text)

            coords = {
                "start_list": start["list"],
                "start_para": start["para"],
                "start_pos": start["pos"],
                "end_list": end["list"],
                "end_para": end["para"],
                "end_pos": end["pos"]
            }

            reason = None

            # 1. 중단원 태그가 아예 없는 경우
            if not raw_chapter:
                reason = "no_chapter_tag"
            # 2. 중단원이 등록된 목록에 없는 경우
            elif valid_chapters and raw_chapter not in valid_chapters:
                reason = "invalid_chapter"
            # 3. 난이도 태그가 아예 없는 경우
            elif not raw_difficulty:
                reason = "no_difficulty_tag"
            # 4. 난이도가 상/중/하 외의 값인 경우
            elif difficulty is None:
                reason = "invalid_difficulty"

            if reason:
                exc = ExceptionProblem(
                    source_file=source_file, problem_number=str(idx + 1),
                    reason=reason, raw_difficulty=raw_difficulty,
                    raw_chapter=raw_chapter, plain_text_preview=plain_text[:400]
                )
                exceptions.append({"exc": exc, "coords": coords})
                continue

            # 정상 문제
            problems.append(ProblemBlock(
                index=idx + 1, problem_number=str(idx + 1),
                start_list=coords["start_list"],
                start_para=coords["start_para"],
                start_pos=coords["start_pos"],
                end_list=coords["end_list"],
                end_para=coords["end_para"],
                end_pos=coords["end_pos"],
                plain_text=plain_text, difficulty=difficulty,
                source_file=source_file, chapter=raw_chapter
            ))

        return problems, exceptions

    def _get_para_end_pos(self, hwp, list_id: int, para: int) -> int:
        """지정된 문단의 끝 문자 좌표(Pos)를 구합니다."""
        try:
            old_info = hwp.GetPosBySet()
            old_pos = (old_info.Item("List"), old_info.Item("Para"), old_info.Item("Pos"))

            hwp.set_pos(list_id, para, 0)
            hwp.MoveSelParaEnd()
            info = hwp.GetPosBySet()
            end_pos = info.Item("Pos")
            hwp.Cancel()

            hwp.set_pos(*old_pos)
            return end_pos
        except Exception:
            return 0xfffff  # HWP API상 충분히 큰 값은 문단 끝까지의 범위를 지정하게 됨

    def _find_text_occurrences_single(self, hwp, query: str) -> list:
        """문서 전체에서 특정 텍스트를 단독 검색하여 좌표 목록을 반환합니다."""
        occurrences = []
        try:
            pset = hwp.HParameterSet.HFindReplace
            hwp.HAction.GetDefault("FindDlg", pset.HSet)
            pset.FindString = query
            pset.Direction = hwp.FindDir("Forward")
            pset.IgnoreMessage = 1
            pset.MatchCase = 1

            try:
                hwp.SetMessageBoxMode(0x2FFF1)
            except Exception:
                pass

            old_info = hwp.GetPosBySet()
            old_pos = (old_info.Item("List"), old_info.Item("Para"), old_info.Item("Pos"))

            hwp.MoveDocBegin()
            while hwp.HAction.Execute("RepeatFind", pset.HSet):
                info = hwp.GetPosBySet()
                occurrences.append({
                    "list": info.Item("List"),
                    "para": info.Item("Para"),
                    "pos": info.Item("Pos")
                })
                hwp.HAction.Run("MoveRight")

            hwp.set_pos(*old_pos)
        except Exception as e:
            if self.logger:
                self.logger.error(f"텍스트 '{query}' 검색 중 오류 발생: {e}")
        finally:
            try:
                hwp.SetMessageBoxMode(0xFFFFF)
            except Exception:
                pass
        return occurrences

    def _get_plain_text_between(self, hwp, start, end):
        hwp.select_text(start["para"], start["pos"], end["para"], end["pos"], start["list"])
        text = hwp.get_selected_text() or ""
        hwp.Cancel()
        return text

    def _log_error(self, message, source_file=""):
        if self.logger:
            self.logger.error(message, source_file=source_file)
