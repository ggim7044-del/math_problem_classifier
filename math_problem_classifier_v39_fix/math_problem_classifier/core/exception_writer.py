# -*- coding: utf-8 -*-
"""
core/exception_writer.py

난이도 또는 중단원 값이 유효하지 않아 정상 처리되지 못한 문제들을
별도의 예외 파일(JSON + TXT)로 저장하는 모듈입니다.

저장 파일:
- exceptions.json : 구조화된 예외 목록 (프로그래밍 방식으로 재처리 가능)
- exceptions.txt  : 사람이 읽기 쉬운 텍스트 요약 (검토용)

설계 원칙:
- 예외 발생 시 프로그램 전체가 중단되지 않습니다.
- 예외 문제는 정상 결과 파일(상/중/하 HWP)에 포함되지 않습니다.
- 배치 작업 완료 후 save()를 한 번만 호출하면 됩니다.
- 예외가 없으면 파일을 생성하지 않습니다.
"""

import json
import os
from datetime import datetime
from typing import List

from config.settings import OUTPUT_DIR
from core.models import ExceptionProblem


class ExceptionWriter:
    """
    ExceptionProblem 목록을 수집하고, 작업 완료 후 파일로 저장하는 클래스.

    사용 순서:
        writer = ExceptionWriter(output_dir=OUTPUT_DIR, logger=logger)
        writer.add(exc)          # 예외 발생 시마다 호출
        ...
        writer.save()            # 배치 작업 완료 후 1회 호출
    """

    def __init__(self, output_dir: str = OUTPUT_DIR, logger=None):
        self.output_dir = output_dir
        self.logger = logger
        self._exceptions: List[ExceptionProblem] = []

    # ------------------------------------------------------------------
    # 예외 추가
    # ------------------------------------------------------------------
    def add(self, exc: ExceptionProblem) -> None:
        """예외 문제를 내부 목록에 추가합니다."""
        self._exceptions.append(exc)

    def add_all(self, exceptions: List[ExceptionProblem]) -> None:
        """예외 문제 목록을 한 번에 추가합니다."""
        self._exceptions.extend(exceptions)

    @property
    def count(self) -> int:
        """현재까지 수집된 예외 문제 수를 반환합니다."""
        return len(self._exceptions)

    # ------------------------------------------------------------------
    # 저장
    # ------------------------------------------------------------------
    def save(self) -> None:
        """
        수집된 예외 문제를 파일로 저장합니다.
        예외가 없으면 파일을 생성하지 않고 반환합니다.

        생성 파일:
        - {output_dir}/exceptions.json
        - {output_dir}/exceptions.txt
        """
        if not self._exceptions:
            if self.logger:
                self.logger.info("예외 문제 없음 — 예외 파일을 생성하지 않습니다.")
            return

        os.makedirs(self.output_dir, exist_ok=True)

        json_path = os.path.join(self.output_dir, "exceptions.json")
        txt_path = os.path.join(self.output_dir, "exceptions.txt")

        self._save_json(json_path)
        self._save_txt(txt_path)

        if self.logger:
            self.logger.info(
                f"예외 문제 {self.count}건 저장 완료: "
                f"{json_path}, {txt_path}"
            )

    # ------------------------------------------------------------------
    # 내부 저장 메서드
    # ------------------------------------------------------------------
    def _save_json(self, path: str) -> None:
        """예외 목록을 JSON 형식으로 저장합니다."""
        data = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_count": self.count,
            "exceptions": [
                {
                    "source_file": exc.source_file,
                    "problem_number": exc.problem_number,
                    "reason": exc.reason,
                    "raw_difficulty": exc.raw_difficulty,
                    "raw_chapter": exc.raw_chapter,
                    "plain_text_preview": exc.plain_text_preview,
                }
                for exc in self._exceptions
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_txt(self, path: str) -> None:
        """예외 목록을 사람이 읽기 쉬운 텍스트 형식으로 저장합니다."""
        lines = [
            "=" * 70,
            "수학 문제은행 자동 분류 — 예외 문제 목록",
            f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"총 예외 건수: {self.count}건",
            "=" * 70,
            "",
        ]

        reason_labels = {
            "invalid_difficulty": "[난이도 오류]",
            "invalid_chapter": "[중단원 오류]",
            "no_difficulty_tag": "[난이도 태그 없음]",
            "no_chapter_tag": "[중단원 태그 없음]",
            "boundary_merge_suspected": "[문제 경계 오류 의심 - 다음 문제와 병합됨]",
        }

        for i, exc in enumerate(self._exceptions, start=1):
            label = reason_labels.get(exc.reason, f"[{exc.reason}]")
            lines.append(f"[{i}] {label}")
            lines.append(f"  파일     : {exc.source_file}")

            from core.filename_parser import parse_source_info
            source_label = parse_source_info(exc.source_file)
            lines.append(f"  출처     : {source_label}")

            lines.append(f"  문제번호 : {exc.problem_number}")

            if exc.reason == "invalid_difficulty":
                val = exc.raw_difficulty if exc.raw_difficulty else "(값 없음)"
                lines.append(f"  난이도값 : {val}  ← 상/중/하가 아님")
            elif exc.reason == "invalid_chapter":
                lines.append(f"  중단원   : {exc.raw_chapter}  ← 허용 목록에 없음")
            elif exc.reason == "boundary_merge_suspected":
                lines.append("  ※ [난이도] 태그가 한 블록에 2번 이상 발견되어, 문제 끝 경계를")
                lines.append("     못 찾고 다음 문제가 함께 묶인 것으로 보입니다. 원본 문서에서")
                lines.append("     해당 문제 번호의 자동번호/각주 설정을 확인해주세요.")

            preview_len = 250 if exc.reason == "boundary_merge_suspected" else 100
            lines.append(f"  미리보기 : {exc.plain_text_preview[:preview_len].strip()}")
            lines.append("")

        lines.append("=" * 70)

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
