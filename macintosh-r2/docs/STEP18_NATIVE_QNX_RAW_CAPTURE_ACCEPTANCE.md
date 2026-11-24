# Native QNX bounded UART raw-capture acceptance — November 24, 2026

**PASS for synthetic native replay; not live STM32.**

## Evidence

Windows evidence folder: evidence/Step18_Native_QNX_Bounded_Raw_Capture_20261124T071630Z

Target: QNX RaspberryPi4B, logged in as qnxuser (uid 1000), strict ED25519 host pin approved by a direct-Ethernet physical challenge and confirmed independently before SSH login. No root access, GPIO setting, serial device access or QNX boot writes were performed in Step18.

QNX AArch64 raw-capture binary SHA-256: b17cbcb9f8ad97139879009ce8df209f0a4ac36971232d9232df4709fca6e9ae

Synthetic input fixture: v1_good_two_frames.bin. Input and QNX native captured output are **76 bytes byte-for-byte identical**, SHA-256 d0658cf7913a6ce484b34b20277f2ed91b785b2cd79310095b14b8e957c2b66b.

| Native QNX test | Exit | Expected | Evidence |
|---|---:|---:|---|
| Fixture -> bounded raw capture | 0 | 0 | raw_bytes=76, no I/O error |
| Native raw file -> corrected collector decoder | 0 | 0 | 2 frames, 4 decoded rows, zero CRC/sequence/invalid errors, golden stdout+stderr exact |
| Refuse existing raw output overwrite | 1 | 1 | expected File exists |
| Byte limit 10 -> exactly first 10 bytes | 0 | 0 | raw_bytes=10, limit_reached=1 |

Decoded switch events:
    0,SWITCH_IN,1
    10,SWITCH_OUT,1
    20,SWITCH_IN,2
    30,SWITCH_OUT,2

Source bytes and native output independently audited again on Windows. Native status PASS. The evidence is not a substitute for STM32 live frames or release/completion/ISR events.

## Rebooted Pi UART2 preparation

After this boot, read-only inventory found /dev/ser1 but **no /dev/ser2**. The unprivileged qnxuser could not inspect BCM2711 GPIO MMIO. The standard audited root post-boot procedure then restored GPIO0/1 to ALT4 TXD2/RXD2 and started devc-serpl011; its physically shorted Pi header 27-28 loopback returned **22/22 bytes**, with physical-loopback exit 0 and register snapshot exit 0. Evidence: evidence/Step7_UART2_Postboot_Physical_Loopback_20261124T071802404682Z.txt.

A bounded live /dev/ser2 *quiet-no-stimulus* test was attempted via docs/Step19_QNX_UART2_Bounded_Quiet_Smoke.py on November 24. The QNX sshd answered with a pre-authentication notice `Banner: Not allowed at this time`; therefore **the quiet serial test DID NOT RUN**. This is a transport/SSH refusal, not a UART capture failure. Evidence: evidence/Step19_QNX_UART2_Bounded_Quiet_Smoke_20261124T071901Z/manifest.json. Avoid rapid SSH retries; diagnose any QNX pre-authentication penalty separately. Do not mark live STM32 integration complete.

## Remaining gating conditions

- Current STM32 firmware, actual LPUART1-to-board-header solder bridge configuration, and measured SystemCoreClock/DWT rate.
- Remove the Pi 27-28 shorting loopback jumper ONLY with both Pi and STM32 powered off; do not attach any STM32 signal with the shorting jumper in place.
- Confirm the ST default board routes PG7 TX / PG8 RX to onboard ST-LINK USB virtual COM, NOT Arduino D1/D0. If unchanged, test Windows ST-LINK VCP first.
- Once powered and wired correctly, capture bounded raw STM32 trace via /dev/ser2 with byte-exact Windows readback and decode CRC/sequence. The v1 switch-only protocol is not full R2 release/complete/ISR timing data.
