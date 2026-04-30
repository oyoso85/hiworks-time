"""
디버그 스크립트 — 각 단계 소요 시간을 콘솔에 출력
사용: python debug_scraper.py
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")

WORK_URL  = "https://hr-work.office.hiworks.com/personal/index"
OUT = Path("debug")
OUT.mkdir(exist_ok=True)

_t0 = None  # 전체 시작 시점


def _now() -> str:
    """전체 시작 기준 경과 시간 (초)."""
    return f"{time.time() - _t0:5.1f}s"


def tick(label: str):
    """단계 시작을 찍는 타이머."""
    return time.time(), label


def tock(start: float, label: str):
    """단계 종료 후 소요 시간 출력."""
    elapsed = time.time() - start
    print(f"  [{_now()}] ✓ {label}  ({elapsed:.2f}s)")


async def run(username: str, password: str, domain: str):
    global _t0
    _t0 = time.time()

    from playwright.async_api import async_playwright

    async with async_playwright() as p:

        # ── 브라우저 실행 ─────────────────────────────────
        t, label = tick("브라우저 실행")
        print(f"\n[{_now()}] 브라우저 실행 중...")
        browser = None
        for channel in ("msedge", "chrome"):
            try:
                browser = await p.chromium.launch(channel=channel, headless=False)
                print(f"  [{_now()}] {channel} 사용")
                break
            except Exception:
                continue
        if not browser:
            browser = await p.chromium.launch(headless=False)
            print(f"  [{_now()}] playwright 내장 chromium 사용")
        tock(t, label)

        page = await browser.new_page()
        login_url = f"https://login.office.hiworks.com/{domain}"

        # ── goto (load 이벤트까지 대기) ───────────────────
        t, label = tick("page.goto (wait_until=domcontentloaded)")
        print(f"\n[{_now()}] 로그인 페이지 접속: {login_url}")
        await page.goto(login_url, wait_until="domcontentloaded", timeout=30_000)
        tock(t, label)

        t, label = tick("wait_for_timeout(1000) — 1초 후 바로 입력")
        print(f"[{_now()}] 1초 대기...")
        await page.wait_for_timeout(1_000)
        tock(t, label)

        # ── 아이디 입력 ───────────────────────────────────
        login_id = username.split("@")[0]
        t, label = tick("아이디 입력")
        print(f"[{_now()}] 아이디 입력 시도: {login_id}")
        # 후보를 하나의 CSS selector로 합쳐 한 번에 검색 — 순차 타임아웃 낭비 없음
        id_selector = (
            'input[placeholder*="로그인 ID"], input[placeholder*="ID"], '
            'input[placeholder*="아이디"], input[name="id"], '
            'input[name="username"], input[name="loginId"]'
        )
        try:
            field = page.locator(id_selector).first
            await field.wait_for(state="visible", timeout=3_000)
            matched = await field.get_attribute("placeholder") or await field.get_attribute("name") or "?"
            await field.fill(login_id)
            print(f"  [{_now()}] ✓ 입력 성공 (placeholder/name: {matched})")
        except Exception as e:
            print(f"  [{_now()}] !! 입력 실패 ({e.__class__.__name__}) — 현재 페이지 input 목록:")
            inputs = await page.evaluate("""
                () => [...document.querySelectorAll('input')].map(el => ({
                    type: el.type, name: el.name, placeholder: el.placeholder,
                    id: el.id, visible: el.offsetParent !== null
                }))
            """)
            for inp in inputs:
                print(f"       {inp}")
        tock(t, label)

        # ── '다음' 버튼 클릭 ──────────────────────────────
        t, label = tick("'다음' 버튼 클릭")
        print(f"[{_now()}] '다음' 버튼 클릭...")
        for sel in ('button:has-text("다음")', 'button:has-text("Next")',
                    'button[type="submit"]', 'input[type="submit"]'):
            try:
                await page.click(sel, timeout=1_500)
                print(f"  [{_now()}] selector 성공: {sel}")
                break
            except Exception:
                continue
        tock(t, label)

        # ── 비밀번호 필드 렌더링 대기 ─────────────────────
        t, label = tick("wait_for_selector (비밀번호 필드)")
        print(f"[{_now()}] 비밀번호 필드 대기 중...")
        await page.wait_for_selector('input[type="password"]', timeout=10_000)
        await page.screenshot(path=str(OUT / "01_after_next.png"))
        tock(t, label)

        # ── 비밀번호 입력 (delay=50) ──────────────────────
        t, label = tick(f"비밀번호 type (delay=50, {len(password)}글자 → 예상 {len(password)*50}ms)")
        print(f"[{_now()}] 비밀번호 입력 중...")
        pw_field = page.locator('input[type="password"]')
        await pw_field.click()
        await pw_field.type(password, delay=50)
        tock(t, label)

        # ── 300ms 대기 ────────────────────────────────────
        t, label = tick("wait_for_timeout(300) — React 디바운스")
        print(f"[{_now()}] 300ms 대기...")
        await page.wait_for_timeout(300)
        tock(t, label)

        # ── 로그인 버튼 클릭 ──────────────────────────────
        t, label = tick("로그인 버튼 클릭")
        print(f"[{_now()}] 로그인 버튼 클릭...")
        login_btn = page.locator('button[type="submit"]').first
        await login_btn.wait_for(state="visible", timeout=5_000)
        await login_btn.click()
        tock(t, label)

        # ── 리다이렉트 대기 ───────────────────────────────
        t, label = tick("wait_for_url (로그인 완료 리다이렉트)")
        print(f"[{_now()}] 로그인 완료 대기 중...")
        try:
            await page.wait_for_url(
                lambda url: "login" not in url.lower(),
                timeout=15_000,
            )
            tock(t, label)
            await page.screenshot(path=str(OUT / "02_after_login.png"))
            print(f"  [{_now()}] URL: {page.url}")
            print(f"  [{_now()}] 스크린샷: debug/02_after_login.png")
        except Exception:
            print(f"  [{_now()}] ⚠ 로그인 실패: 아이디 또는 비밀번호를 확인하세요.")
            await page.screenshot(path=str(OUT / "02_after_login.png"))
            await browser.close()
            return

        # ── 근무 페이지 접속 ──────────────────────────────
        t, label = tick("근무 페이지 goto + networkidle")
        print(f"\n[{_now()}] 근무 페이지 접속: {WORK_URL}")
        await page.goto(WORK_URL, timeout=30_000)
        await page.wait_for_load_state("networkidle", timeout=20_000)
        tock(t, label)

        t, label = tick("wait_for_function (HH:MM출근 패턴)")
        print(f"[{_now()}] 출근 시간 렌더링 대기 중...")
        try:
            await page.wait_for_function(
                r"() => /[012]\d:[0-5]\d출근/.test(document.body.innerText)",
                timeout=10_000,
            )
            tock(t, label)
        except Exception:
            print(f"  [{_now()}] 패턴 미발견 (출근 전이거나 구조 변경)")

        await page.screenshot(path=str(OUT / "03_work_page.png"))

        # ── 출근 시간 파싱 ────────────────────────────────
        t, label = tick("JS evaluate (출근 시간 추출)")
        text = await page.evaluate("() => document.body.innerText")
        (OUT / "04_work_page_text.txt").write_text(text, encoding="utf-8")

        import re
        m = re.search(r"([01]\d|2[0-3]):[0-5]\d(?=출근)", text)
        result = m.group(0) if m else "없음"
        tock(t, label)
        print(f"  [{_now()}] 출근 시간: {result}")

        await browser.close()
        print(f"\n[{_now()}] 완료. 총 {time.time() - _t0:.1f}s")


if __name__ == "__main__":
    print("HiWorks 스크래퍼 디버그 (타이밍 측정)\n")

    try:
        import keyring
        uid = keyring.get_password("HiworksTimeWidget", "__username__")
        if uid:
            pw = keyring.get_password("HiworksTimeWidget", uid)
            domain = keyring.get_password("HiworksTimeWidget", "__domain__") or ""
            print(f"저장된 자격증명 사용: {uid} / {domain}\n")
        else:
            uid = None
    except Exception:
        uid = None

    if not uid:
        import getpass
        domain = input("회사 도메인 (예: mycompany.com): ").strip()
        uid = input("아이디: ").strip()
        pw = getpass.getpass("비밀번호: ")

    asyncio.run(run(uid, pw, domain))
