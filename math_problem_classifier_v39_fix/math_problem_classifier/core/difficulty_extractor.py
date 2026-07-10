# -*- coding: utf-8 -*-
"""
core/difficulty_extractor.py

문제의 일반 텍스트(plain_text)에서 [난이도] 및 [중단원] 값을 추출하는 모듈입니다.
"""

import re
from typing import Optional

from config.settings import DIFFICULTY_PATTERN, VALID_DIFFICULTIES

# [난이도] 키워드 뒤의 값을 유효 여부에 관계없이 캡처하는 정규식
# 다음 대괄호가 시작되거나 줄이 바뀌기 전까지의 비공백 문자를 가져옵니다.
_difficulty_raw_regex = re.compile(r"\[\s*난이도\s*\]\s*([^\]\r\n\s]+)")

# [중단원] 키워드 뒤의 값을 캡처하는 정규식
# [난이도] 등 다른 태그가 바로 붙어있는 경우를 대비해 대괄호('[')를 만나기 전까지로 제한합니다.
_chapter_raw_regex = re.compile(r"\[\s*중단원\s*\]\s*([^\[\]\r\n]+)")


def extract_difficulty(problem_text: str) -> Optional[str]:
    """
    문제 텍스트 안에서 '[난이도] 상/중/하' 패턴을 찾아 값을 반환합니다.
    """
    # 정확한 상/중/하 매칭을 위해 settings의 패턴 사용
    match = re.search(DIFFICULTY_PATTERN, problem_text)
    if not match:
        return None

    value = match.group(1).strip()
    if value in VALID_DIFFICULTIES:
        return value
    return None


def extract_difficulty_raw(problem_text: str) -> str:
    """
    문제 텍스트 안에서 '[난이도]' 키워드 뒤의 원본 값을 반환합니다.
    """
    match = _difficulty_raw_regex.search(problem_text)
    if not match:
        return ""
    return match.group(1).strip()


def extract_chapter_raw(problem_text: str) -> str:
    """
    문제 텍스트 안에서 '[중단원]' 키워드 뒤의 원본 값을 반환합니다.
    """
    match = _chapter_raw_regex.search(problem_text)
    if not match:
        return ""
    return match.group(1).strip()
