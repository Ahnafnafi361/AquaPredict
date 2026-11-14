@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo  AquaPredict - Color Theme Rollback Script
echo ========================================================
echo.

set "BACKUP_DIR=C:\Users\ASUS\.gemini\antigravity\brain\6167195c-9df1-46f8-bffd-c82724fdbcab\backups\color_theme_backup_20261114_082045"
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

if not exist "%BACKUP_DIR%\public\css\style.css" (
    echo [ERROR] Backup source file not found:
    echo         "%BACKUP_DIR%\public\css\style.css"
    echo Rollback failed. No files were modified.
    exit /b 1
)

if not exist "%BACKUP_DIR%\dist_static\css\style.css" (
    echo [ERROR] Backup static file not found:
    echo         "%BACKUP_DIR%\dist_static\css\style.css"
    echo Rollback failed. No files were modified.
    exit /b 1
)

echo [1/2] Restoring public\css\style.css ...
copy /Y "%BACKUP_DIR%\public\css\style.css" "%PROJECT_DIR%\public\css\style.css" >nul
if errorlevel 1 (
    echo [ERROR] Failed to restore public\css\style.css
    exit /b 1
)

echo [2/2] Restoring dist_static\css\style.css ...
copy /Y "%BACKUP_DIR%\dist_static\css\style.css" "%PROJECT_DIR%\dist_static\css\style.css" >nul
if errorlevel 1 (
    echo [ERROR] Failed to restore dist_static\css\style.css
    exit /b 1
)

echo.
echo ========================================================
echo  SUCCESS: Color theme rolled back to original version!
echo  Restored files:
echo    - %PROJECT_DIR%\public\css\style.css
echo    - %PROJECT_DIR%\dist_static\css\style.css
echo  Backup preserved safely at:
echo    %BACKUP_DIR%
echo ========================================================
exit /b 0

