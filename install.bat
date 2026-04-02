@echo off
setlocal

echo.
echo ================================================
echo   Gold Coin Billing - Windows Installer
echo ================================================
echo.

set "APP_NAME=GoldCoinBilling"
set "SRC_EXE=%~dp0dist\GoldCoinBilling.exe"
set "BIN_DIR=%LOCALAPPDATA%\GoldCoinBilling\bin"
set "DATA_DIR=%LOCALAPPDATA%\GoldCoinBilling"
set "EXE_PATH=%BIN_DIR%\GoldCoinBilling.exe"

if not exist "%SRC_EXE%" (
  echo ERROR: Build output not found:
  echo   "%SRC_EXE%"
  echo.
  echo Run build.bat first.
  pause
  exit /b 1
)

echo [1/4] Creating folders...
mkdir "%BIN_DIR%" 2>nul
mkdir "%DATA_DIR%" 2>nul

echo [2/4] Copying EXE...
copy /Y "%SRC_EXE%" "%EXE_PATH%" >nul
if errorlevel 1 (
  echo ERROR: Failed to copy EXE.
  pause
  exit /b 1
)

echo [3/4] Creating shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$exe='%EXE_PATH%';" ^
  "$desktop=[Environment]::GetFolderPath('Desktop');" ^
  "$start=[Environment]::GetFolderPath('ApplicationData');" ^
  "$startPrograms=Join-Path $start 'Microsoft\Windows\Start Menu\Programs\GoldCoinBilling';" ^
  "New-Item -ItemType Directory -Force -Path $startPrograms | Out-Null;" ^
  "$shell=New-Object -ComObject WScript.Shell;" ^
  "$s1=Join-Path $desktop 'Gold Coin Billing System.lnk';" ^
  "$sc=$shell.CreateShortcut($s1); $sc.TargetPath=$exe; $sc.WorkingDirectory=Split-Path $exe; $sc.Save();" ^
  "$s2=Join-Path $startPrograms 'Gold Coin Billing System.lnk';" ^
  "$sc=$shell.CreateShortcut($s2); $sc.TargetPath=$exe; $sc.WorkingDirectory=Split-Path $exe; $sc.Save();"

echo [4/4] Installation complete.
echo Installed EXE:
echo   "%EXE_PATH%"
echo Data will be stored under:
echo   "%DATA_DIR%"
echo.

echo You can now start the app from Desktop or Start Menu.
pause
exit /b 0

