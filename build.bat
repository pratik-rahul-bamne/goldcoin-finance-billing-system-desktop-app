@echo off
echo.
echo ================================================
echo   Gold Coin Consultancy - Desktop App Builder
echo ================================================
echo.

:: Install dependencies
echo [1/3] Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Make sure Python is installed.
    pause
    exit /b 1
)

echo.
echo [2/3] Building executable with PyInstaller...
pyinstaller GoldCoinBilling.spec --noconfirm

if %errorlevel% neq 0 (
    echo ERROR: PyInstaller build failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo [3/3] Build complete!
echo.
echo ================================================
echo   Output: dist\GoldCoinBilling.exe
echo   The .exe does NOT require Python to be installed.
echo ================================================
echo.
pause
