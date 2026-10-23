@echo off
rem Bu klasordeki projenin 4K (3840x2160) FINAL videosunu uretir. Uzun surer.
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set "ENGINE=%~dp0..\16x9-engine\"
cd /d "%~dp0"
"%ENGINE%.venv\Scripts\python.exe" "%ENGINE%render.py" --4k
for %%f in (renders\*2160p_4K.mp4) do start "" "%%f"
pause
