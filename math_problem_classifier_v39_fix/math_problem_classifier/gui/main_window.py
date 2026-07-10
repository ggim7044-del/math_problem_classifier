# -*- coding: utf-8 -*-
"""
gui/main_window.py

프로그램의 메인 윈도우(화면)를 담당하는 모듈입니다.

역할:
- HWP 파일 여러 개 선택
- 중단원 개별 등록/수정/삭제 (리스트 관리)
- 시작 버튼으로 처리 시작
- 진행률 / 현재 처리 파일 / 로그 출력을 화면에 표시
"""

import os

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QInputDialog,
    QCheckBox,
    QScrollArea,
    QFrame,
)

from config.settings import OUTPUT_HWP_DIR
from utils.logger import Logger
from workers.batch_worker import BatchWorker
from workers.reprocess_worker import ReprocessWorker


class ChapterItemWidget(QWidget):
    """중단원 리스트의 각 항목을 표시하는 커스텀 위젯 (이름 + 수정/삭제 버튼)"""

    def __init__(self, name, parent_list_widget, on_edit, on_delete):
        super().__init__()
        self.name = name
        self.parent_list_widget = parent_list_widget
        self.on_edit = on_edit
        self.on_delete = on_delete

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)

        self.label = QLabel(name)
        layout.addWidget(self.label)
        layout.addStretch()

        btn_edit = QPushButton("수정")
        btn_edit.setFixedWidth(40)
        btn_edit.clicked.connect(lambda: self.on_edit(self))
        layout.addWidget(btn_edit)

        btn_delete = QPushButton("삭제")
        btn_delete.setFixedWidth(40)
        btn_delete.clicked.connect(lambda: self.on_delete(self))
        layout.addWidget(btn_delete)

        self.setLayout(layout)


