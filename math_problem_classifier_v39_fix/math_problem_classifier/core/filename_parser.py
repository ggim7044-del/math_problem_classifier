# -*- coding: utf-8 -*-
"""
core/filename_parser.py

파일명에서 학교명, 연도, 학기, 시험 종류 등을 추출하는 모듈입니다.
"""

import os
import re
from typing import Optional
from config.settings import SEMESTER_CODE_PATTERN, EXAM_TYPE_MAP

def parse_source_info(filepath: str) -> str:
    """
    파일명에서 출처 정보를 추출하여 포맷팅된 문자열을 반환합니다.
    예: "[금옥여고_2025_1_1_기말]"
    """
    filename = os.path.basename(filepath)

    # 학교명 추출 (대괄호 묶음 중 학교명 위치 탐색)
    # 예: [고][2025][1-1-b][서울양천구][금옥여고]...
    brackets = re.findall(r"\[(.*?)\]", filename)

    school_name = "알수없음"
    year = "202X"
    semester_info = ""

    if len(brackets) >= 5:
        # 일반적인 패턴 기반 추출 (설정값 활용 가능)
        year = brackets[1] if brackets[1].isdigit() else year
        school_name = brackets[4]

        # 학기/시험 정보 파싱
        semester_match = re.search(SEMESTER_CODE_PATTERN, filename)
        if semester_match:
            grade = semester_match.group(1)
            semester = semester_match.group(2)
            exam_code = semester_match.group(3)
            exam_type = EXAM_TYPE_MAP.get(exam_code, "시험")
            semester_info = f"_{grade}_{semester}_{exam_type}"

    return f"[{school_name}_{year}{semester_info}]"
