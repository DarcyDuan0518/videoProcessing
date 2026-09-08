@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title Camera Video Sorter

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
set "PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"
set "SORTER=%PROJECT_DIR%video_sorter.py"
set "DEFAULT_CONFIG=%PROJECT_DIR%config.json"

cls
echo ============================================================
echo                 Camera Video Sorter
 echo ============================================================
echo.
echo This program only reads videos and creates CSV reports.
echo It never deletes, moves, or changes source videos.
echo.

if not exist "%PYTHON%" (
    echo [ERROR] Python virtual environment .venv was not found.
    echo Run scripts\install_windows.ps1 before starting this launcher.
    echo.
    pause
    exit /b 1
)

if not exist "%SORTER%" (
    echo [ERROR] video_sorter.py was not found.
    echo Keep this BAT file in the project root directory.
    echo.
    pause
    exit /b 1
)

if not exist "%DEFAULT_CONFIG%" (
    echo [ERROR] config.json was not found.
    echo Keep the single config.json file in the project root directory.
    echo.
    pause
    exit /b 1
)

echo.
echo Example video directory: E:\CameraArchive
echo Press Enter to use this project's data folder for testing.
set /p "INPUT_DIR=Video input directory: "
if "%INPUT_DIR%"=="" set "INPUT_DIR=%PROJECT_DIR%data"

if not exist "%INPUT_DIR%" (
    echo.
    echo [ERROR] Input directory does not exist: %INPUT_DIR%
    echo.
    pause
    exit /b 1
)

echo.
echo Default configuration: %DEFAULT_CONFIG%
echo Press Enter to use the default, or enter another JSON file path.
set /p "CONFIG_FILE=Configuration file: "
if "%CONFIG_FILE%"=="" set "CONFIG_FILE=%DEFAULT_CONFIG%"

if not exist "%CONFIG_FILE%" (
    echo.
    echo [ERROR] Configuration file does not exist: %CONFIG_FILE%
    echo.
    pause
    exit /b 1
)

echo.
echo Reports will be placed in a new folder under reports.
set /p "REPORT_NAME=Report folder name (Enter for automatic name): "
if "%REPORT_NAME%"=="" set "REPORT_NAME=run_%RANDOM%_%RANDOM%"
set "OUTPUT_DIR=%PROJECT_DIR%reports\%REPORT_NAME%"

cls
echo ============================================================
echo Ready to analyze
 echo Input directory: %INPUT_DIR%
echo Configuration:   %CONFIG_FILE%
echo Report directory: %OUTPUT_DIR%
echo.
echo The program displays video number, percent complete, and ETA.
echo Keep this window open. Press Ctrl+C only when you need to stop.
echo ============================================================
echo.

"%PYTHON%" "%SORTER%" --input-dir "%INPUT_DIR%" --config "%CONFIG_FILE%" --output-dir "%OUTPUT_DIR%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo ============================================================
    echo Analysis completed. Opening report folder:
    echo %OUTPUT_DIR%
    echo ============================================================
    start "" "%OUTPUT_DIR%"
) else (
    echo ============================================================
    echo Analysis did not finish normally. Exit code: %EXIT_CODE%
    echo See errors above and rerun for a complete report.
    echo ============================================================
)
echo.
pause
exit /b %EXIT_CODE%
