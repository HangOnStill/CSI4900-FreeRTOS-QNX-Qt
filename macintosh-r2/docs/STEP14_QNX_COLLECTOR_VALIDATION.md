# CSI4900 — UART v1 QNX Collector: Review and Native Test Plan
Date: 2026-11-23 Toronto. Source branch: feature/macintosh-r2-metrics, Xavier commit 1d736e9339aa70aae66edfb2debf392cb7f42bb1.
Review branch (LOCAL ONLY): review/collector-v1-offline-tests. This plan and fixes have NOT been pushed to Xavier's shared branch.

## Review status

1. Xavier added macintosh-r2/src/uart_collector_v1.c, 408 lines. It reads offline v1 binary frames or /dev/ser2, validates CRC-16/CCITT init FFFF, sees frame sequence gaps and emits task switch CSV with cycles-to-us conversion.
2. Original collector FAILS -std=c11 -Wall -Wextra -Werror cross-build for Windows and QNX AArch64. The isolated local review fixes headers/feature macros and removes nonportable cfmakeraw.
3. Original review baseline 5/12 collector regression checks passed; important bugs included dropping second frame from a single read, unreported partial EOF, missing sequence gap after frame zero, reversed timestamps on GAP, silent unsupported event, and fractional cycle truncation.
4. Corrected isolated local branch PASS Windows GCC and QNX qcc builds with -Wall -Wextra -Werror. 12/12 collector tests pass. Original R2 tests 25/25 pass. Three contract checks demonstrate CURRENT v1 stream is NOT accepted as valid R2 analysis, yielding 40/40 test PASS for EXPECTED outcomes.
5. There is NO native QNX execution result for this new collector, and NO live STM32 UART capture. The board was previously shut down and must not be remotely power-cycled or assumed online.

## Frame specification checked against Xavier's earlier trace_transport.c

- sync bytes A5 5A
- version = 1
- 16-bit little-endian declared length = 10 + 13*n for n in [1,8]
- 32-bit little-endian frame sequence (first may be zero)
- event_count = n
- each event 13 bytes: type U8, object hash LE32, DWT cycle counter LE32, param LE32
- CRC16 CCITT-FALSE poly 1021 init FFFF over bytes from version (offset 2) up to but not including CRC
- known task hashes currently derived from SensorTask, ControlTask, LoggerTask, CommunicationTask, then dynamic IDs.
- The current CSI4911.ioc lists defaultTask, task_green, task_blue, task_red, NOT those four names. It configures core HCLK=16MHz but does not by itself prove active firmware SystemCoreClock or UART peripheral state.
- The actual Core/Src STM32 FreeRTOS task code and project-local QNX collector integration are NOT present in the committed CSI4911/ source tree; only IDE metadata, .ioc, launch configurations and linker scripts are pushed.

## Offline synthetic acceptance (already PASS on Windows in isolated review copy)

In macintosh-r2 (the review worktree):
- Windows: build/uart_collector_v1_host.exe
- QNX 8 AArch64: build/uart_collector_v1
- Unit tests: py -3.13 -m unittest tests.test_uart_collector_v1 tests.test_v1_r2_adapter_contract -v
- Golden binary fixture directory: build/qnx_collector_fixture_bundle/
- Bundle manifest: build/qnx_collector_fixture_bundle/manifest.json with SHA256 and expected exit codes.
- Good 2-frame capture: v1_good_two_frames.bin => 4 exact CSV rows: 0,SWITCH_IN,1 / 10,SWITCH_OUT,1 / 20,SWITCH_IN,2 / 30,SWITCH_OUT,2. Exit 0, frames=2, CRC errors=0, seq gaps=0, invalid=0.
- CRC-bad fixture => exit 1, crc_errors=1, emits timestamped GAP.
- Missing frame sequence => exit 1, frame_gaps=1, emits GAP without timestamp reversal.
- Truncated capture => exit 1, invalid_frames>=1, emits GAP.
- The recorder does NOT synthesize RELEASE, COMPLETE or ISR events. R2 consuming v1-only SWITCH_IN/OUT correctly rejects events as INVALID_SWITCH_IN. This is a known protocol integration blocker.

## Next boot: native QNX offline fixture test (NO STM32 hardware required)

