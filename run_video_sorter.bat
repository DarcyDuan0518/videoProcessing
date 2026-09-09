@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title Camera Video Sorter

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
set "PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"
set "SORTER=%PROJECT_DIR%video_sorter.py"
set "CONFIG_FILE=%PROJECT_DIR%config.json"

cls
echo ============================================================
echo                 Camera Video Sorter
echo ============================================================
echo.
echo This program only reads videos and creates CSV reports.
echo It never deletes, moves, or changes source videos.
echo Input and output folders are read from config.json.
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

if not exist "%CONFIG_FILE%" (
    echo [ERROR] config.json was not found.
    echo Keep the single config.json file in the project root directory.
    echo.
    pause
    exit /b 1
)

cls
echo ============================================================
echo Starting analysis with folders configured in config.json.
echo The program displays video number, percent complete, and ETA.
echo Keep this window open. Press Ctrl+C only when you need to stop.
echo ============================================================
echo.

"%PYTHON%" "%SORTER%" --config "%CONFIG_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo ============================================================
    echo Analysis completed. The report directory is shown above.
    echo ============================================================
) else (
    echo ============================================================
    echo Analysis did not finish normally. Exit code: %EXIT_CODE%
    echo See errors above and rerun for a complete report.
    echo ============================================================
)
echo.
pause
exit /b %EXIT_CODE%
