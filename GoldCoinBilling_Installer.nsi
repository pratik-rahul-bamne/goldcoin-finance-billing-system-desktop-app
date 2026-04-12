; GoldCoinBilling.nsi - NSIS Installer Script
; This script creates a professional Windows installer for the Gold Coin Billing System

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

; General Configuration
Name "Gold Coin Consultancy Billing System"
OutFile "GoldCoinBilling_Installer.exe"
Unicode True
InstallDir "$PROGRAMFILES\Gold Coin Consultancy\Billing System"
InstallDirRegKey HKLM "Software\GoldCoinBilling" "Install_Dir"
RequestExecutionLevel admin

; Modern UI Configuration
!define MUI_ABORTWARNING
!define MUI_ICON "assets\icon.ico"
!define MUI_UNICON "assets\icon.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "assets\header.bmp"
!define MUI_WELCOMEFINISHPAGE_BITMAP "assets\wizard.bmp"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Languages
!insertmacro MUI_LANGUAGE "English"

; Version Information
VIProductVersion "1.0.0.0"
VIAddVersionKey "ProductName" "Gold Coin Consultancy Billing System"
VIAddVersionKey "CompanyName" "Gold Coin Consultancy"
VIAddVersionKey "FileVersion" "1.0.0.0"
VIAddVersionKey "ProductVersion" "1.0.0.0"
VIAddVersionKey "FileDescription" "Desktop Billing & Ledger System"

; Installer Sections
Section "Main Application" SecApp
    SectionIn RO

    SetOutPath "$INSTDIR"

    ; Copy all application files
    DetailPrint "Installing application files..."
    File /r "dist\GoldCoinBilling\*.*"

    ; Create data directory
    CreateDirectory "$APPDATA\GoldCoinBilling"
    CreateDirectory "$APPDATA\GoldCoinBilling\backup"
    CreateDirectory "$APPDATA\GoldCoinBilling\logs"

    ; Copy database schema if it doesn't exist
    IfFileExists "$APPDATA\GoldCoinBilling\goldcoin_billing.db" skip_db_copy
        DetailPrint "Setting up initial database..."
        File "database.sql"
        nsExec::ExecToLog '"$INSTDIR\GoldCoinBilling.exe" --init-db'
    skip_db_copy:

    ; Store installation folder
    WriteRegStr HKLM "Software\GoldCoinBilling" "Install_Dir" "$INSTDIR"

    ; Create uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoldCoinBilling" "DisplayName" "Gold Coin Consultancy Billing System"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoldCoinBilling" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoldCoinBilling" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoldCoinBilling" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoldCoinBilling" "DisplayIcon" "$INSTDIR\GoldCoinBilling.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoldCoinBilling" "Publisher" "Gold Coin Consultancy"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoldCoinBilling" "DisplayVersion" "1.0.0"
    WriteRegDWord HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoldCoinBilling" "NoModify" 1
    WriteRegDWord HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoldCoinBilling" "NoRepair" 1
    WriteRegDWord HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoldCoinBilling" "EstimatedSize" 50000

SectionEnd

; Shortcuts Section
Section "Desktop Shortcut" SecDesktop
    CreateShortCut "$DESKTOP\Gold Coin Billing.lnk" "$INSTDIR\GoldCoinBilling.exe" "" "$INSTDIR\GoldCoinBilling.exe" 0
SectionEnd

Section "Start Menu Shortcut" SecStartMenu
    CreateDirectory "$SMPROGRAMS\Gold Coin Consultancy"
    CreateShortCut "$SMPROGRAMS\Gold Coin Consultancy\Gold Coin Billing.lnk" "$INSTDIR\GoldCoinBilling.exe" "" "$INSTDIR\GoldCoinBilling.exe" 0
    CreateShortCut "$SMPROGRAMS\Gold Coin Consultancy\Uninstall.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0
SectionEnd

; Uninstaller Section
Section "Uninstall"

    ; Remove files
    Delete "$INSTDIR\Uninstall.exe"
    RMDir /r "$INSTDIR"

    ; Remove shortcuts
    Delete "$DESKTOP\Gold Coin Billing.lnk"
    RMDir /r "$SMPROGRAMS\Gold Coin Consultancy"

    ; Remove registry keys
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoldCoinBilling"
    DeleteRegKey HKLM "Software\GoldCoinBilling"

    ; Note: User data in %APPDATA%\GoldCoinBilling is preserved for uninstall

SectionEnd

; Functions
Function .onInit
    ; Check if already installed
    ReadRegStr $R0 HKLM "Software\GoldCoinBilling" "Install_Dir"
    ${If} $R0 != ""
        MessageBox MB_YESNO "Gold Coin Billing System is already installed. Do you want to reinstall?" IDYES continue_install
        Abort
        continue_install:
    ${EndIf}

    ; Check Windows version (Windows 10+)
    ${IfNot} ${AtLeastWin10}
        MessageBox MB_OK "This application requires Windows 10 or later."
        Abort
    ${EndIf}
FunctionEnd

Function un.onInit
    MessageBox MB_YESNO "This will uninstall Gold Coin Billing System. Your data files will be preserved. Continue?" IDYES continue_uninstall
    Abort
    continue_uninstall:
FunctionEnd