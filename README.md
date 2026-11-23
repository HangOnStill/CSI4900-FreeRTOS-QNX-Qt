# CSI4900 — FreeRTOS / QNX / Qt

Fall 2026 Honours Project: Real-Time FreeRTOS Trace Visualization and Timing Analysis on NUCLEO-L552ZE-Q using Raspberry Pi 4 / QNX 8 and a PC/Qt frontend.

**Team:** Xavier Darboux and Macintosh Chen.

## Project architecture

NUCLEO-L552ZE-Q / FreeRTOS → 3.3 V UART → Raspberry Pi 4B / QNX → Ethernet / UDP → PC / Qt.

The first proposed contribution is the independent [Macintosh R2 metrics and diagnostics module](macintosh-r2/README.md). It includes normalized-event timing analysis, offline Qt-neutral exports, synthetic fixtures and regression tests; it is **not** a completed integrated hardware demonstration. Xavier's firmware and Qt components will be integrated only after the event and transport contracts are agreed.

**Development policy:** use review branches and pull requests; do not commit credentials, host keys, QNX boot images, unreviewed hardware logs, or generated build directories.
