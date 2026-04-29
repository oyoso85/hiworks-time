import sys
import winreg

_REG_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "HiworksTimeWidget"


def _exe_command() -> str:
    if getattr(sys, "frozen", False):
        # PyInstaller 빌드된 exe
        return f'"{sys.executable}"'
    # 개발 환경: pythonw 로 콘솔 없이 실행
    script = sys.argv[0]
    py = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{py}" "{script}"'


def register() -> None:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _exe_command())


def unregister() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _APP_NAME)
    except OSError:
        pass


def is_registered() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as key:
            winreg.QueryValueEx(key, _APP_NAME)
        return True
    except OSError:
        return False