class MainWindow(QMainWindow):
    """수학 문제은행 자동 분류 프로그램의 메인 윈도우"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("수학 문제은행 자동 분류 프로그램")
        self.resize(850, 900)

        # 데이터 관리
        self.selected_files: list[str] = []
        self.chapters: list[str] = []

        # 로거 생성
        self.logger = Logger()
        self.logger.log_signal.connect(self._append_log)

        self.worker = None
        self.reprocess_worker = None
        self._reprocess_checkboxes: list[tuple[QCheckBox, str]] = []  # (체크박스, 파일경로)
        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # 상단: 파일 선택 및 중단원 관리 (가로 배치)
        top_layout = QHBoxLayout()
        top_layout.addWidget(self._build_file_selection_group(), 1)
        top_layout.addWidget(self._build_chapter_management_group(), 1)
        main_layout.addLayout(top_layout)

        # 중단: 예외 재처리
        main_layout.addWidget(self._build_reprocess_group())

        # 하단: 진행 상태 및 로그
        main_layout.addWidget(self._build_progress_group())
        main_layout.addWidget(self._build_log_group())

        # 액션 버튼
        main_layout.addLayout(self._build_action_buttons())

    def _build_file_selection_group(self) -> QGroupBox:
        group = QGroupBox("1. HWP 파일 선택")
        layout = QVBoxLayout()
        group.setLayout(layout)

        btn_layout = QHBoxLayout()
        self.btn_select_files = QPushButton("파일 추가")
        self.btn_select_files.clicked.connect(self._on_select_files_clicked)
        self.btn_clear_files = QPushButton("목록 비우기")
        self.btn_clear_files.clicked.connect(self._on_clear_files_clicked)

        btn_layout.addWidget(self.btn_select_files)
        btn_layout.addWidget(self.btn_clear_files)
        layout.addLayout(btn_layout)

        self.list_files = QListWidget()
        self.list_files.setMaximumHeight(150)
        layout.addWidget(self.list_files)

        self.lbl_file_count = QLabel("선택된 파일: 0개")
        layout.addWidget(self.lbl_file_count)

        return group

    def _build_chapter_management_group(self) -> QGroupBox:
        group = QGroupBox("2. 중단원 관리")
        layout = QVBoxLayout()
        group.setLayout(layout)

        input_layout = QHBoxLayout()
        self.input_chapter = QLineEdit()
        self.input_chapter.setPlaceholderText("중단원명 입력 후 Enter")
        self.input_chapter.returnPressed.connect(self._on_add_chapter_clicked)

        btn_add = QPushButton("추가")
        btn_add.clicked.connect(self._on_add_chapter_clicked)

        input_layout.addWidget(self.input_chapter)
        input_layout.addWidget(btn_add)
        layout.addLayout(input_layout)

        self.list_chapters = QListWidget()
        self.list_chapters.setMaximumHeight(150)
        layout.addWidget(self.list_chapters)

        layout.addWidget(QLabel("* 문제 내 [중단원] 태그와 일치하는 항목만 분류됩니다."))

        return group

    def _build_progress_group(self) -> QGroupBox:
        group = QGroupBox("진행 상태")
        layout = QVBoxLayout()
        group.setLayout(layout)

        self.lbl_current_file = QLabel("대기 중...")
        layout.addWidget(self.lbl_current_file)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        return group

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("로그")
        layout = QVBoxLayout()
        group.setLayout(layout)

        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        layout.addWidget(self.text_log)

        return group

    def _build_reprocess_group(self) -> QGroupBox:
        """예외 파일 재처리 섹션 빌드"""
        group = QGroupBox("3. 예외 파일 재처리 (output/오류/ 폴더)")
        layout = QVBoxLayout()
        group.setLayout(layout)

        # 새로고침 + 재처리 버튼
        btn_row = QHBoxLayout()
        self.btn_refresh_exceptions = QPushButton("🔄 목록 새로고침")
        self.btn_refresh_exceptions.clicked.connect(self._on_refresh_exceptions_clicked)
        self.btn_reprocess = QPushButton("▶ 선택 파일 재처리")
        self.btn_reprocess.clicked.connect(self._on_reprocess_clicked)
        self.btn_reprocess.setStyleSheet("font-weight: bold;")
        btn_row.addWidget(self.btn_refresh_exceptions)
        btn_row.addWidget(self.btn_reprocess)
        layout.addLayout(btn_row)

        # 스크롤 가능한 체크박스 목록
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(130)
        self._reprocess_list_widget = QWidget()
        self._reprocess_list_layout = QVBoxLayout(self._reprocess_list_widget)
        self._reprocess_list_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._reprocess_list_widget)
        layout.addWidget(scroll)

        self.lbl_reprocess_hint = QLabel(
            "* '목록 새로고침'을 눌러 output/오류/ 안의 HWP 파일을 불러오세요.\n"
            "  재처리 성공한 문제는 output/오류/재처리완료/ 에 저장됩니다."
        )
        self.lbl_reprocess_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.lbl_reprocess_hint)

        return group

    def _build_action_buttons(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.btn_start = QPushButton("분류 시작")
        self.btn_start.setMinimumHeight(50)
        self.btn_start.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.btn_start.clicked.connect(self._on_start_clicked)
        layout.addWidget(self.btn_start)
        return layout

    # ------------------------------------------------------------------
    # 이벤트 핸들러 - 예외 재처리
    # ------------------------------------------------------------------
    def _on_refresh_exceptions_clicked(self):
        """output/오류/ 폴더 안의 HWP 파일 목록을 체크박스로 표시합니다."""
        error_dir = os.path.join(OUTPUT_HWP_DIR, "오류")

        # 기존 체크박스 초기화
        while self._reprocess_list_layout.count():
            item = self._reprocess_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._reprocess_checkboxes.clear()

        if not os.path.isdir(error_dir):
            QMessageBox.information(self, "알림", f"폴더가 없습니다: {error_dir}")
            return

        hwp_files = [
            f for f in os.listdir(error_dir)
            if f.endswith(".hwp") and os.path.isfile(os.path.join(error_dir, f))
        ]

        if not hwp_files:
            lbl = QLabel("(재처리 가능한 HWP 파일이 없습니다)")
            lbl.setStyleSheet("color: gray;")
            self._reprocess_list_layout.addWidget(lbl)
            return

        for fname in sorted(hwp_files):
            fpath = os.path.join(error_dir, fname)
            cb = QCheckBox(fname)
            cb.setChecked(True)
            self._reprocess_list_layout.addWidget(cb)
            self._reprocess_checkboxes.append((cb, fpath))

    def _on_reprocess_clicked(self):
        """체크된 예외 HWP 파일들을 재처리합니다."""
        if not self.chapters:
            QMessageBox.warning(self, "알림", "중단원을 먼저 등록해주세요.")
            return

        selected = [path for cb, path in self._reprocess_checkboxes if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "알림", "재처리할 파일을 체크해주세요.")
            return

        self.btn_reprocess.setEnabled(False)
        self.btn_start.setEnabled(False)
        self.progress_bar.setValue(0)
        self.lbl_current_file.setText("재처리 준비 중...")

        self.reprocess_worker = ReprocessWorker(selected, self.chapters, self.logger)
        self.reprocess_worker.current_file_signal.connect(self.update_current_file)
        self.reprocess_worker.finished_signal.connect(self._on_reprocess_finished)
        self.reprocess_worker.start()

    def _on_reprocess_finished(self, success: bool, message: str):
        self.btn_reprocess.setEnabled(True)
        self.btn_start.setEnabled(True)
        self.lbl_current_file.setText("대기 중")
        if success:
            QMessageBox.information(self, "재처리 완료", message)
        else:
            QMessageBox.critical(self, "재처리 오류", f"오류: {message}")

    # ------------------------------------------------------------------
    # 이벤트 핸들러 - 파일 관리
    # ------------------------------------------------------------------
    def _on_select_files_clicked(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "HWP 파일 선택", "", "HWP Files (*.hwp)"
        )
        if not files:
            return

        for f in files:
            if f not in self.selected_files:
                self.selected_files.append(f)
                self.list_files.addItem(os.path.basename(f))

        self.lbl_file_count.setText(f"선택된 파일: {len(self.selected_files)}개")

    def _on_clear_files_clicked(self):
        self.selected_files.clear()
        self.list_files.clear()
        self.lbl_file_count.setText("선택된 파일: 0개")

    # ------------------------------------------------------------------
    # 이벤트 핸들러 - 중단원 관리
    # ------------------------------------------------------------------
    def _on_add_chapter_clicked(self):
        name = self.input_chapter.text().strip()
        if not name:
            return

        if name in self.chapters:
            QMessageBox.warning(self, "알림", "이미 등록된 중단원입니다.")
            return

        self.chapters.append(name)
        self._add_chapter_to_list(name)
        self.input_chapter.clear()

    def _add_chapter_to_list(self, name):
        item = QListWidgetItem(self.list_chapters)
        widget = ChapterItemWidget(name, self.list_chapters, self._on_edit_chapter, self._on_delete_chapter)
        item.setSizeHint(widget.sizeHint())
        self.list_chapters.addItem(item)
        self.list_chapters.setItemWidget(item, widget)

    def _on_edit_chapter(self, widget):
        old_name = widget.name
        new_name, ok = QInputDialog.getText(self, "중단원 수정", "새 이름을 입력하세요:", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            new_name = new_name.strip()
            if new_name in self.chapters:
                QMessageBox.warning(self, "알림", "이미 존재하는 이름입니다.")
                return

            idx = self.chapters.index(old_name)
            self.chapters[idx] = new_name
            widget.name = new_name
            widget.label.setText(new_name)

    def _on_delete_chapter(self, widget):
        name = widget.name
        self.chapters.remove(name)

        for i in range(self.list_chapters.count()):
            item = self.list_chapters.item(i)
            if self.list_chapters.itemWidget(item) == widget:
                self.list_chapters.takeItem(i)
                break

    # ------------------------------------------------------------------
    # 이벤트 핸들러 - 실행
    # ------------------------------------------------------------------
    def _on_start_clicked(self):
        if not self.selected_files:
            QMessageBox.warning(self, "알림", "먼저 HWP 파일을 선택해주세요.")
            return

        if not self.chapters:
            QMessageBox.warning(self, "알림", "최소 하나 이상의 중단원을 등록해주세요.")
            return

        self.btn_start.setEnabled(False)
        self.btn_select_files.setEnabled(False)
        self.btn_clear_files.setEnabled(False)
        self.input_chapter.setEnabled(False)

        self.progress_bar.setValue(0)
        self.lbl_current_file.setText("준비 중...")

        # 워커 실행 (중단원 목록 전체 전달)
        # chapter_name 인자 대신 chapters 리스트를 전달하도록 BatchWorker 수정 필요
        self.worker = BatchWorker(self.selected_files, self.chapters, self.logger)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.current_file_signal.connect(self.update_current_file)
        self.worker.finished_signal.connect(self._on_processing_finished)
        self.worker.start()

    def _on_processing_finished(self, success: bool, message: str):
        self.btn_start.setEnabled(True)
        self.btn_select_files.setEnabled(True)
        self.btn_clear_files.setEnabled(True)
        self.input_chapter.setEnabled(True)

        if success:
            QMessageBox.information(self, "완료", message)
        else:
            QMessageBox.critical(self, "오류", f"처리 중 오류가 발생했습니다:\n{message}")

        self.lbl_current_file.setText("대기 중")

    def update_progress(self, current: int, total: int):
        percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percent)

    def update_current_file(self, filename: str):
        self.lbl_current_file.setText(f"처리 중: {os.path.basename(filename)}")

    def _append_log(self, message: str):
        self.text_log.append(message)
