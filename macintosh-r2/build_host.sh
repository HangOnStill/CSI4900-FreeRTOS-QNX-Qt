#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p build
cc -std=c11 -O2 -Wall -Wextra -Werror -Iinclude src/trace_engine.c src/analyze_cli.c -o build/trace_analyzer_host.exe
cc -std=c11 -O2 -Wall -Wextra -Werror -Iinclude src/trace_metrics_v2.c src/metrics_cli_v2.c -o build/trace_metrics_v2_host.exe
cc -std=c11 -O2 -Wall -Wextra -Werror -Iinclude src/uart_collector_v1.c -o build/uart_collector_v1
