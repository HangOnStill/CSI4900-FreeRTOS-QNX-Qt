# CSI4900: STM32 Core source recovery (historical integration candidate)

STATUS: HISTORICAL SOURCE SNAPSHOT ONLY. NOT Xavier's latest Nov 23 firmware. FRESH ARM CORTEX-M33 OFFLINE BUILD PASSED ON 2026-11-24; firmware NOT FLASHED or runtime-verified. See integration/STEP21_HISTORICAL_STM32_BUILD_VERIFICATION.md.

Recovered 17 application files under CSI4911/Core/{Src,Inc,Startup} verbatim from the existing local "Xavier Codes" archive (source modification time 2026-11-15). The GitHub feature commit 1d736e9 contained the .ioc, IDE settings, linker scripts, and collector, but omitted these Core sources. SHA-256 file-by-file verification is in integration/STM32_BASELINE_SOURCE_MANIFEST.json; reproduction: py -3.13 -B CSI4911/integration/audit_stm32_baseline.py.

## Verified at source level, NOT verified on hardware
- Four FreeRTOS threads: SensorTask, ControlTask, LoggerTask, CommunicationTask. Source periods 100, 250, 500 and 10 *RTOS ticks*. Real ms duration needs RTOS tick configuration.
- Task IDs are FNV-1a hashes of names; collector names match the archival app_freertos.c.
- Source trace buffer has TASK_SWITCH_IN (1), TASK_SWITCH_OUT (2), DWT->CYCCNT timestamps, ring capacity 128, overflow counter. No explicit release/complete/ISR in wire v1.
- Archived transport uses LPUART1 and GPIOG PG7/PG8 AF8 at 115200 baud, A5 5A frame prefix, eight event maximum, CCITT CRC16. Which PG pin is actually TX at the NUCLEO connector requires board pinout verification.
- Archived main.c uses HSI nominally 16 MHz, PLL disabled, AHB/APB dividers 1. Actual runtime SystemCoreClock and DWT conversion are NOT measured.

## Blocking discrepancies
1. The committed CSI4911.ioc still names defaultTask, task_green, task_blue, task_red, unlike the source. Regenerating with STM32CubeIDE may overwrite or change the archived custom task code. Resolve before regeneration and preserve USER CODE sections.
2. The original archive contains vendor Drivers, Middlewares and old ELF binaries. On November 24 the exact 17 archived Core files were independently and freshly compiled/linked with Arm GNU Toolchain 14.3.Rel1 in an isolated cloned project: PASS (ELF SHA-256 900417B036E20E5CB8C73CDF3AC854795D6A7864580E13B9A7AA5109271805F1), but this proves **only the 2026-11-15 historical snapshot** builds. Newer Nov 23/current Xavier firmware, actual MCU flash, clock and runtime have NOT been verified. See Step21 verification report.
3. **Critical board-routing issue:** ST UM2581 Rev 5 Section 6.12 says this NUCLEO-L552ZE-Q board defaults to SB127/SB129 ON, LPUART1 PG7(TX)/PG8(RX) connected to ST-LINK USB Virtual COM, and SB128/SB130 OFF (NOT Arduino D1/D0). The GPIOG AF8 source configuration does not make the TX line appear at Arduino D1. CN12 access additionally depends on actual SB168/SB167 bridge continuity. See integration/NUCLEO_L552ZE_Q_PINOUT_PREFLIGHT.md; do not wire the Pi until the exact PCB revision and solder-bridge state are verified.
4. Wire v1 lacks release/completion, ISR and synchronization, source overflow status, and clock-epoch features required by the R2 timing engine; no inferences from switch events can substitute.
5. Xavier's invitation to private 613Xav/CSI4911 was found in email, but the repository was not readable through the connected GitHub account. This branch does NOT claim to supersede those newer files.

## Recommended process
- Xavier to provide current actual firmware Core source + FreeRTOS/trace hooks + his Qt tree or repository access; reconcile old and new source rather than copying over either.
- The older historical project now has a fresh independent Arm GCC offline build with logged evidence. Next, obtain and compile Xavier's CURRENT source; reconcile the .ioc task names; validate actual MCU pinout, run-time HCLK/DWT frequency, live UART output and firmware flash, none of which are established by the archived build.
- On next physical session power BOTH boards fully off first, remove Pi physical 27-28 jumper, connect verified 3.3V STM32 TX to Pi physical pin 28 RX, plus common ground. Do not connect 5V UART.
- On QNX restore the direct SSH host-key trust procedure, initialize GPIO ALT4 and /dev/ser2 if necessary, and capture raw bytes before decoding CRC/sequence and testing end-to-end.
- Agree v2 wire/event semantics and Qt envelope with Xavier before integrating changes into shared production branches.

Native QNX offline collector 4/4 passed previously; see PR #2. Historical Nov 15 STM32 firmware fresh offline compile/link PASS on 2026-11-24. CURRENT Xavier firmware build and hardware STM32->Pi live UART have NOT been tested.
