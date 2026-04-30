import asyncio
from PyQt5.QtCore import QThread, pyqtSignal
from playwright.async_api import async_playwright

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


STEPS = [
    "브라우저 시작",   # 1/5
    "로그인 페이지",   # 2/5
    "로그인 중",       # 3/5
    "근무 페이지",     # 4/5
    "시간 파싱",       # 5/5
]
TOTAL = len(STEPS)


class ScraperThread(QThread):
    success  = pyqtSignal(str)       # 출근 시간 'HH:MM'
    failure  = pyqtSignal(str)       # 에러 메시지
    progress = pyqtSignal(int, str)  # (현재 단계 1~5, 단계명)

    def __init__(self, username: str, password: str, domain: str, parent=None):
        super().__init__(parent)
        self.username = username
        self.password = password
        self.login_url = f"https://login.office.hiworks.com/{domain}"

    def _step(self, n: int):
        self.progress.emit(n, STEPS[n - 1])

    def run(self):
        try:
            result = asyncio.run(self._scrape())
            self.success.emit(result)
        except Exception as e:
            self.failure.emit(str(e))

    async def _scrape(self) -> str:
        self._step(1)
        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            page = await browser.new_page()
            try:
                await self._login(page)
                return await self._get_clock_in(page)
            finally:
                await browser.close()

    async def _launch_browser(self, p):
        # Windows 10/11에 기본 설치된 Edge 우선 사용 → Chrome → 내장 Chromium
        for channel in ("msedge", "chrome"):
            try:
                return await p.chromium.launch(channel=channel, headless=True)
            except Exception:
                continue
        # 개발 환경 fallback: playwright install chromium 이 된 경우만 동작
        return await p.chromium.launch(headless=True)

    async def _login(self, page):
        self._step(2)

        # domcontentloaded: HTML 파싱 완료 시점에 리턴 (이미지/폰트/광고 스크립트 무시).
        # 기본값 "load"는 모든 리소스가 끝날 때까지 기다려 5초 이상 낭비될 수 있음.
        # 아래 wait_for_selector가 ID 필드 렌더링을 보장하므로 여기선 빠르게 넘어감.
        await page.goto(self.login_url, wait_until="domcontentloaded", timeout=30_000)
        # 다른 리소스 로딩 완료 여부와 무관하게 1초 후 바로 입력 시작
        await page.wait_for_timeout(1_000)

        # HiWorks 로그인 페이지는 아이디 입력란에 '@example.com'을 자동으로 붙여줌.
        # 전체 이메일을 입력하면 'example@example.com@example.com'이 되므로 @ 앞부분만 사용.
        login_id = self.username.split("@")[0]

        # ── 1단계: 아이디 입력 ─────────────────────────────────────────────────
        # 후보를 CSS ','로 묶어 한 번에 검색 — 순차 타임아웃(1.5s × N) 낭비 없음.
        # 실제 확인된 placeholder: '로그인 ID'
        # 페이지 로딩이 늦을 경우를 대비해 최대 3회 재시도 (1초 간격)
        id_selector = (
            'input[placeholder*="로그인 ID"], input[placeholder*="ID"], '
            'input[placeholder*="아이디"], input[name="id"], '
            'input[name="username"], input[name="loginId"]'
        )
        for attempt in range(3):
            try:
                await page.locator(id_selector).first.fill(login_id, timeout=1_000)
                break
            except Exception:
                if attempt == 2:
                    raise
                await page.wait_for_timeout(1_000)

        # ── '다음' 버튼 클릭 ───────────────────────────────────────────────────
        # HiWorks 로그인은 2단계 구조: 아이디 입력 → '다음' → 비밀번호 입력.
        # '다음' 클릭 전까지는 비밀번호 필드가 DOM에 존재하지 않음.
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

        # '다음' 클릭 후 React가 비밀번호 필드를 DOM에 삽입할 때까지 대기.
        # 이 전환은 페이지 이동 없이 컴포넌트 교체로 이루어지므로
        # wait_for_url이 아닌 wait_for_selector로 감지함.
        await page.wait_for_selector('input[type="password"]', timeout=10_000)

        # ── 2단계: 비밀번호 입력 ──────────────────────────────────────────────
        pw_field = page.locator('input[type="password"]')
        await pw_field.click()  # 포커스 이동 (React onFocus 이벤트 트리거)

        # page.fill()은 값을 한 번에 주입해 onChange가 한 번만 발생.
        # React 폼은 각 키 입력마다 onChange를 누적해 유효성 검사를 하므로
        # type(delay=50)으로 실제 타이핑처럼 한 글자씩 입력해야 로그인 버튼이 활성화됨.
        await pw_field.type(self.password, delay=50)

        # 마지막 키 입력 후 React 상태 업데이트(디바운스)가 완료될 시간을 줌.
        # 이게 없으면 버튼이 아직 비활성(disabled) 상태일 수 있음.
        await page.wait_for_timeout(300)

        self._step(3)

        # page.click()은 단순 JS click()이라 React의 합성 이벤트를 우회할 수 있음.
        # locator().click()은 마우스 이동 → mousedown → mouseup → click 전체를 시뮬레이션해
        # React onClick 핸들러가 정상적으로 발화됨.
        login_btn = page.locator('button[type="submit"]').first
        await login_btn.wait_for(state="visible", timeout=5_000)
        await login_btn.click()

        # 로그인 성공 시 HiWorks가 다른 도메인(hr-work.office.hiworks.com 등)으로 리다이렉트함.
        # URL에 'login'이 사라질 때까지 기다려 성공 여부를 판단.
        # 타임아웃 내에 리다이렉트가 없으면 아이디/비밀번호 오류로 간주.
        try:
            await page.wait_for_url(
                lambda url: "login" not in url.lower(),
                timeout=15_000,
            )
        except Exception:
            raise RuntimeError("로그인 실패: 아이디 또는 비밀번호를 확인하세요.")

    async def _get_clock_in(self, page) -> str:
        self._step(4)
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

        self._step(5)
        result = await page.evaluate(_JS_FIND_CLOCK_IN)
        if result:
            return result

        raise RuntimeError(
            "출근 시간을 찾을 수 없습니다.\n"
            "아직 출근 전이거나 페이지 구조가 변경되었을 수 있습니다."
        )
