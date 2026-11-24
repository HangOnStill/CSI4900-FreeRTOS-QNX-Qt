# NUCLEO-L552ZE-Q board wiring preflight (NO HARDWARE MODIFICATIONS PERFORMED)

Official board documentation: STMicroelectronics UM2581 Rev 5 (May 2022), Section 6.12, Table 10, printed page 26 and solder bridge table, printed page 32:
https://www.st.com/resource/en/user_manual/dm00615305-stm32l5-nucleo-144-board-mb1361-stmicroelectronics.pdf
Board schematic MB1361-L552ZEQ-C02:
https://www.st.com.cn/resource/en/schematic_pack/mb1361-l552zeq-c02_schematic.pdf

## Critical correction to previous live UART planning
- The archived firmware configures GPIOG PG7/PG8 AF8 for LPUART1, 115200 baud. **PG7 is TX; PG8 is RX.**
- ST's **default** NUCLEO-L552ZE-Q solder-bridge routing: SB127 and SB129 ON, SB124, SB126, SB128 and SB130 OFF. LPUART1 PG7/PG8 is connected to on-board ST-LINK VCP; **it is NOT thereby available on Arduino D1/D0**.
- Arduino D1/D0 routing of LPUART1 would require different bridge positions: SB128 and SB130 ON and SB123, SB125, SB127 and SB129 OFF (see UM2581 Table 10). Do not assume this is the actual hardware configuration, and DO NOT rework solder bridges without inspection/approval.
- ST morpho CN12 availability of PG7 and PG8 additionally depends on solder bridges SB168 (PG7) and SB167 (PG8) respectively; OFF means disconnected (UM2581 solder bridge table, page 32). Confirm actual board PCB revision and bridge continuity before attempting any wiring.
- The default UART exposed on Arduino D1/D0 is **USART3** PD8/PD9, not the source's configured LPUART1 PG7/PG8. A simple D1->Pi physical-28 cable under the default board configuration would NOT capture the expected v1 trace.
- Verify MCU VDDIO2 voltage and Pi 3.3V logic compatibility. Connect the UART data line ONLY after both boards are fully powered off and correct electrical routing is established; common GND is mandatory.
- NEVER connect the Pi header's 5V power pins to STM32 UART or MCU I/O pins. The existing Pi physical 27-28 shorting jumper must first be removed while power is fully off.

## Independent test before rewiring (recommended)
With the STM32 board connected to Windows through the board's ST-LINK USB interface, its default LPUART1 output should be visible on the ST-LINK VCP serial COM port, provided the correct firmware is actually running and bridges retain default settings. This is a **separate Windows-side serial capture**, not STM32->QNX native UART.

A read-only bounded Windows PowerShell capture helper lives in CSI4911/integration/Step17_Capture_STLink_VCP_Windows.ps1. It can capture raw COMx bytes for the corrected host collector's --fixture mode; never use ReadExisting/text mode for binary trace captures. Confirm firmware version, actual COM port, source DWT frequency and live CRC before interpreting timings. No capture was run (STM32 board powered off).

## Xavier confirmation needed
Please supply a board top/bottom photo showing actual PCB revision, SB127/SB128/SB129/SB130/SB167/SB168 bridge configuration, and exact UART header pins or approve the Windows ST-LINK VCP validation route. Provide your latest flashed firmware source/commit, runtime clock and task identities. Physical connection to Pi should be chosen **only then**.
