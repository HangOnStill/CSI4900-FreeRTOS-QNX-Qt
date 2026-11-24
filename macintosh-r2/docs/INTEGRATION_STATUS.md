# R2 Merge Review — Verified Scope and Dependencies

Date: November 23, 2026. Source-based engineering handoff to Xavier Darboux.

## Ownership

Xavier: FreeRTOS baseline/task switches and trace ring, STM32 UART TX, QNX serial receiver and frame validation, Qt baseline timeline. Macintosh: ISR and synchronization extensions, timing/violation engine, Qt warning/statistics/CSV interfaces, anomaly experiments, separate STM32 timer reference. Joint: event/UDP schema, integration, performance and final demo.

## Evidence

- Pi UART2 /dev/ser2 physical jumper across Pi header 27 and 28 eventually **PASS 22/22** (not an STM32 capture).
- Older R1 native QNX smoke **12/12** and provisional UDP replay **11/11** succeeded.
- R2 host engine and QNX AArch64 cross-build succeeded with GCC/qcc `-Wall -Wextra -Werror`.
- **25 R2 host tests PASS**, including same-event R1/R2 comparisons; 9 R1 synthetic anomaly cases PASS. The local source snapshot of Xavier's 17 recorded files matched hashes.
- The latest R2 native-QNX test **FAILED before completion** at SSH session establishment, with `SSHException: No existing session`. Cross-build does not establish QNX native PASS.

## Integration design

Inputs are normalized ordered microsecond events (not raw wire v1). Collector must detect CRC/sequence/source overflow and emit GAP; handle timebase wrap and reset; map stable task, ISR and synchronization IDs. In nested ISR accounting, CPU goes to the top ISR, then task, explicitly observed idle, or UNKNOWN. Partial/gap windows cannot be called precise total utilization. R1 computes deadline/response statistics only if RELEASE and COMPLETE are explicitly instrumented; do not derive those from switch-outs.

Qt proposal: the offline exporter writes `csi4900.diagnostics.v1` JSONL records and CSV tables. An agreed UDP schema and Qt integration are not yet implemented. When using both R1 and R2 outputs, ensure they are produced from the same source and pass `--source-trace` to the exporter.

## Xavier review requests

1. Supply current firmware, QNX collector and Qt commits; November 15 may not be latest.
2. Agree on distinct RELEASE/COMPLETE, ISR and mutex/semaphore/queue event IDs, object ownership and priority inheritance, timestamp source, overflow/loss counters, and clock epoch.
3. Decide QNX normalized-event callback and Qt UDP/schema boundaries; test offline replay then live.
4. Coordinate NUCLEO wire pinout: remove Pi loopback *while both devices fully unpowered*, connect 3.3 V UART TX→Pi RX and common ground; optional reverse wire. No 5 V UART.
5. Plan I1–I5 progression, priority inversion/overload/drop experiments, C0–C3, 30-minute run and independent STM32 timer comparison.

Do not merge this branch into main before reviewing the proposed interfaces and validating actual QNX R2 execution.
