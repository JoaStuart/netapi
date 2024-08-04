@echo off
setlocal

REM Define the path to the Python script
set PYTHON_SCRIPT=.\src\main.py

REM Check if the Python script exists
if not exist "%PYTHON_SCRIPT%" (
    echo Error: Main script not found!
    exit /b 1
)

:loop
REM Run the Python script with all provided arguments
python "%PYTHON_SCRIPT%" %*
set EXIT_CODE=%ERRORLEVEL%

REM Check if the exit code is 2
if %EXIT_CODE% equ 12 (
    echo Restarting...
    goto loop
)

exit /b %EXIT_CODE%
