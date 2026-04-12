@echo off
setlocal enabledelayedexpansion

echo.
echo ================================================
echo   Gold Coin Consultancy — Admin Installer
echo ================================================
echo.

:: Verify Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not available on PATH.
    echo Install Python 3.10+ from https://www.python.org/downloads/ and try again.
    pause
    exit /b 1
)

:: Verify Python version
python -c "import sys; sys.exit(0) if sys.version_info >= (3,10) else sys.exit(1)" 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python 3.10 or newer is required.
    pause
    exit /b 1
)

:: Create virtual environment if missing
if not exist venv (
    echo [1/4] Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate virtual environment
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [2/4] Upgrading pip and installing dependencies...
python -m pip install --upgrade pip setuptools wheel
if %errorlevel% neq 0 (
    echo ERROR: Failed to upgrade pip.
    pause
    exit /b 1
)
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

echo [3/4] Building executable with PyInstaller...
python -m PyInstaller GoldCoinBilling.spec --noconfirm
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller build failed. Check output above.
    pause
    exit /b 1
)

echo [4/4] Admin install complete.
echo Output path: dist\GoldCoinBilling\GoldCoinBilling.exe
echo Default admin credentials: username=admin, password=admin123
echo First login will automatically hash the password; change it after login.
echo.
echo To run the installed app, execute:
echo     dist\GoldCoinBilling\GoldCoinBilling.exe
echo.
pause
endlocal