PRECONDITIONS:
- Power on QNX Pi normally and wait for startup. Do not modify microSD or boot image.
- QNX SSH host keys live in volatile /dev/shmem. Windows DPAPI backup of the old host private key exists, but does not make QNX startup keys persistent. Expect key rotation. Verify new Pi host identity independently via physical QNX console and/or documented controlled direct-link identity challenge BEFORE updating the Windows pinned known host. Never use StrictHostKeyChecking=no.
- Confirm Windows direct-link source IP 169.254.157.155, Pi 169.254.157.154; qnxuser password known only locally.
- Ensure no other script is using /dev/ser2 or SSH channels; synthetic replay DOES NOT open /dev/ser2.

STAGE binary and four synthetic .bin fixture files onto QNX flat /tmp (RAM-backed) using a strictly host-pinned authenticated upload with bounded byte verification. Do NOT use ordinary Windows PowerShell text piping for binary transfers. The trusted Step7 project uploader's byte comparison procedure can be reused. File names must be flat, e.g.:

/tmp/csi4900_uart_collector_v1
/tmp/csi4900_v1_good_two_frames.bin
/tmp/csi4900_v1_bad_crc.bin
/tmp/csi4900_v1_frame_gap.bin
/tmp/csi4900_v1_truncated.bin

Use chmod +x for the collector and verify the transferred bytes match local SHA-256/size. QNX may not provide sha256sum; compare byte-for-byte through the existing transfer session instead.

In an authenticated QNX qnxuser shell, RUN sequentially:

    /tmp/csi4900_uart_collector_v1 --fixture /tmp/csi4900_v1_good_two_frames.bin --cycles-per-us 16
    echo GOOD_RC=$?
    /tmp/csi4900_uart_collector_v1 --fixture /tmp/csi4900_v1_bad_crc.bin --cycles-per-us 16
    echo CRC_RC=$?
    /tmp/csi4900_uart_collector_v1 --fixture /tmp/csi4900_v1_frame_gap.bin --cycles-per-us 16
    echo GAP_RC=$?
    /tmp/csi4900_uart_collector_v1 --fixture /tmp/csi4900_v1_truncated.bin --cycles-per-us 16
    echo TRUNCATED_RC=$?

EXPECTED: GOOD_RC=0, CRC_RC=1, GAP_RC=1, TRUNCATED_RC=1. Preserve exact stdout, stderr and exit codes in Windows evidence, with target architecture and binary SHA-256. These must pass before any physical serial capture is treated as trustworthy.

## Later: native /dev/ser2 live capture (requires Xavier's complete sources and powered hardware)

1. Ask Xavier for real Core/Src and Core/Inc files, FreeRTOS/trace buffer changes, actual board UART TX pin mapping and clock. Current CSI4911 project pushed is metadata-only. Ask whether 16MHz DWT cycles are genuinely correct and which task-name hashes are transmitted.
2. Shut down/unplug BOTH boards before wiring: remove shorting loopback Pi physical 27-to-28. Connect NUCLEO UART TX (verified 3.3 V signal pin) to Pi physical 28 RXD2, plus shared GND. Optional reverse TX pin 27 to STM32 RX. Do not use RS-232 voltage or 5 V on Pi pins.
3. QNX boot-time pinmux/driver are volatile. Verify GPIO0/1 ALT4 and devc-serpl011 exposes /dev/ser2 at 115200 8N1. Avoid running Pi loopback or pad sampler concurrently with collector.
4. Obtain a bounded live capture (e.g., a future --max-seconds/--max-frames CLI option) while NUCLEO generates known, repeatable frames. As written, --device currently blocks until terminated, so use an operator-supervised short run and expect missing summary on a forceful termination. Do not claim long-run success from a manually killed process.
5. Archive RAW binary frames separately, with capture timestamp, raw byte count, CRC count, sequence-gap count, source ring-buffer overflow count (currently NOT sent), source firmware commit, clock Hz and pin wiring. Decoded CSV alone cannot distinguish every upstream failure.
6. Compare 30-second and 30-minute conditions only after loss diagnostics, bounded collector termination, and timestamp wrap/reset handling are complete.
7. Freeze protocol v2 releases/completions/ISR/mutex/queue data and stable IDs; then rerun collector -> R2 -> Qt offline replay and live integration. Current v1 cannot satisfy the R2 task analysis contract.

## Scope and reproducibility

- Worktree and review tests are LOCAL ONLY and do not modify Xavier's pushed feature branch or main.
- QNX AArch64 cross-build PASS is NOT native QNX execution PASS.
- Golden traces are purely synthetic. Do not present them as actual NUCLEO event measurements.
- Before preparing a PR, review the changes for protocol IDs and timestamp reset handling with Xavier. The current local patch does not solve STM32 source-event overflow counters, timebase epoch resets or v2 semantic events.
