# -*- coding: utf-8 -*-
"""
core/models.py

프로그램 전체에서 공유되는 데이터 클래스(모델)를 정의합니다.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProblemBlock:
    """
    HWP 문서 안에서 인식된 '문제 하나'의 위치와 정보를 담는 클래스.
    """

    index: int                  # 문서 내에서 몇 번째로 인식된 문제인지
    problem_number: str         # 원본 문제 번호 문자열

    start_list: int             # 시작 위치의 List 값
    start_para: int             # 시작 문단 번호
    start_pos: int              # 시작 문단 내 글자 위치

    end_list: int                # 끝 위치의 List 값
    end_para: int                # 끝 문단 번호
    end_pos: int                  # 끝 문단 내 글자 위치

    plain_text: str               # 문제 블록의 일반 텍스트

    difficulty: Optional[str] = None  # '상' / '중' / '하'
    chapter: str = ""             # 추출된 중단원명
    source_file: str = ""        # 원본 HWP 파일 경로


@dataclass
class ExceptionProblem:
    """
    예외 상황별 사유:
    - "invalid_difficulty" : 난이도가 상/중/하가 아님
    - "no_difficulty_tag"  : [난이도] 태그가 없음
    - "invalid_chapter"    : 중단원이 등록된 목록에 없음
    - "no_chapter_tag"     : [중단원] 태그가 없음
    """

    source_file: str            # 원본 HWP 파일 경로
    problem_number: str         # 문제 번호
    reason: str                 # 예외 사유
    raw_difficulty: str         # 추출된 난이도 원본 값
    raw_chapter: str            # 추출된 중단원 원본 값
    plain_text_preview: str     # 문제 텍스트 미리보기
