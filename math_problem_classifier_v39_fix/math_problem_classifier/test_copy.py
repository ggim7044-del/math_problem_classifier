# -*- coding: utf-8 -*-
"""
test_copy.py

프로젝트에서 가장 핵심적인 기능인
"HWP 문제 블록을 원본 서식 그대로 다른 HWP 문서에 복사"
가 실제로 정상 동작하는지 확인하기 위한 단독 테스트 스크립트입니다.

사용 방법 (Windows + 한글 프로그램 설치 환경에서 실행):
    python test_copy.py

동작:
1. 파일 선택 창에서 HWP 파일 하나를 선택합니다.
2. 문서에서 '첫 번째 문제 블록'만 찾습니다. (core.problem_locator 사용)
3. test_output.hwp 라는 새 빈 문서를 만듭니다.
4. 첫 번째 문제 블록을 서식(수식/표/그림/미주/자동번호 등) 그대로 복사해 넣습니다.
5. test_output.hwp로 저장합니다.

주의:
- 한글 창(visible=True)을 그대로 열어두므로, 스크립트 실행이 끝난 뒤
  '한글' 프로그램에서 test_output.hwp 내용을 직접 눈으로 확인하시면 됩니다.
  (확인 후에는 한글 창을 직접 닫아주세요)
- 오류가 발생하면 한글 프로세스를 정리(quit)한 뒤 오류 메시지를 출력합니다.
"""

import os
import sys
import traceback

# tkinter는 파이썬 표준 라이브러리이므로 별도 설치 없이 파일 선택 창에 사용합니다.
from tkinter import Tk
from tkinter.filedialog import askopenfilename

from core.hwp_session import HwpSession, HwpSessionError
from core.problem_locator import ProblemLocator, ProblemLocatorError
from utils.logger import Logger


# 결과 파일이 저장될 경로 (현재 작업 폴더 기준)
OUTPUT_PATH = os.path.join(os.getcwd(), "test_output.hwp")


def select_hwp_file() -> str:
    """파일 선택 창을 띄워 사용자가 HWP 파일 하나를 고르게 합니다."""
    root = Tk()
    root.withdraw()  # 불필요한 tkinter 메인 창은 숨김
    root.attributes("-topmost", True)  # 파일선택창이 뒤로 숨지 않도록

    filepath = askopenfilename(
        title="테스트할 HWP 파일을 선택하세요",
        filetypes=[("HWP 파일", "*.hwp")],
    )
    root.destroy()
    return filepath


def find_document_by_path(hwp, filepath: str):
    """현재 열려있는 문서(XHwpDocuments) 중 filepath와 일치하는 문서 객체를 찾습니다."""
    normalized_target = os.path.normpath(filepath)
    count = hwp.XHwpDocuments.Count
    for i in range(count):
        doc = hwp.XHwpDocuments.Item(i)
        try:
            if os.path.normpath(doc.FullName) == normalized_target:
                return doc
        except Exception:
            continue
    return None


def main():
    print("=" * 60)
    print("HWP 서식 유지 복사 기능 테스트")
    print("=" * 60)

    # 1) HWP 파일 선택
    filepath = select_hwp_file()
    if not filepath:
        print("파일을 선택하지 않아 종료합니다.")
        return

    print(f"\n[1/5] 선택한 파일: {filepath}")

    session = None
    try:
        # 한글 프로그램을 화면에 보이는 상태로 실행 (결과를 직접 눈으로 확인하기 위함)
        print("\n[2/5] 한글 프로그램 실행 중...")
        session = HwpSession(visible=True)

        # 2) 원본 파일 열기
        session.open_document(filepath)
        source_doc = find_document_by_path(session.hwp, filepath)
        if source_doc is None:
            raise HwpSessionError(
                "원본 파일을 열었지만 문서 목록에서 찾지 못했습니다."
            )
        source_doc.SetActive_XHwpDocument()
        print("    → 원본 파일 열기 완료")

        # 2-1) 로거 준비: error_log.txt 기록 + 콘솔 출력도 함께 볼 수 있도록 연결
        logger = Logger()
        logger.log_signal.connect(print)

        # 3) 첫 번째 문제 블록 찾기
        print("\n[3/5] 문제 블록 인식 중... (자동번호/미주 컨트롤 구조 기반)")
        locator = ProblemLocator(logger=logger)
        problems, exceptions = locator.locate_problems(session.hwp, source_file=filepath)

        if not problems:
            raise ProblemLocatorError("문제를 하나도 찾지 못했습니다.")

        first = problems[0]
        print(f"    → 총 {len(problems)}개 문제 인식됨")
        print(f"    → 첫 번째 문제 번호: {first.problem_number}")
        print(f"    → 시작 좌표: (para={first.start_para}, pos={first.start_pos})")
        print(f"    → 끝 좌표:   (para={first.end_para}, pos={first.end_pos})")
        print(f"    → 난이도: {first.difficulty or '(인식 실패)'}")
        preview = first.plain_text[:100].replace("\n", " ")
        print(f"    → 문제 앞부분(100자): {preview}")

        # 4) 새 빈 문서(test_output.hwp) 생성
        print("\n[4/5] 새 결과 문서(test_output.hwp) 생성 중...")
        output_doc = session.create_blank_document()

        # 원본 문서 재활성화 후, 첫 번째 문제 블록을 서식 그대로(HWP 포맷) 추출
        source_doc.SetActive_XHwpDocument()
        session.hwp.select_text(
            first.start_para, first.start_pos,
            first.end_para, first.end_pos,
            first.start_list,
        )
        block_data = session.hwp.GetTextFile(format="HWP", option="saveblock")
        session.hwp.Cancel()  # 선택 해제

        if not block_data:
            raise HwpSessionError("문제 블록 추출 결과가 비어 있습니다.")

        # 결과 문서에 서식 그대로 삽입
        output_doc.SetActive_XHwpDocument()
        session.hwp.MoveDocEnd()
        session.hwp.SetTextFile(block_data, format="HWP")
        print("    → 서식 유지 복사 완료 (수식/표/그림/미주/자동번호 포함 여부는 육안 확인 필요)")

        # 5) 저장
        print("\n[5/5] 저장 중...")
        output_doc.SetActive_XHwpDocument()
        session.hwp.save_as(OUTPUT_PATH)
        print(f"    → 저장 완료: {OUTPUT_PATH}")

        print("\n" + "=" * 60)
        print("복사가 완료되었습니다.")
        print("수식, 표, 그림, 미주, 자동번호를 확인해주세요.")
        print("=" * 60)

        # Windows에서 결과 파일을 탐색기 기본 연결 프로그램(한글)으로 자동으로 열어줌
        try:
            os.startfile(OUTPUT_PATH)
            print(f"\ntest_output.hwp 파일을 자동으로 열었습니다: {OUTPUT_PATH}")
        except Exception as e:
            print(f"\n[안내] 파일 자동 열기에 실패했습니다 ({e}). 직접 열어서 확인해주세요.")

        print("\n확인이 끝나면 한글 창을 직접 닫아주시면 됩니다.")

        # 정상 종료 시에는 세션을 종료하지 않고 한글 창을 그대로 열어둡니다.
        # (육안 확인이 끝난 뒤 사용자가 직접 닫도록 함)

    except (HwpSessionError, ProblemLocatorError) as e:
        print(f"\n[오류] {e}")
        if session:
            session.quit()
        sys.exit(1)

    except Exception as e:
        print(f"\n[예상하지 못한 오류] {e}")
        traceback.print_exc()
        if session:
            session.quit()
        sys.exit(1)


if __name__ == "__main__":
    main()
