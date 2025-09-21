@echo off
echo Starting Image Batch Downloader...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found, please ensure Python is installed and added to PATH
    pause
    exit /b 1
)

REM Check if dependencies are installed
echo Checking dependencies...
python -c "import requests, bs4, PIL" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Error: Failed to install dependencies
        pause
        exit /b 1
    )
)

REM Create necessary directories
if not exist "downloads" mkdir downloads
if not exist "logs" mkdir logs

REM Start the program
echo Starting program...
python main.py

if errorlevel 1 (
    echo Program execution failed
    pause
)