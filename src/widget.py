import json
import os
from pathlib import Path
from datetime import datetime, timedelta

from PyQt5.QtWidgets import QWidget, QApplication, QMenu
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QFontMetrics,
    QPainterPath, QLinearGradient,
)

import credentials
import startup
from scraper import ScraperThread
from login_dialog import LoginDialog

CONFIG_DIR = Path(os.environ.get("APPDATA", ".")) / "HiworksTimeWidget"
CONFIG_FILE = CONFIG_DIR / "config.json"

W, H = 118, 56                          # 위젯 크기 (바탕화면 아이콘 수준)
REFRESH_INTERVAL_MS = 60 * 60 * 1000   # 1시간마다 hiworks 재조회


class DesktopWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._clock_in: str | None = None
        self._status = "idle"   # idle | no_creds | loading | ok | error
        self._error_msg = ""
        self._drag_pos: QPoint | None = None
        self._thread: ScraperThread | None = None

        self._init_window()
        self._restore_position()
        self._start_auto_refresh()
        self._start_minute_tick()
        QTimer.singleShot(300, self._on_startup)

    # ── 초기화 ────────────────────────────────────────────────────────────────

    def _init_window(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool                   # 작업표시줄 미노출
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(W, H)

    def _on_startup(self):
        creds = credentials.load()
        if creds is None:
            self._status = "no_creds"
            self.update()
        else:
            self._fetch(*creds)

    # ── 데이터 수집 ───────────────────────────────────────────────────────────

    def _fetch(self, username: str, password: str):
        if self._thread and self._thread.isRunning():
            return
        self._status = "loading"
        self.update()
        self._thread = ScraperThread(username, password, self)
        self._thread.success.connect(self._on_success)
        self._thread.failure.connect(self._on_failure)
        self._thread.start()

    def _on_success(self, clock_in: str):
        self._clock_in = clock_in
        self._status = "ok"
        self.update()

    def _on_failure(self, msg: str):
        self._status = "error"
        self._error_msg = msg
        self.update()

    def _start_auto_refresh(self):
        t = QTimer(self)
        t.timeout.connect(self._refresh)
        t.start(REFRESH_INTERVAL_MS)

    def _start_minute_tick(self):
        t = QTimer(self)
        t.timeout.connect(self.update)  # 1분마다 repaint → 남은 시간 갱신
        t.start(60_000)

    def _refresh(self):
        creds = credentials.load()
        if creds:
            self._fetch(*creds)

    # ── 렌더링 ────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        # 10% opacity 둥근 배경
        self._draw_bg(p)

        if self._status == "no_creds":
            self._draw_login_button(p)
        elif self._status == "loading":
            self._draw_times(p, "…", "…")
        elif self._status == "error":
            self._draw_error(p)
        elif self._status == "ok" and self._clock_in:
            self._draw_times(p, self._clock_in, self._remaining())

    def _draw_bg(self, p: QPainter):
        path = QPainterPath()
        path.addRoundedRect(0, 0, W, H, 10, 10)
        p.fillPath(path, QColor(0, 0, 0, 26))  # 검정 10% (255 * 0.1 ≈ 26)

    def _draw_times(self, p: QPainter, line1: str, line2: str):
        # 퇴근 가능 여부에 따라 두 번째 줄 색상 결정
        can_leave = self._can_leave()
        color2 = QColor(100, 255, 120) if can_leave else QColor(80, 210, 255)

        font = QFont("Segoe UI", 13, QFont.Bold)
        p.setFont(font)
        fm = QFontMetrics(font)
        lh = fm.height()
        gap = 2
        total = lh * 2 + gap
        base_y = (H - total) // 2 + fm.ascent()

        rows = [
            (line1, QColor(255, 220, 80)),  # 출근 — 노란색
            (line2, color2),                # 남은 시간 — 하늘색 / 퇴근 가능 — 초록색
        ]
        for i, (text, color) in enumerate(rows):
            tw = fm.horizontalAdvance(text)
            x = (W - tw) // 2
            y = base_y + i * (lh + gap)
            p.setPen(QColor(0, 0, 0, 160))
            p.drawText(x + 1, y + 1, text)
            p.setPen(color)
            p.drawText(x, y, text)

    def _draw_login_button(self, p: QPainter):
        mx, my, mw, mh = 8, 10, W - 16, H - 20
        path = QPainterPath()
        path.addRoundedRect(mx, my, mw, mh, 8, 8)
        p.fillPath(path, QColor(30, 30, 30, 210))

        font = QFont("Segoe UI", 9, QFont.Bold)
        p.setFont(font)
        p.setPen(QColor(220, 220, 220))
        p.drawText(mx, my, mw, mh, Qt.AlignCenter, "⚙ 로그인 설정")

    def _draw_error(self, p: QPainter):
        font = QFont("Segoe UI", 8)
        p.setFont(font)
        fm = QFontMetrics(font)
        text = "⚠ 조회 실패"
        tw = fm.horizontalAdvance(text)
        p.setPen(QColor(0, 0, 0, 140))
        p.drawText((W - tw) // 2 + 1, H // 2 + fm.ascent() // 2 + 1, text)
        p.setPen(QColor(255, 100, 100))
        p.drawText((W - tw) // 2, H // 2 + fm.ascent() // 2, text)

    # ── 마우스 ────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            if self._status == "no_creds":
                self._open_login()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_pos:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = None
            self._save_position()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._refresh()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#2b2b2b; color:white; border:1px solid #555; }"
            "QMenu::item { padding:5px 18px; }"
            "QMenu::item:selected { background:#444; }"
            "QMenu::separator { height:1px; background:#555; margin:2px 0; }"
        )
        menu.addAction("새로고침", self._refresh)
        menu.addAction("로그인 설정", self._open_login)
        menu.addSeparator()

        reg = startup.is_registered()
        act = menu.addAction("시작프로그램 해제" if reg else "시작프로그램 등록")
        act.triggered.connect(self._toggle_startup)

        menu.addSeparator()
        menu.addAction("종료", QApplication.instance().quit)
        menu.exec_(event.globalPos())

    # ── 유틸 ─────────────────────────────────────────────────────────────────

    def _clock_out_dt(self) -> datetime | None:
        try:
            base = datetime.strptime(self._clock_in, "%H:%M")
            today = datetime.now().replace(second=0, microsecond=0)
            return today.replace(hour=base.hour, minute=base.minute) + timedelta(hours=9)
        except Exception:
            return None

    def _can_leave(self) -> bool:
        dt = self._clock_out_dt()
        return dt is not None and datetime.now() >= dt

    def _remaining(self) -> str:
        dt = self._clock_out_dt()
        if dt is None:
            return "?:??"
        delta = datetime.now() - dt          # 양수 = 초과, 음수 = 남음
        total_min = int(delta.total_seconds() // 60)

        if total_min < 0:                    # 아직 퇴근 전 → -표시
            h, m = divmod(-total_min, 60)
            if h > 0:
                return f"-{h}h {m:02d}m"
            return f"-{m}m"
        else:                                # 퇴근 시간 초과 → +표시
            total_min = min(total_min, 24 * 60)   # 최대 24시간 캡
            h, m = divmod(total_min, 60)
            return f"+{h}h {m:02d}m"

    def _open_login(self):
        dlg = LoginDialog(self)
        if dlg.exec_():
            creds = credentials.load()
            if creds:
                self._fetch(*creds)

    def _toggle_startup(self):
        if startup.is_registered():
            startup.unregister()
        else:
            startup.register()

    def _save_position(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps({"x": self.x(), "y": self.y()}))

    def _restore_position(self):
        try:
            data = json.loads(CONFIG_FILE.read_text())
            screen = QApplication.primaryScreen().geometry()
            x = max(0, min(data["x"], screen.width() - W))
            y = max(0, min(data["y"], screen.height() - H))
            self.move(x, y)
        except Exception:
            # 기본 위치: 오른쪽 하단 (작업표시줄 위)
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.width() - W - 16, screen.height() - H - 16)
