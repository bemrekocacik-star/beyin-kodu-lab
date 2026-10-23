@echo off
rem Bu klasordeki projenin 1080p FINAL videosunu uretir. Cift tiklayin.
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set "ENGINE=%~dp0..\16x9-engine\"
cd /d "%~dp0"
"%ENGINE%.venv\Scripts\python.exe" "%ENGINE%render.py"
for %%f in (renders\*1080p.mp4) do start "" "%%f"
pause
