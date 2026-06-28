@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ----------------------------------------
echo YSM Parts Center R8 Storage Engine
echo Server folder: %CD%
echo URL: http://127.0.0.1:8788
echo ----------------------------------------
py ysm_parts_storage_engine_R8.py
pause
