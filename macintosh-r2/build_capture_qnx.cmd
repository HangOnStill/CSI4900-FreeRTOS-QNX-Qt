@echo off
setlocal
cd /d "%~dp0"
if "%QNX_SDP_DIR%"=="" set "QNX_SDP_DIR=%USERPROFILE%\qnx800"
if not exist "%QNX_SDP_DIR%\qnxsdp-env.bat" (
  echo MISSING QNX_SDP_DIR environment: %QNX_SDP_DIR%
  exit /b 2
)
call "%QNX_SDP_DIR%\qnxsdp-env.bat"
if errorlevel 1 exit /b 2
if not exist build mkdir build
qcc -Vgcc_ntoaarch64le -std=c11 -O2 -Wall -Wextra -Werror src\uart_capture_v1.c -o build\uart_capture_v1
if errorlevel 1 exit /b 1
echo PASS QNX AArch64 bounded UART raw capture cross-build
