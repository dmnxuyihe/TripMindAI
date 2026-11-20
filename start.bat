@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 日常启动：不创建表、不导入初始数据，只使用现有数据库。
set "TRIPMIND_INIT_DATABASE=0"
echo [数据库] 日常启动模式：跳过数据库初始化。

.venv\Scripts\python.exe run.py
pause
