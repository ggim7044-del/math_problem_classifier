# -*- coding: utf-8 -*-
"""
diag_ctrls.py

목적: 문제 번호가 어떤 컨트롤(atno/nwno 등)로 구현되어 있는지,
문서 내 몇 개가 있는지, 각각의 위치(List/Para/Pos)와 그 지점의
주변 텍스트가 무엇인지 눈으로 확인하기 위한 진단 스크립트입니다.

이 스크립트는 아직 어떤 것도 수정하지 않고, "읽기 전용"으로 구조만 출력합니다.

사용법 (Windows + 한글 환경, math_problem_classifier 폴더 안에서):
    python diag_ctrls.py
"""

import os
from tkinter import Tk
from tkinter.filedialog import askopenfilename

from core.hwp_session import HwpSession, HwpSessionError


def select_hwp_file() -> str:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    filepath = askopenfilename(
        title="진단할 HWP 파일을 선택하세요",
        filetypes=[("HWP 파일", "*.hwp")],
    )
    root.destroy()
    return filepath


def find_document_by_path(hwp, filepath: str):
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


def get_preview_text_at(hwp, list_id, para, pos, length=40):
    """
    해당 좌표(List/Para/Pos)부터 length자 정도의 텍스트를 미리보기로 가져옵니다.
    (해당 문단 전체를 선택해서 앞부분만 잘라서 보여주는 방식)
    """
    try:
        hwp.set_pos(list_id, para, pos)
        hwp.MoveSelParaEnd()
        text = hwp.get_selected_text() or ""
        hwp.Cancel()
        preview = text[:length].replace("\n", " ").replace("\r", " ")
        return preview
    except Exception as e:
        return f"(미리보기 실패: {e})"


def main():
    print("=" * 70)
    print("HWP 컨트롤 구조 진단 (자동번호/필드/컨트롤 종류 확인)")
    print("=" * 70)

    filepath = select_hwp_file()
    if not filepath:
        print("파일을 선택하지 않아 종료합니다.")
        return

    print(f"\n선택한 파일: {filepath}")

    session = None
    try:
        print("\n한글 프로그램 실행 중...")
        session = HwpSession(visible=True)

        session.open_document(filepath)
        doc = find_document_by_path(session.hwp, filepath)
        if doc is None:
            raise HwpSessionError("파일을 열었지만 문서 목록에서 찾지 못했습니다.")
        doc.SetActive_XHwpDocument()
        print("파일 열기 완료\n")

        hwp = session.hwp

        # 1) 문서 내 모든 컨트롤 종류별 개수 집계
        print("-" * 70)
        print("[1] 문서 내 전체 컨트롤 종류별 개수")
        print("-" * 70)
        ctrl_counts = {}
        all_ctrls = list(hwp.ctrl_list)
        for ctrl in all_ctrls:
            cid = ctrl.CtrlID
            ctrl_counts[cid] = ctrl_counts.get(cid, 0) + 1

        for cid, cnt in sorted(ctrl_counts.items(), key=lambda x: -x[1]):
            print(f"    {cid!r:8s} : {cnt}개")

        print(f"\n    (전체 컨트롤 수: {len(all_ctrls)}개)")

        # 2) atno / nwno 컨트롤만 추려서, 위치와 그 지점 주변 텍스트 출력
        print("\n" + "-" * 70)
        print("[2] 자동번호 계열 컨트롤(atno, nwno) 상세 목록")
        print("-" * 70)

        target_ids = {"atno", "nwno"}
        numbered = [c for c in all_ctrls if c.CtrlID in target_ids]

        if not numbered:
            print("    atno/nwno 컨트롤을 하나도 찾지 못했습니다.")
            print("    (다른 컨트롤 ID를 쓰고 있을 수 있습니다. 위 [1] 목록을 확인해주세요.)")
        else:
            print(f"    총 {len(numbered)}개 발견\n")
            for i, ctrl in enumerate(numbered):
                try:
                    pos = hwp.get_ctrl_pos(ctrl, option=1)  # (List, Para, Pos)
                except Exception as e:
                    print(f"    [{i+1}] 위치 조회 실패: {e}")
                    continue

                preview = get_preview_text_at(hwp, *pos)
                print(f"    [{i+1}] CtrlID={ctrl.CtrlID!r}  위치(List,Para,Pos)={pos}")
                print(f"         주변 텍스트: {preview}")
                print()

        print("=" * 70)
        print("진단 완료. 위 [2] 목록의 개수가 실제 '문제 개수'(예: 22개)와")
        print("일치하는지, 각 위치의 '주변 텍스트'가 실제 문제 시작 부분과")
        print("일치하는지 확인해주세요.")
        print("=" * 70)
        print("\n확인이 끝나면 한글 창을 직접 닫아주시면 됩니다.")

    except Exception as e:
        print(f"\n[오류] {e}")
        import traceback
        traceback.print_exc()
        if session:
            session.quit()


if __name__ == "__main__":
    main()
