@echo off
setlocal EnableDelayedExpansion
set PYTHON_EXECUTABLE=python3
where /q py
if errorlevel 0 set PYTHON_EXECUTABLE=py
cd /d "%~dp0"
!PYTHON_EXECUTABLE! -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install cnocr==1.2.3.1
pip install -r requirements.txt --index-url https://mirrors.aliyun.com/pypi/simple
endlocal
