# -*- coding: utf-8 -*-
"""
core/backup_manager.py

기존에 존재하는 출력 HWP 파일(예: 고차방정식_상.hwp)을 프로그램이 열어서
수정하기 전에, 원본을 안전하게 보관하기 위한 백업 기능을 제공합니다.

동작:
- config/settings.py의 BACKUP_DIR 폴더에 타임스탬프가 붙은 이름으로 복사본을 만듭니다.
  예) backup/고차방정식_상_20260708_143210.hwp
"""

import os
import shutil
from datetime import datetime
from typing import Optional

from config.settings import BACKUP_DIR


def create_backup(filepath: str) -> Optional[str]:
    """
    filepath가 실제로 존재하면, 백업 폴더에 타임스탬프를 붙여 복사본을 생성합니다.

    Args:
        filepath: 백업할 원본 파일 경로

    Returns:
        생성된 백업 파일의 경로. 원본 파일이 없으면 None (백업할 대상이 없으므로).

    Raises:
        OSError: 복사 중 디스크 오류 등이 발생한 경우
    """
    if not os.path.exists(filepath):
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    ext = os.path.splitext(filepath)[1]
    backup_path = os.path.join(BACKUP_DIR, f"{base_name}_{timestamp}{ext}")

    shutil.copy2(filepath, backup_path)
    return backup_path
