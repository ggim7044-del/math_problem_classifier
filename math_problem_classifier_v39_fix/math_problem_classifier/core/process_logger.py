# -*- coding: utf-8 -*-
"""
core/process_logger.py

작업 프로세스의 상태를 기록하고 최종 요약 파일(process_result.txt)을 생성하는 모듈입니다.
"""

import os
from datetime import datetime
from typing import List, Dict, Any


class ProcessLogger:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.result_file = os.path.join(output_dir, "process_result.txt")

        # 처리 상태 저장
        self.success_files: List[Dict[str, Any]] = []
        self.failed_files: List[Dict[str, Any]] = []

        # 현재 처리 중인 정보 (강제 종료 대비)
        self.current_file = ""
        self.current_step = ""
        self.current_prob_num = ""

    def start_file(self, filepath: str):
        self.current_file = filepath
        self.current_step = "파일 열기"
        self.current_prob_num = ""

    def update_step(self, step: str, prob_num: str = ""):
        self.current_step = step
        if prob_num:
            self.current_prob_num = prob_num

    def add_success(self, filepath: str, problem_count: int, output_files: List[str]):
        self.success_files.append({
            "name": os.path.basename(filepath),
            "count": problem_count,
            "outputs": output_files
        })

    def add_failure(self, filepath: str, prob_num: str, step: str, error_msg: str):
        self.failed_files.append({
            "name": os.path.basename(filepath),
            "prob_num": prob_num,
            "step": step,
            "error": error_msg
        })

    def save_summary(self):
        """최종 요약 파일을 생성합니다."""
        os.makedirs(self.output_dir, exist_ok=True)

        lines = []
        lines.append("====================")
        lines.append("처리 결과 요약")
        lines.append(f"일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("====================\n")

        lines.append(f"총 대상 파일: {len(self.success_files) + len(self.failed_files)}개")
        lines.append(f"성공: {len(self.success_files)}개")
        lines.append(f"실패: {len(self.failed_files)}개\n")

        lines.append("====================")
        lines.append("완료 파일:")
        lines.append("====================")
        if not self.success_files:
            lines.append("(없음)")
        for i, f in enumerate(self.success_files, 1):
            lines.append(f"{i}. {f['name']}")
            lines.append(f"   - 문제 수: {f['count']}개")
            if f['outputs']:
                lines.append(f"   - 생성 파일: {', '.join(f['outputs'])}")
        lines.append("")

        lines.append("====================")
        lines.append("실패 파일:")
        lines.append("====================")
        if not self.failed_files:
            lines.append("(없음)")
        for i, f in enumerate(self.failed_files, 1):
            lines.append(f"{i}. {f['name']}")
            lines.append(f"   - 문제 번호: {f['prob_num'] if f['prob_num'] else 'N/A'}")
            lines.append(f"   - 단계: {f['step']}")
            lines.append(f"   - 오류: {f['error']}")
        lines.append("\n====================")

        with open(self.result_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def get_last_status_msg(self) -> str:
        """비정상 종료 시 보여줄 마지막 상태 메시지"""
        msg = f"마지막 처리 파일: {os.path.basename(self.current_file) if self.current_file else '없음'}\n"
        msg += f"마지막 처리 단계: {self.current_step}\n"
        if self.current_prob_num:
            msg += f"마지막 문제 번호: {self.current_prob_num}"
        return msg
