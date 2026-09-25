@echo off
REM Sestavi Tracki.exe do dist\. Vyzaduje Python 3.11+ na Windows.
setlocal

where python >nul 2>nul
if errorlevel 1 (
  echo Python nenalezen v PATH. Nainstalujte Python 3.11 nebo novejsi.
  exit /b 1
)

if not exist .venv (
  echo === vytvarim virtualni prostredi ===
  python -m venv .venv || exit /b 1
)

call .venv\Scripts\activate.bat || exit /b 1

echo === instaluji zavislosti ===
python -m pip install --upgrade pip || exit /b 1
python -m pip install -r requirements-build.txt pytest || exit /b 1

python build\build.py %* || exit /b 1

echo.
echo Vysledek: dist\Tracki.exe
endlocal
