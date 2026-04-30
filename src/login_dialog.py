from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox,
)
from PyQt5.QtCore import Qt
import credentials


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HiWorks 로그인 설정")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setFixedWidth(300)
        self._build_ui()
        self._load_existing()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(QLabel("회사 도메인"))
        self._domain_edit = QLineEdit()
        self._domain_edit.setPlaceholderText("예: mycompany.com")
        layout.addWidget(self._domain_edit)

        layout.addWidget(QLabel("아이디 (사원번호 또는 이메일)"))
        self._id_edit = QLineEdit()
        self._id_edit.setPlaceholderText("예: hong.gildong")
        layout.addWidget(self._id_edit)

        layout.addWidget(QLabel("비밀번호"))
        self._pw_edit = QLineEdit()
        self._pw_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self._pw_edit)

        layout.addSpacing(4)

        note = QLabel(
            "※ 자격증명은 Windows 자격증명 관리자에 안전하게 저장됩니다."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(note)

        layout.addSpacing(4)

        btn_row = QHBoxLayout()
        btn_save = QPushButton("저장")
        btn_cancel = QPushButton("취소")
        btn_save.setDefault(True)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        btn_save.clicked.connect(self._save)
        btn_cancel.clicked.connect(self.reject)
        self._pw_edit.returnPressed.connect(self._save)

    def _load_existing(self):
        creds = credentials.load()
        if creds:
            self._id_edit.setText(creds[0])
            self._domain_edit.setText(creds[2])
            self._pw_edit.setFocus()
        else:
            self._domain_edit.setFocus()

    def _save(self):
        domain = self._domain_edit.text().strip()
        uid = self._id_edit.text().strip()
        pw = self._pw_edit.text()
        if not domain or not uid or not pw:
            QMessageBox.warning(self, "입력 오류", "회사 도메인, 아이디, 비밀번호를 모두 입력해주세요.")
            return
        credentials.save(uid, pw, domain)
        self.accept()
