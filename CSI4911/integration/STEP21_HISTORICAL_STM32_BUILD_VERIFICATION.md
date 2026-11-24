# Step21 — Historical STM32 firmware fresh offline build, 2026-11-24

**PASS: November 15, 2026 archived firmware source only.** This is NOT proof of Xavier's current flashed firmware, real UART signals, or STM32 runtime.

## Toolchain and build provenance

- Machine: DESKTOP-TIQ0VAU. Archived local "Xavier Codes" STM32CubeIDE project copied to a separate private isolated build tree.
- All 17 original Core/Src, Core/Inc and Core/Startup source files matched their archival SHA-256 digests. No firmware C, header, startup assembly, HAL/CMSIS or FreeRTOS vendor source was changed.
- Arm official compiler distribution: https://armkeil.blob.core.windows.net/developer/Files/downloads/gnu/14.3.rel1/binrel/arm-gnu-toolchain-14.3.rel1-mingw-w64-x86_64-arm-none-eabi.zip
- Official publisher's ZIP SHA-256 matches the downloaded archive: 864C0C8815857D68A1BBBA2E5E2782255BB922845C71C97636004A3D74F60986.
- Compiler: Arm GNU Toolchain 14.3.Rel1, gcc 14.3.1, 20250623.
- Verified full rebuilt command in isolated Debug tree: mingw32-make --always-make --jobs=4 all.

## Adjustments to generated build files, solely within the isolated copy

1. The original Debug/makefile references an obsolete absolute linker-script path on Xavier's other computer. Changed the two references to the equivalent relative ../STM32L552ZETXQ_FLASH.ld.
2. The first compilation stopped on the unknown option -fcyclomatic-complexity. Removed exactly seven occurrences of this nonstandard compiler-reporting flag from seven generated Debug/**/subdir.mk files.
3. Retained all other compilation and link flags, including -mcpu=cortex-m33 and hard-float options. The original archive and published Core source were not edited.

## Successful rebuilt output

- Full fresh make exit: 0.
- Architecture: ELF32, ARM little-endian, Cortex-M33 hard-float ABI.
- Newly rebuilt ELF file: CSI4911.elf, 1,575,148 bytes.
- New ELF SHA-256: 900417B036E20E5CB8C73CDF3AC854795D6A7864580E13B9A7AA5109271805F1.
- Historical preexisting Debug ELF SHA-256, distinct: D4C1BDCAA35159E3D347D43FAA9F4C3A1386C36E85B63C3F33302FBF923DAA5E.
- arm-none-eabi-size: text 21872; data 96; bss 45616; decimal 67584; hex 10800.
- Linked symbols: MX_FREERTOS_Init, Trace_OnTaskSwitchedIn, Trace_OnTaskSwitchedOut, TraceTransport_SendPending.
- Build log, acceptance manifest, ELF header, size, trace symbols, and an independent byte-exact copy of new ELF were preserved in local Windows evidence:
  evidence/Step21_Historical_STM32_Fresh_Build_20261124T073815Z/
- The compiled ELF and portable compiler are deliberately NOT committed to the public repository and were NOT flashed to the board.

## Independent reproduction

1. Obtain the matching complete **historical** STM32CubeIDE project, including historical Core, Drivers, Middlewares and generated Debug makefiles. The 17 Core application files alone cannot support a full build.
2. Work on a separate cloned copy; do not edit the archival source directory.
3. Download Arm GNU 14.3.Rel1 from the URL above and independently verify SHA-256 against the published checksum before extraction.
4. In the isolated Debug/makefile change the two obsolete absolute linker-script references to ../STM32L552ZETXQ_FLASH.ld.
5. In generated Debug/**/subdir.mk remove unsupported reporting option -fcyclomatic-complexity (seven occurrences, no other flags).
6. Put the extracted Arm toolchain bin folder into the current process PATH; run mingw32-make --directory Debug --always-make --jobs=4 all.
7. Confirm exit 0, ARM ELF header, symbol map and output SHA-256. The exact ELF hash may vary across computers because of debug paths/timestamps, despite identical source.

## Not established by this build

- Current November 23 or later Xavier firmware; actual MCU flash and execution; NUCLEO board solder bridge routing; current STM32 task-name hashes and physical output; actual DWT cycle frequency; real STM32->QNX UART traffic.
- The committed later CSI4911.ioc names defaultTask, task_green, task_blue and task_red, unlike historical source SensorTask/ControlTask/LoggerTask/CommunicationTask. Do not flash this historical ELF without reconciled current firmware and pinout verification.
- QNX native UART2 local loopback and bounded silent read have passed separately, but the boards have not been connected for STM32 data.
- The Qt 6.12 reference diagnostic UDP receiver passed 51 host tests in PR #4, but Xavier's production Qt application is not present.

**Xavier still needs to supply his actual latest source/commit, currently flashed firmware identity, ST-LINK / PG7 solder bridges and Qt application.**
