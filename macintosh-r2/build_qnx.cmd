@echo off
setlocal
cd /d "%~dp0"
if not exist build mkdir build
if "%QNX_SDP_DIR%"=="" (
 echo Set QNX_SDP_DIR to QNX SDP directory.
 exit /b 2
)
if not exist "%QNX_SDP_DIR%\qnxsdp-env.bat" exit /b 2
call "%QNX_SDP_DIR%\qnxsdp-env.bat"
if errorlevel 1 exit /b 1
qcc -Vgcc_ntoaarch64le -std=c11 -O2 -Wall -Wextra -Werror -Iinclude src\trace_metrics_v2.c src\metrics_cli_v2.c -o build\trace_metrics_v2
if errorlevel 1 exit /b 1
qcc -Vgcc_ntoaarch64le -std=c11 -O2 -Wall -Wextra -Werror -Iinclude src\uart_collector_v1.c -o build\uart_collector_v1
if errorlevel 1 exit /b 1
echo PASS QNX AArch64 cross-build; native serial execution not yet verified
