import asyncio
from PyQt5.QtCore import QThread, pyqtSignal
from playwright.async_api import async_playwright

LOGIN_URL = "https://login.office.hiworks.com/axgate.com"
WORK_URL = "https://hr-work.office.hiworks.com/personal/index"

# JavaScript: 페이지에서 오늘 출근 시간(HH:MM)을 찾는 전략
_JS_FIND_CLOCK_IN = """
() => {
    const inlineTimeRe = /([01]\\d|2[0-3]):[0-5]\\d/;

    // 전략 1: 'HH:MM출근' 패턴 — 오늘 근무현황 섹션에 정확히 이 형식으로 존재
    const m1 = document.body.innerText.match(/([01]\\d|2[0-3]):[0-5]\\d(?=출근)/);
    if (m1) return m1[0];

    // 전략 2: '출근하기' 버튼 근처의 시간 (HH:MM:SS → HH:MM 변환)
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
        if (!n.textContent.includes('출근하기')) continue;
        const container = n.parentElement && n.parentElement.closest('div,section,article');
        if (!container) continue;
        const m = container.textContent.match(/([01]\\d|2[0-3]):[0-5]\\d/);
        if (m) return m[0];
    }

    // 전략 3: body.innerText 줄 단위 스캔 —
    //          '출근' 포함 줄에서 바로 HH:MM 추출 (앞에 붙은 경우 포함)
    const lines = document.body.innerText.split('\\n')
        .map(l => l.trim()).filter(Boolean);
    for (let i = 0; i < lines.length; i++) {
        if (!lines[i].includes('출근')) continue;
        // 같은 줄에 시간이 있는 경우 (예: "08:07출근")
        const mSame = lines[i].match(inlineTimeRe);
        if (mSame) return mSame[0];
        // 다음 줄에 시간이 있는 경우
        for (let j = i + 1; j < Math.min(i + 4, lines.length); j++) {
            const mNext = lines[j].match(/^([01]\\d|2[0-3]):[0-5]\\d$/);
            if (mNext) return mNext[0];
        }
    }

    return null;
}
"""


class ScraperThread(QThread):
    success = pyqtSignal(str)   # 출근 시간 'HH:MM'
    failure = pyqtSignal(str)   # 에러 메시지

    def __init__(self, username: str, password: str, parent=None):
        super().__init__(parent)
        self.username = username
        self.password = password

    def run(self):
        try:
            result = asyncio.run(self._scrape())
            self.success.emit(result)
        except Exception as e:
            self.failure.emit(str(e))

    async def _scrape(self) -> str:
        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            page = await browser.new_page()
            try:
                await self._login(page)
                return await self._get_clock_in(page)
            finally:
                await browser.close()

    @staticmethod
    async def _launch_browser(p):
        # Windows 10/11에 기본 설치된 Edge 우선 사용 → Chrome → 내장 Chromium
        for channel in ("msedge", "chrome"):
            try:
                return await p.chromium.launch(channel=channel, headless=True)
            except Exception:
                continue
        # 개발 환경 fallback: playwright install chromium 이 된 경우만 동작
        return await p.chromium.launch(headless=True)

    async def _login(self, page):
        await page.goto(LOGIN_URL, timeout=30_000)
        # networkidle 대신 아이디 입력 필드가 보이는 즉시 진행
        await page.wait_for_selector('input[placeholder*="ID"]', timeout=10_000)

        # 페이지가 @axgate.com 을 자동으로 붙여주므로 도메인 부분 제거
        login_id = self.username.split("@")[0]

        # ── 1단계: 아이디 입력 후 '다음' 클릭 ─────────────
        for sel in (
            'input[name="id"]',
            'input[name="username"]',
            'input[name="loginId"]',
            'input[placeholder*="아이디"]',
            'input[placeholder*="ID"]',
            'input[type="text"]:visible',
        ):
            try:
                await page.fill(sel, login_id, timeout=1_500)
                break
            except Exception:
                continue

        for sel in (
            'button:has-text("다음")',
            'button:has-text("Next")',
            'button[type="submit"]',
            'input[type="submit"]',
        ):
            try:
                await page.click(sel, timeout=1_500)
                break
            except Exception:
                continue

        # 비밀번호 필드가 나타날 때까지 대기
        await page.wait_for_selector('input[type="password"]', timeout=10_000)

        # ── 2단계: 비밀번호 실제 키입력 후 버튼 클릭 ──────
        pw_field = page.locator('input[type="password"]')
        await pw_field.click()
        await pw_field.type(self.password, delay=50)  # 실제 키 입력으로 React 이벤트 트리거
        await page.wait_for_timeout(300)

        # Playwright locator로 버튼 클릭 (마우스 이벤트 전체 시뮬레이션)
        login_btn = page.locator('button[type="submit"]').first
        await login_btn.wait_for(state="visible", timeout=5_000)
        await login_btn.click()

        # 로그인 후 login URL에서 벗어날 때까지 대기
        try:
            await page.wait_for_url(
                lambda url: "login" not in url.lower(),
                timeout=15_000,
            )
        except Exception:
            raise RuntimeError("로그인 실패: 아이디 또는 비밀번호를 확인하세요.")

    async def _get_clock_in(self, page) -> str:
        await page.goto(WORK_URL, timeout=30_000)
        await page.wait_for_load_state("networkidle", timeout=20_000)
        # '오늘 근무현황' 섹션이 렌더링될 때까지 대기 (최대 10초)
        try:
            await page.wait_for_function(
                "() => /[012]\\d:[0-5]\\d출근/.test(document.body.innerText)",
                timeout=10_000,
            )
        except Exception:
            pass  # 출근 전일 수 있으므로 그대로 파싱 시도

        result = await page.evaluate(_JS_FIND_CLOCK_IN)
        if result:
            return result

        raise RuntimeError(
            "출근 시간을 찾을 수 없습니다.\n"
            "아직 출근 전이거나 페이지 구조가 변경되었을 수 있습니다."
        )
