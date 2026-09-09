@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title Move Video Candidates to Removable Folder

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
set "PROCESSOR=%PROJECT_DIR%scripts\move_candidates_to_removable_folder.ps1"
set "CONFIG_FILE=%PROJECT_DIR%config.json"

cls
echo ============================================================
echo       Move Reviewed Video Candidates to Removable Folder
echo ============================================================
echo.
echo Source, current report, and target folder are read from config.json:
echo   launch.input_dir
echo   launch.output_dir
echo   deletion.target_folder_name
echo.
echo The current source report is selected automatically.
echo Eligible candidates will be moved immediately to the target folder.
echo.

if not exist "%PROCESSOR%" (
    echo [ERROR] Processor script was not found:
    echo %PROCESSOR%
    echo.
    pause
    exit /b 1
)

if not exist "%CONFIG_FILE%" (
    echo [ERROR] config.json was not found:
    echo %CONFIG_FILE%
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PROCESSOR%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [ERROR] The move operation did not finish normally. Exit code: %EXIT_CODE%
)
echo.
pause
exit /b %EXIT_CODE%
