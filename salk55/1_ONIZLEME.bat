@echo off
rem Bu klasordeki projenin 540p ONIZLEME videosunu uretir. Cift tiklayin.
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set "ENGINE=%~dp0..\16x9-engine\"
cd /d "%~dp0"
"%ENGINE%.venv\Scripts\python.exe" "%ENGINE%render.py" --onizleme
for %%f in (renders\*540p_onizleme.mp4) do start "" "%%f"
pause
