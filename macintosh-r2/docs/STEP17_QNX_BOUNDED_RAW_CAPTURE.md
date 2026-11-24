# CSI4900 - bounded raw QNX UART capture

The source src/uart_capture_v1.c preserves raw serial bytes in a file, with a byte limit and monotonic deadline. It is READ-ONLY with respect to the UART; it never configures GPIO or firmware. Fixture mode works on Windows. Real UART mode is QNX-only.

## Verified now
- Windows GCC strict C11 -Wall -Wextra -Werror build: PASS.
- QNX 8 AArch64 strict C11 cross-build: PASS.
- 27/27 focused Windows tests PASS (12 new raw tests, 12 collector tests, 3 expected R2 contract tests).
- Raw fixture copied byte-exactly and decoded via uart_collector_v1.
- New helper NATIVE QNX execution: NOT TESTED yet; separate from earlier 4/4 native QNX tests of uart_collector_v1.
- Live STM32->QNX UART: NOT TESTED, no STM32/ST-LINK COM port connected.

## Compile and run tests

On Windows, in macintosh-r2:

    gcc -std=c11 -O2 -Wall -Wextra -Werror src/uart_capture_v1.c -o build/uart_capture_v1_host.exe
    set QNX_SDP_DIR=%USERPROFILE%\qnx800
    build_capture_qnx.cmd
    py -3.13 -m unittest tests.test_uart_capture_v1 tests.test_uart_collector_v1 tests.test_v1_r2_adapter_contract -q

## Native QNX synthetic replay (no hardware cable necessary)
After strictly verifying the QNX host key and authenticating, stage the AArch64 helper and a golden binary fixture with byte-verified transport to /tmp. Then on QNX:

    chmod 700 /tmp/csi4900_uart_capture_v1
    /tmp/csi4900_uart_capture_v1 --fixture /tmp/csi4900_v1_good_two_frames.bin --raw-output /tmp/csi4900_raw_capture_001.bin --seconds 2 --max-bytes 100000
    echo CAPTURE_RC=$?
    /tmp/csi4900_uart_collector_v1 --fixture /tmp/csi4900_raw_capture_001.bin --cycles-per-us 16

Capture exit 0 and 4 decoded synthetic switch rows expected. Verify byte equality of source and copied raw fixture.

## Future live experiment (hardware needs separate safety check)
Before any physical wiring, both Pi and STM32 boards must be OFF. Remove the existing Pi physical header 27-to-28 loopback jumper. Verify actual NUCLEO-L552ZE-Q solder bridges: ST UM2581 specifies default PG7/PG8 LPUART1 routes to on-board ST-LINK Virtual COM, not Arduino D1/D0. Use 3.3 V UART TX from verified STM32 header only, connect to Pi RX physical pin 28 and shared GND. Never connect 5V or RS232-level signals.

Only after QNX GPIO ALT4 / devc-serpl011 /dev/ser2 has been verified at 115200 8N1 and no other UART reader exists, run:

    /tmp/csi4900_uart_capture_v1 --device /dev/ser2 --raw-output /tmp/csi4900_capture_001.bin --seconds 20 --max-bytes 1048576

The output is raw evidence only. Status 0 and raw_bytes > 0 means bytes were received but does NOT prove a valid STM32 wire protocol; status 3 means no data; 1 means I/O error; 2 means invalid arguments. Time or byte limits stop the read so the helper cannot wait indefinitely. Never silently overwrite raw-output files. Stage the binary raw capture back to Windows with byte-integrity checks, then run the corrected collector on --fixture using the *measured* DWT cycles-per-us (16 from older source remains provisional).

This does not supply RELEASE, COMPLETE or ISR lifecycle semantics and does not establish R2 end-to-end or Qt acceptance.
