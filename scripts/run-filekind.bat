@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions
cd /d "%~dp0"
set "EXITCODE=0"
set "LOG=%~dp0run-filekind.log"
set "SYS=%~dp0_系统"

echo ===== %date% %time% =====>"%LOG%"

if not exist "filekind.exe" (
  echo [ERROR] filekind.exe not found>>"%LOG%"
  echo 未找到 filekind.exe。请复制完整的 dist\filekind 文件夹。
  set EXITCODE=1
  goto :pause_exit
)

if not exist "_internal" (
  echo [ERROR] _internal folder missing>>"%LOG%"
  echo 未找到 _internal 目录。请解压整个 filekind 文件夹，不要只复制 exe。
  set EXITCODE=1
  goto :pause_exit
)

if not exist "%SYS%" mkdir "%SYS%"

if not exist "%SYS%\projects.yaml" (
  if exist "%SYS%\projects.example.yaml" (
    copy /y "%SYS%\projects.example.yaml" "%SYS%\projects.yaml" >nul
    echo 已从 _系统\projects.example.yaml 生成 _系统\projects.yaml。
  ) else if exist "projects.example.yaml" (
    copy /y "projects.example.yaml" "%SYS%\projects.yaml" >nul
    echo 已从 projects.example.yaml 生成 _系统\projects.yaml。
  )
)

if not exist "待整理" mkdir "待整理"
if not exist "已整理" mkdir "已整理"
if not exist "项目清单" mkdir "项目清单"

set "HAS_FILES="
for /f "delims=" %%F in ('dir /b /a-d "待整理\*" 2^>nul') do (
  set "HAS_FILES=1"
  goto :inbox_ok
)
if not defined HAS_FILES (
  echo 待整理\ 目录为空，没有可处理的文件。>>"%LOG%"
  echo 待整理\ 目录为空，没有可处理的文件。
  echo 请先将待整理文件放入: %~dp0待整理
  set EXITCODE=1
  goto :pause_exit
)
:inbox_ok

echo ==^> filekind 整理
echo     工作目录: %~dp0
echo     待整理 -^> 已整理
echo     项目清单: 自动识别或运行中选择
echo     配置文件: %SYS%\projects.yaml
echo     使用说明: %~dp0使用说明.txt
echo     日志文件: %LOG%
echo.
echo     提示: 首次整理需联网下载约 100MB 语义模型，详见使用说明「Windows 首次联网说明」
echo.

set "FILEKIND_FROM_BAT=1"
call filekind.exe run --apply --no-dry-run --confirm --open-dest >>"%LOG%" 2>&1
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
  echo.
  echo 整理未成功完成（错误码 %EXITCODE%）。请打开日志查看详情:
  echo %LOG%
)

:pause_exit
echo.
pause
exit /b %EXITCODE%
