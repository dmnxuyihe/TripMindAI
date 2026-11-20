@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 初始化启动：创建缺失的数据表，并在景点表为空时导入初始数据。
rem 初始化是幂等操作，不会删除、清空或覆盖已有数据。
set "TRIPMIND_INIT_DATABASE=1"
echo [数据库] 初始化启动模式：创建缺失表并按需导入初始数据。

if not exist .env (
 echo [错误] 缺少 .env，请先复制 .env.example 并完成配置。
 pause
 exit /b 1
)
if not exist .venv\Scripts\python.exe (
 python -m venv .venv
 if errorlevel 1 (echo [错误] Python 虚拟环境创建失败 & pause & exit /b 1)
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (echo [错误] 依赖安装失败 & pause & exit /b 1)
.venv\Scripts\python.exe run.py
pause
