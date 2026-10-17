@echo off
rem 目录自定位：切到本 bat 所在目录，移动/改名后无需修改。
cd /d "%~dp0"
start http://127.0.0.1:8910
python scripts\dedup_server.py
