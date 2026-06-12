# Gold Coin Billing System

# Branches

## main
- Original stable Version 1 of the Gold Coin Finance Billing System.

## v2
- Latest Version 2 with enhanced UI and UX.
- Improved invoice generation.
- PDF export enhancements.
- Backup & Restore functionality.
- Email integration.
- Performance optimizations.
- Bug fixes and new features.

## Windows Installer Setup

This project includes a professional Windows installer that creates a complete installation package for the Gold Coin Consultancy Billing System.

### Prerequisites

1. **Python 3.10+** - Download from [python.org](https://python.org/downloads/)
2. **NSIS (Nullsoft Scriptable Install System)** - Download from [nsis.sourceforge.io](https://nsis.sourceforge.io/)
   - Add NSIS to your system PATH during installation
3. **ImageMagick** (optional) - For icon conversion from PNG to ICO

### Building the Installer

1. Open Command Prompt as Administrator in the project root folder
2. Run the installer builder:

```bat
build_installer.bat
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Build the executable with PyInstaller
- Create installer graphics (placeholders)
- Build the Windows installer (.exe)

### Installing the Application

1. Run `GoldCoinBilling_Installer.exe` as Administrator
2. Follow the installation wizard
3. Choose installation directory (default: Program Files)
4. Select shortcut options (Desktop, Start Menu)
5. Complete installation

### Post-Installation

- **Location**: `C:\Program Files\Gold Coin Consultancy\Billing System\`
- **Data**: `%APPDATA%\GoldCoinBilling\` (preserved during uninstall)
- **Shortcuts**: Desktop and Start Menu
- **Uninstaller**: Add/Remove Programs

### Default Credentials

- **Username**: admin
- **Password**: admin123
- Change password after first login

### Development

To run without installer:

```bat
venv\Scripts\activate.bat
python main.py
```

### Legacy Admin Installation

For development/testing purposes, you can use the legacy batch script:

```bat
install_admin.bat
```

This creates a local build without installer.

### Files Overview

- `build_installer.bat` - Builds the complete Windows installer
- `GoldCoinBilling_Installer.nsi` - NSIS installer script
- `install_admin.bat` - Legacy development build script
- `GoldCoinBilling.spec` - PyInstaller specification
- `requirements.txt` - Python dependencies
- `assets/` - Installer graphics and icons

### Troubleshooting

- **NSIS not found**: Ensure NSIS is installed and in PATH
- **Python errors**: Verify Python 3.10+ is installed
- **Permission errors**: Run Command Prompt as Administrator
- **Icon issues**: Install ImageMagick for PNG→ICO conversion
