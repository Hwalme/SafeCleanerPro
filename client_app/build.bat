@echo off
setlocal
cd /d "%~dp0.."
set "RELEASE_PYTHON=%~dp0..\.venv-release\Scripts\python.exe"
if not exist "%RELEASE_PYTHON%" set "RELEASE_PYTHON=python"
rem A failed protection step fails the release. No unprotected fallback.
"%RELEASE_PYTHON%" tools\build_release.py build
exit /b %errorlevel%
