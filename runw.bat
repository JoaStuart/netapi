@echo off
setlocal

cd C:\Users\joa\Documents\Python\netapi

REM Define the path to the Python script
set PYTHON_SCRIPT=.\src\main.py
set ARGS="frontend"

REM Check if the Python script exists
if not exist "%PYTHON_SCRIPT%" (
    echo Error: Main script not found!
    exit /b 1
)

REM Execute script windowed
start pythonw "%PYTHON_SCRIPT%" %ARGS%
