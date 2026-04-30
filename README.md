# hiworks-time

HiWorks 출근 시간과 퇴근까지 남은 시간을 바탕화면에 표시하는 Windows 위젯.

![위젯 예시](docs/preview.png)

---

## 기능

- 출근 시간 표시 (HiWorks 자동 조회)
- 9시간 기준 퇴근까지 남은 시간 실시간 카운트다운
- 퇴근 가능 전: 하늘색 `-Xh XXm`, 퇴근 가능 후: 초록색 `+Xh XXm`
- 1시간마다 자동 재조회, 1분마다 화면 갱신
- 시작프로그램 등록/해제 (우클릭 메뉴)
- 투명 배경, 항상 위, 드래그로 위치 이동

---

## 설치 및 실행

별도 설치 없이 `hiworks-time.exe` 를 실행하면 됩니다.

처음 실행 시 로그인 설정 버튼이 표시됩니다. 클릭 후 HiWorks 계정을 입력하면 이후 자동으로 조회합니다. 자격증명은 Windows 자격증명 관리자에 저장됩니다.

---

## 조작

| 동작 | 기능 |
|------|------|
| 왼쪽 드래그 | 위젯 이동 |
| 더블클릭 | 즉시 새로고침 |
| 우클릭 | 메뉴 (새로고침 / 로그인 설정 / 시작프로그램 / 종료) |

---

## 개발 환경 설정

```bash
pip install -r requirements.txt
playwright install msedge
```

```bash
# 실행
python src/main.py

# 스크래핑 디버그 (브라우저 열림, 단계별 소요 시간 출력)
python debug_scraper.py
```

---

## 빌드

`build.bat` 더블클릭 → `hiworks-time.exe` 생성

내부적으로 PyInstaller `--onefile`로 빌드하며 Edge/Chrome 브라우저를 시스템에서 직접 사용합니다 (playwright 브라우저 별도 설치 불필요).

---

## 기술 스택

| 항목 | 내용 |
|------|------|
| UI | PyQt5 (프레임리스 투명 위젯) |
| 스크래핑 | Playwright (시스템 Edge/Chrome 사용) |
| 자격증명 | Windows Credential Manager (`keyring`) |
| 시작프로그램 | `winreg` HKCU Run 키 |
| 배포 | PyInstaller `--onefile` |
