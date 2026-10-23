@echo off
rem Proje klasorunu bu dosyanin uzerine surukleyin: 1080p FINAL video uretir.
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set "ENGINE=%~dp0"
if "%~1"=="" (echo Proje klasorunu URET.bat uzerine surukleyin. & pause & exit /b 1)
pushd "%~1"
"%ENGINE%.venv\Scripts\python.exe" "%ENGINE%render.py"
for %%f in (renders\*1080p.mp4) do start "" "%%f"
popd
pause
