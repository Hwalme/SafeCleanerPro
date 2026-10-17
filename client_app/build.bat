@echo off
rem Run from this script's own directory so the build works from any cwd.
cd /d "%~dp0"
echo ==============================================
echo  SafeCleaner Pro - Build and Obfuscate Script
echo ==============================================
echo.
echo NOTE: Pyarmor TRIAL caps each obfuscated script at
echo       ~42KB. main.py exceeded that long ago, so this
echo       script tries pyarmor first and automatically
echo       falls back to plain PyInstaller when it fails.
echo       (Register a pyarmor license to get obfuscated
echo       builds again: pyarmor register)
echo.

set BUILD_MODE=pyarmor
set BUILD_TIME=%date% %time%

echo 1. Building Single EXE (Onefile) Mode...
pyarmor gen --pack onefile main.py
if errorlevel 1 goto :fallback_onefile
move /y dist\main.exe dist\SafeCleanerPro.exe
goto :onedir

:fallback_onefile
set BUILD_MODE=pyinstaller
echo.
echo Pyarmor failed (trial size cap?) - falling back to plain PyInstaller...
pyinstaller --noconfirm --clean --onefile --windowed --name SafeCleanerPro --icon logo.ico --add-data "splash_logo.png;." --add-data "logo.ico;." --add-data "rules;rules" main.py
if errorlevel 1 goto :failed
goto :refresh_latest

:onedir
echo 2. Building Portable Directory (Onedir) Mode...
if exist dist\SafeCleanerPro rmdir /s /q dist\SafeCleanerPro
pyarmor gen --pack onedir main.py
if errorlevel 1 goto :onedir_fallback
if exist dist\main rename dist\main SafeCleanerPro
rename dist\SafeCleanerPro\main.exe SafeCleanerPro.exe
goto :refresh_latest

:onedir_fallback
echo Onedir pyarmor failed too - skipping onedir (onefile is enough).

:refresh_latest
echo 3. Refreshing latest\ (fixed path - shortcuts never break again)...
if exist latest rmdir latest 2>nul
if not exist latest mkdir latest
copy /y dist\SafeCleanerPro.exe latest\SafeCleanerPro.exe >nul
if errorlevel 1 goto :failed

> latest\build_info.txt echo mode   = %BUILD_MODE%
>> latest\build_info.txt echo built  = %BUILD_TIME%
>> latest\build_info.txt echo source = main.py (this folder)

echo ==============================================
echo Build Complete!  mode=%BUILD_MODE%
echo Latest exe: latest\SafeCleanerPro.exe
echo (Desktop shortcuts can always point at
echo  client_app\latest\SafeCleanerPro.exe)
echo ==============================================
pause
exit /b 0

:failed
echo ==============================================
echo BUILD FAILED - see the error above.
echo Pyarmor trial cap: "out of license" means the
echo script exceeds ~42KB (fallback handles it).
echo ==============================================
pause
exit /b 1
