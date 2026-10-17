@echo off
rem Run from this script's own directory so the build works from any cwd.
cd /d "%~dp0"
echo ==============================================
echo  SafeCleaner Pro - Build and Obfuscate Script
echo ==============================================
echo.
echo NOTE: Pyarmor trial caps each script at about 42KB.
echo       Keep main.py / cleaner_core.py under that limit or the
echo       build fails with "out of license".
echo.

echo 1. Building Single EXE (Onefile) Mode...
pyarmor gen --pack onefile main.py
if errorlevel 1 goto :failed
move /y dist\main.exe dist\SafeCleanerPro.exe

echo 2. Building Portable Directory (Onedir) Mode...
if exist dist\SafeCleanerPro rmdir /s /q dist\SafeCleanerPro
pyarmor gen --pack onedir main.py
if errorlevel 1 goto :failed
if exist dist\main rename dist\main SafeCleanerPro
rename dist\SafeCleanerPro\main.exe SafeCleanerPro.exe

echo ==============================================
echo Build Complete!
echo Final binaries are available in dist/
echo ==============================================
pause
exit /b 0

:failed
echo ==============================================
echo BUILD FAILED - see the error above.
echo If it says "out of license", a script exceeds the
echo Pyarmor trial size limit (about 42KB each).
echo ==============================================
pause
exit /b 1
