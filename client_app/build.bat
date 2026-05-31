@echo off
echo ==============================================
echo  SafeCleaner Pro - Build ^& Obfuscate Script
echo ==============================================

echo 1. Generating obfuscated package and building with PyInstaller...
pyarmor gen --pack onefile main.py

echo 2. Renaming binary to SafeCleanerPro.exe...
move /y dist\main.exe dist\SafeCleanerPro.exe

echo ==============================================
echo Build Complete!
echo You can find the final highly-encrypted EXE at:
echo D:\Coding\app\SafeCleanerPro\client_app\dist\SafeCleanerPro.exe
echo ==============================================
pause
