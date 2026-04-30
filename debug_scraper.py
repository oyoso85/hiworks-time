"""
디버그 스크립트 — 실행 후 debug/ 폴더에 스크린샷과 페이지 텍스트 저장
사용: python debug_scraper.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, "src")

LOGIN_URL = "https://login.office.hiworks.com/axgate.com"
WORK_URL = "https://hr-work.office.hiworks.com/personal/index"
OUT = Path("debug")
OUT.mkdir(exist_ok=True)


async def run(username: str, password: str):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        # 시스템 Edge 우선
        browser = None
        for channel in ("msedge", "chrome"):
            try:
                browser = await p.chromium.launch(channel=channel, headless=False)  # headless=False 로 실제 창 확인
                print(f"[브라우저] {channel} 사용")
                break
            except Exception:
                continue
        if not browser:
            browser = await p.chromium.launch(headless=False)
            print("[브라우저] playwright 내장 chromium 사용")

        page = await browser.new_page()

        # ── 1. 로그인 페이지 ──────────────────────────────
        print(f"\n[1] 로그인 페이지 접속: {LOGIN_URL}")
        await page.goto(LOGIN_URL, timeout=30_000)
        await page.wait_for_load_state("networkidle", timeout=20_000)
        await page.screenshot(path=str(OUT / "01_login_page.png"))
        print(f"    URL: {page.url}")
        print(f"    스크린샷: debug/01_login_page.png")

        # ── 2. 아이디 입력 ────────────────────────────────
        # 페이지가 @axgate.com 을 자동으로 붙여주므로 도메인 제거
        login_id = username.split("@")[0]
        print(f"    입력할 아이디: {login_id}  (원본: {username})")

        filled = False
        for sel in (
            'input[name="id"]', 'input[name="username"]', 'input[name="loginId"]',
            'input[placeholder*="아이디"]', 'input[placeholder*="ID"]',
            'input[type="text"]:visible',
        ):
            try:
                await page.fill(sel, login_id, timeout=1_500)
                print(f"[2] 아이디 입력 성공 (selector: {sel})")
                filled = True
                break
            except Exception:
                continue
        if not filled:
            print("[2] 아이디 입력 실패 — 페이지의 input 목록:")
            inputs = await page.evaluate("""
                () => [...document.querySelectorAll('input')].map(el => ({
                    type: el.type, name: el.name, placeholder: el.placeholder, id: el.id
                }))
            """)
            for inp in inputs:
                print(f"    {inp}")

        # ── 3. '다음' 버튼 클릭 ──────────────────────────
        for sel in ('button:has-text("다음")', 'button:has-text("Next")',
                    'button[type="submit"]', 'input[type="submit"]'):
            try:
                await page.click(sel, timeout=1_500)
                print(f"[3] 다음 버튼 클릭 (selector: {sel})")
                break
            except Exception:
                continue

        # 비밀번호 필드 대기
        print("[4] 비밀번호 필드 대기 중...")
        await page.wait_for_selector('input[type="password"]', timeout=10_000)
        await page.screenshot(path=str(OUT / "01b_after_next.png"))
        print("    스크린샷: debug/01b_after_next.png")

        pw_field = page.locator('input[type="password"]')
        await pw_field.click()
        await pw_field.type(password, delay=50)  # 실제 키 입력으로 React 이벤트 트리거
        print("[5] 비밀번호 입력 완료 — Playwright locator로 버튼 클릭")
        await page.wait_for_timeout(300)

        login_btn = page.locator('button[type="submit"]').first
        await login_btn.wait_for(state="visible", timeout=5_000)
        await login_btn.click()
        print("[6] 로그인 버튼 클릭 완료")

        # login URL에서 벗어날 때까지 대기
        try:
            await page.wait_for_url(
                lambda url: "login" not in url.lower(),
                timeout=15_000,
            )
            await page.screenshot(path=str(OUT / "02_after_login.png"))
            print(f"\n[5] 로그인 후 URL: {page.url}")
            print(f"    스크린샷: debug/02_after_login.png")
            print("\n✓ 로그인 성공")
        except Exception:
            await page.screenshot(path=str(OUT / "02_after_login.png"))
            print(f"\n[5] 로그인 후 URL: {page.url}")
            print("\n⚠ 로그인 실패: 아이디 또는 비밀번호를 확인하세요.")
            await browser.close()
            return

        # ── 4. 근무 페이지 접속 ───────────────────────────
        print(f"\n[6] 근무 페이지 접속: {WORK_URL}")
        await page.goto(WORK_URL, timeout=30_000)
        await page.wait_for_load_state("networkidle", timeout=20_000)
        await page.wait_for_timeout(3_000)
        await page.screenshot(path=str(OUT / "03_work_page.png"))
        print(f"    URL: {page.url}")
        print(f"    스크린샷: debug/03_work_page.png")

        # ── 5. 페이지 텍스트 저장 ─────────────────────────
        text = await page.evaluate("() => document.body.innerText")
        (OUT / "04_work_page_text.txt").write_text(text, encoding="utf-8")
        print(f"    전체 텍스트: debug/04_work_page_text.txt")

        # ── 6. '출근' 키워드 주변 텍스트 출력 ───────────────
        print("\n[7] '출근' 포함 줄:")
        for line in text.splitlines():
            if "출근" in line and line.strip():
                print(f"    >>> {line.strip()}")

        await browser.close()
        print("\n완료. debug/ 폴더를 확인하세요.")


if __name__ == "__main__":
    print("HiWorks 스크래퍼 디버그\n")

    # 1) 저장된 자격증명 우선 사용
    try:
        import keyring
        uid = keyring.get_password("HiworksTimeWidget", "__username__")
        if uid:
            pw = keyring.get_password("HiworksTimeWidget", uid)
            print(f"저장된 자격증명 사용: {uid}\n")
        else:
            uid = None
    except Exception:
        uid = None

    # 2) 없으면 직접 입력
    if not uid:
        import getpass
        uid = input("아이디: ").strip()
        pw = getpass.getpass("비밀번호: ")

    asyncio.run(run(uid, pw))
