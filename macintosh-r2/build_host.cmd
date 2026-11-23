@echo off
setlocal
cd /d "%~dp0"
if not exist build mkdir build
where gcc >nul 2>nul
if errorlevel 1 exit /b 1
gcc -std=c11 -O2 -Wall -Wextra -Werror -Iinclude src\trace_engine.c src\analyze_cli.c -o build\trace_analyzer_host.exe
if errorlevel 1 exit /b 1
gcc -std=c11 -O2 -Wall -Wextra -Werror -Iinclude src\trace_metrics_v2.c src\metrics_cli_v2.c -o build\trace_metrics_v2_host.exe
if errorlevel 1 exit /b 1
echo PASS host build
