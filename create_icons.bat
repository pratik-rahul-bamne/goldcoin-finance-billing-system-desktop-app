@echo off
REM Icon conversion script for installer assets
REM Requires ImageMagick (magick command)

if not exist "assets\icon.png" (
    echo ERROR: assets\icon.png not found. Please add your application icon.
    echo Creating placeholder...
    echo. > assets\icon_placeholder.txt
    goto :eof
)

echo Converting PNG to ICO...
if exist "magick" (
    magick "assets\icon.png" -define icon:auto-resize=256,128,64,48,32,16 "assets\icon.ico"
    if %errorlevel% equ 0 (
        echo Icon conversion successful.
    ) else (
        echo ERROR: Icon conversion failed. Using placeholder.
        copy "assets\icon.png" "assets\icon.ico" >nul 2>&1
    )
) else (
    echo ImageMagick not found. Using PNG as ICO placeholder.
    copy "assets\icon.png" "assets\icon.ico" >nul 2>&1
)

REM Create basic BMP files for installer (placeholders)
echo Creating installer graphics...
if not exist "assets\header.bmp" (
    REM Create a simple colored BMP (you should replace with actual graphics)
    echo. > assets\header.bmp
)

if not exist "assets\wizard.bmp" (
    echo. > assets\wizard.bmp
)

echo Icon setup complete.