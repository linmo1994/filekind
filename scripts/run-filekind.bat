@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set EXITCODE=0

if not exist "filekind.exe" (
  echo 未找到 filekind.exe。请复制完整的 dist\filekind 文件夹。
  set EXITCODE=1
  goto :pause_exit
)

if not exist "projects.yaml" (
  if exist "projects.example.yaml" (
    copy /y "projects.example.yaml" "projects.yaml" >nul
    echo 已从 projects.example.yaml 生成 projects.yaml。
  )
)

if not exist "待整理" mkdir "待整理"
if not exist "已整理" mkdir "已整理"
if not exist "项目清单" mkdir "项目清单"

dir /s /b /a-d "待整理\*" 2>nul | findstr /r "." >nul
if errorlevel 1 (
  echo 待整理\ 目录为空，没有可处理的文件。
  echo 请先将待整理文件放入: %~dp0待整理
  set EXITCODE=1
  goto :pause_exit
)

echo ==^> filekind 整理
echo     工作目录: %~dp0
echo     待整理 -^> 已整理
echo     项目清单: 自动识别或运行中选择
echo     使用说明: %~dp0使用说明.txt
echo.
echo     提示: 首次整理需联网下载约 100MB 语义模型，详见使用说明「Windows 首次联网说明」
echo.

filekind.exe run --apply --no-dry-run --confirm --open-dest
set EXITCODE=%ERRORLEVEL%

:pause_exit
echo.
pause
exit /b %EXITCODE%
