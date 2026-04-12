@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ================================================
echo   Gold Coin Billing System - Installer Builder
echo ================================================
echo.

:: Check if NSIS is installed
makensis /VERSION >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: NSIS is not installed.
    echo.
    echo To create a professional Windows installer, please:
    echo 1. Download NSIS from: https://nsis.sourceforge.io/
    echo 2. Install NSIS and add it to your PATH
    echo 3. Re-run this script
    echo.
    echo Continuing with basic executable build only...
) else (
    goto :installer_build
)

:installer_build
:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not available on PATH.
    echo Install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check Python version
python -c "import sys; sys.exit(0) if sys.version_info >= (3,10) else sys.exit(1)" 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python 3.10 or newer is required.
    pause
    exit /b 1
)

:: Create virtual environment if missing
if not exist venv (
    echo [1/5] Creating virtual environment...
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

echo [2/5] Upgrading pip and installing dependencies...
python -m pip install --upgrade pip setuptools wheel
if %errorlevel% neq 0 (
    echo ERROR: Failed to upgrade pip.
    pause
    exit /b 1
)
python -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

echo [3/5] Building executable with PyInstaller...
python -m PyInstaller "%~dp0GoldCoinBilling.spec" --noconfirm
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller build failed. Check output above.
    pause
    exit /b 1
)

echo [4/5] Creating installer graphics...
if not exist assets mkdir assets
call "%~dp0create_icons.bat"

echo [5/5] Building Windows installer...
makensis /VERSION >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: NSIS not found. Skipping installer creation.
    echo The executable GoldCoinBilling.exe has been created successfully in the dist folder.
    echo.
    echo To create a professional installer:
    echo 1. Download NSIS from: https://nsis.sourceforge.io/
    echo 2. Install NSIS and add it to your PATH
    echo 3. Re-run this script
    goto :build_complete
)

makensis "%~dp0GoldCoinBilling_Installer.nsi"
if %errorlevel% neq 0 (
    echo ERROR: NSIS installer build failed. Check output above.
    pause
    exit /b 1
)

:build_complete
echo.
echo ================================================
echo   Build Complete!
echo ================================================
echo.
echo Your Gold Coin Billing System executable is ready:
echo   dist\GoldCoinBilling.exe
echo.
echo Installer created: GoldCoinBilling_Installer.exe
echo.
echo To install the application:
echo 1. Run GoldCoinBilling_Installer.exe as Administrator
echo 2. Follow the installation wizard
echo 3. Launch from Start Menu or Desktop shortcut
echo.
echo Default admin credentials:
echo Username: admin
echo Password: admin123
echo (Change password after first login)
echo.
pause
goto :eof

:: Basic build path (when NSIS not available)
:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not available on PATH.
    echo Install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check Python version
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
python -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

echo [3/4] Building executable with PyInstaller...
python -m PyInstaller "%~dp0GoldCoinBilling.spec" --noconfirm
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller build failed. Check output above.
    pause
    exit /b 1
)

echo [4/4] Basic build complete.
echo.
echo ================================================
echo   Basic Build Complete!
echo ================================================
echo.
echo Executable created: dist\GoldCoinBilling\GoldCoinBilling.exe
echo.
echo To install manually:
echo 1. Copy dist\GoldCoinBilling folder to desired location
echo 2. Create desktop shortcut to GoldCoinBilling.exe
echo 3. Run the application
echo.
echo For professional installer, install NSIS and re-run this script.
echo.
pause