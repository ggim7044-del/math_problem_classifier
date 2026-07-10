# -*- coding: utf-8 -*-
"""
core/hwp_session.py

pyhwpx의 Hwp 인스턴스 생성 및 해제를 관리하는 래퍼 클래스입니다.
"""

from __future__ import annotations


class HwpSessionError(Exception):
    """HWP 세션 생성/조작 중 발생하는 예외"""
    pass


class HwpSession:
    """
    한글(HWP) 자동화 세션 관리 클래스
    """

    def __init__(self, visible: bool = False):
        try:
            import pyhwpx
        except ImportError as e:
            raise HwpSessionError(
                "pyhwpx 모듈을 불러올 수 없습니다. "
                "pip install pyhwpx 설치 여부를 확인해주세요."
            ) from e

        try:
            self.hwp = pyhwpx.Hwp(visible=visible)
        except Exception as e:
            raise HwpSessionError(
                f"한글 프로그램 실행(Automation)에 실패했습니다: {e}"
            ) from e

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()
        return False

    def open_document(self, filepath: str):
        try:
            result = self.hwp.open(filepath)
            if result is False:
                raise HwpSessionError(f"파일을 열 수 없습니다: {filepath}")
        except HwpSessionError:
            raise
        except Exception as e:
            raise HwpSessionError(f"파일 읽기 실패 ({filepath}): {e}") from e

    def create_blank_document(self):
        try:
            new_doc = self.hwp.add_doc()
            return new_doc
        except Exception as e:
            raise HwpSessionError(f"새 문서 생성 실패: {e}") from e

    def quit(self):
        """한글 프로그램을 종료합니다."""
        try:
            if hasattr(self, "hwp") and self.hwp is not None:
                # pyhwpx는 소문자 quit()를 권장함
                self.hwp.quit()
        except Exception:
            pass
