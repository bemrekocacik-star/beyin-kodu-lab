@echo off
rem Proje klasorunu bu dosyanin uzerine surukleyin: 540p hizli onizleme uretir.
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set "ENGINE=%~dp0"
if "%~1"=="" (echo Proje klasorunu ONIZLEME.bat uzerine surukleyin. & pause & exit /b 1)
pushd "%~1"
"%ENGINE%.venv\Scripts\python.exe" "%ENGINE%render.py" --onizleme
for %%f in (renders\*540p_onizleme.mp4) do start "" "%%f"
popd
pause
