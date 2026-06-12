@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions
cd /d "%~dp0"
echo [debug] cwd=%CD%
echo [debug] 若整理失败，本窗口会保留，便于复制报错。
call "%~dp0run-filekind.bat"
echo.
echo [debug] run-filekind.bat finished with errorlevel %ERRORLEVEL%
cmd /k
