import asyncio
from PyQt5.QtCore import QThread, pyqtSignal
from playwright.async_api import async_playwright

LOGIN_URL = "https://login.office.hiworks.com/axgate.com"
WORK_URL = "https://hr-work.office.hiworks.com/personal/index"

# JavaScript: 페이지에서 오늘 출근 시간(HH:MM)을 찾는 3단계 전략
_JS_FIND_CLOCK_IN = """
() => {
    const timeRe = /^([01]\\d|2[0-3]):[0-5]\\d$/;
    const inlineTimeRe = /([01]\\d|2[0-3]):[0-5]\\d/;

    // 전략 1: 순수 HH:MM 텍스트를 가진 leaf 요소 중,
    //          조상 6단계 내에 '출근' 텍스트가 있는 것을 반환
    for (const el of document.querySelectorAll('*')) {
        if (el.children.length !== 0) continue;
        const t = el.textContent.trim();
        if (!timeRe.test(t)) continue;
        let node = el.parentElement;
        for (let i = 0; i < 6; i++) {
            if (!node) break;
            if (node.textContent.includes('출근')) return t;
            node = node.parentElement;
        }
    }

    // 전략 2: TreeWalker로 '출근' 텍스트 노드를 찾고,
    //          같은 행(tr / row / item / li) 안에서 HH:MM 탐색
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
        if (!n.textContent.includes('출근')) continue;
        const row = n.parentElement &&
            n.parentElement.closest('tr,[class*="row"],[class*="item"],li,[class*="list"]');
        if (!row) continue;
        for (const el of row.querySelectorAll('*')) {
            if (el.children.length === 0 && timeRe.test(el.textContent.trim()))
                return el.textContent.trim();
        }
        // row 전체 텍스트에서 인라인 패턴 탐색
        const m = row.textContent.match(inlineTimeRe);
        if (m) return m[0];
    }

    // 전략 3: body.innerText를 줄 단위로 스캔 —
    //          '출근' 포함 줄 이후 8줄 안에서 첫 번째 HH:MM 반환
    const lines = document.body.innerText.split('\\n')
        .map(l => l.trim()).filter(Boolean);
    for (let i = 0; i < lines.length; i++) {
        if (!lines[i].includes('출근')) continue;
        for (let j = i; j < Math.min(i + 8, lines.length); j++) {
            const m = lines[j].match(inlineTimeRe);
            if (m) return m[0];
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
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await self._login(page)
                return await self._get_clock_in(page)
            finally:
                await browser.close()

    async def _login(self, page):
        await page.goto(LOGIN_URL, timeout=30_000)
        await page.wait_for_load_state("networkidle", timeout=20_000)

        # 아이디 입력 필드 — 다양한 selector 순차 시도
        for sel in (
            'input[name="id"]',
            'input[name="username"]',
            'input[name="loginId"]',
            'input[placeholder*="아이디"]',
            'input[placeholder*="ID"]',
            'input[type="text"]:visible',
        ):
            try:
                await page.fill(sel, self.username, timeout=1_500)
                break
            except Exception:
                continue

        await page.fill('input[type="password"]', self.password, timeout=8_000)

        # 로그인 버튼 클릭
        for sel in (
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("로그인")',
            'button:has-text("Login")',
        ):
            try:
                await page.click(sel, timeout=1_500)
                break
            except Exception:
                continue

        await page.wait_for_load_state("networkidle", timeout=20_000)

        if "login" in page.url.lower():
            raise RuntimeError("로그인 실패: 아이디 또는 비밀번호를 확인하세요.")

    async def _get_clock_in(self, page) -> str:
        await page.goto(WORK_URL, timeout=30_000)
        await page.wait_for_load_state("networkidle", timeout=20_000)
        # SPA 렌더링 대기
        await page.wait_for_timeout(3_000)

        result = await page.evaluate(_JS_FIND_CLOCK_IN)
        if result:
            return result

        raise RuntimeError(
            "출근 시간을 찾을 수 없습니다.\n"
            "아직 출근 전이거나 페이지 구조가 변경되었을 수 있습니다."
        )
