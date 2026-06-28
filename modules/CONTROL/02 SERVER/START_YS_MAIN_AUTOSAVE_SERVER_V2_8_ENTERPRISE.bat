@echo off
chcp 65001 >nul
pushd "%~dp0"
if errorlevel 1 goto ERR_PATH

python -X utf8 "%~dp0ysmts_autosave_server_v2_8_enterprise.py"
if errorlevel 1 (
    "C:\Users\mycom\AppData\Local\Programs\Python\Python314\python.exe" -X utf8 "%~dp0ysmts_autosave_server_v2_8_enterprise.py"
)

pause
exit /b

:ERR_PATH
echo PATH ERROR
pause