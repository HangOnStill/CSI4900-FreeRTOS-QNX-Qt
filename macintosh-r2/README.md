# Macintosh R2 — QNX timing metrics and diagnostics

**CSI 4900 (Fall 2026), integration candidate — not a finished end-to-end release.** This folder contains the Macintosh-side portable C11 timing engine, a normalized event CLI, Qt-neutral JSONL/CSV exporter, timer-comparison harness, synthetic fixtures and tests. Xavier's firmware/collector/Qt work is not contained here.

## Build and test

On Windows with GCC in PATH:

```powershell
cd macintosh-r2
cmd /c build_host.cmd
py -3 -m unittest tests.test_metrics_v2 tests.test_qt_export_v2 tests.test_timer_reference_v2 tests.test_r1_r2_consistency -v
.\build\trace_metrics_v2_host.exe .\fixtures\config.csv .\fixtures\r2_nested_gap.csv 100
```

On Linux/macOS with a C compiler: `sh build_host.sh` followed by `python3 -m unittest discover -s tests -v` (note that the tests also require the host binaries to have the published `.exe` names). For QNX 8 on Windows, set `QNX_SDP_DIR` to the installed SDK root and run `build_qnx.cmd` — this builds AArch64 but does not certify native execution.

## Scope and data contract

Input: **validated, timestamp-ordered normalized microsecond events**, with explicit GAP on missing/corrupt frame or source overflow. Supported tokens: RELEASE, SWITCH_IN, SWITCH_OUT, COMPLETE, BLOCK, UNBLOCK, ISR_ENTER, ISR_EXIT, GAP. The optional `IDLE,<id>` configuration describes an observed idle actor. Unknown CPU time is never fabricated as idle. ISR inclusive durations and exclusive execution time differ under nesting. CPU/task/ISR/idle/unknown exclusive time sums to each window length.

The source-derived November 15 STM32 v1 protocol contains only task switch events, so R2 **cannot infer release/complete/ISR/synchronization** from that stream. The R1 analyzer included here is a test/reference component, not a production UART collector. All wire protocol and live UDP/Qt interface changes require Xavier's review.

Offline exports: `docs/Step10_Export_Qt_Diagnostics.py` emits versioned `diagnostics.jsonl`, statistics, warnings and utilization CSVs. These are not yet implemented as live Qt panels. `docs/Step11_Timing_Reference_Compare.py` uses paired marker intervals and subtracts reference read overhead, but currently only synthetic example data exists. `docs/Step12_Run_Anomaly_Matrix.py` runs nine synthetic violation checks.

## Verification

**PASS:** host GCC and QNX AArch64 cross-build (local development environment); 25 host regressions and nine R1 anomaly fixtures; 22/22 physical Pi GPIO UART2 loopback from previous local work; preexisting R1 12/12 QNX smoke and 11/11 provisional UDP reception.

**PENDING/NOT TESTED:** native R2 on QNX (last attempt produced `SSHException: No existing session`), any live NUCLEO→QNX→Qt trace, Xavier's live Qt statistics panels, firmware ISR/mutex/semaphore/queue hooks, independent hardware timer validation, C0–C3 and 30-minute stability evaluation.

See `docs/INTEGRATION_STATUS.md` and `docs/R2_FIRMWARE_EVENTS_PROPOSAL.md`. No passwords, host-key pins, generated binaries or Pi boot image are committed.
