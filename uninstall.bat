@echo off
setlocal

echo.
echo ================================================
echo   Gold Coin Billing - Uninstall
echo ================================================
echo.

set "APP_NAME=GoldCoinBilling"
set "BIN_DIR=%LOCALAPPDATA%\GoldCoinBilling\bin"
set "DATA_DIR=%LOCALAPPDATA%\GoldCoinBilling"

echo [1/2] Removing installed program...
if exist "%BIN_DIR%" (
  rmdir /s /q "%BIN_DIR%"
  echo Removed: "%BIN_DIR%"
) else (
  echo Program folder not found (skipping): "%BIN_DIR%"
)

echo.
echo [2/2] Removing shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desktop=[Environment]::GetFolderPath('Desktop');" ^
  "$start=[Environment]::GetFolderPath('ApplicationData');" ^
  "$startPrograms=Join-Path $start 'Microsoft\Windows\Start Menu\Programs\GoldCoinBilling';" ^
  "$files=@( (Join-Path $desktop 'Gold Coin Billing System.lnk'), (Join-Path $startPrograms 'Gold Coin Billing System.lnk') );" ^
  "foreach($f in $files){ if(Test-Path $f){ Remove-Item $f -Force } }" ^
  "if(Test-Path $startPrograms){ Remove-Item $startPrograms -Force -ErrorAction SilentlyContinue }"

echo.
echo NOTE: Your database and backups are stored in:
echo   "%DATA_DIR%"
echo.

set /p "choice=Do you want to delete ALL saved data (database + backups/logs)? (Y/N): "
if /I "%choice%"=="Y" (
  rmdir /s /q "%DATA_DIR%"
  echo Deleted all saved data.
) else (
  echo Kept saved data.
)

echo.
echo Uninstall complete.
pause
exit /b 0

