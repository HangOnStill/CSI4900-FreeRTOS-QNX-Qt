# CSI4900 R2 wire and Qt interface proposal (RFC; UNIMPLEMENTED)

No existing UART v1 event identifiers are changed by this proposal.

## Verified v1
Frame sync A5 5A, version 1, LE16 remaining length incl. trailing CRC16, LE32 frame sequence, event count 1-8, events [type U8, task-hash LE32, DWT cycles LE32, parameter LE32], CRC16/CCITT-FALSE. Type 1 SWITCH_IN, 2 SWITCH_OUT.

## Required agreement with Xavier
- Define RELEASE and COMPLETE as explicit, separately instrumented FreeRTOS job lifecycle events; do not label a preemption or switch-out as completion. Validate initial job release ordering relative to first switch-in.
- Define ISR_ENTER and ISR_EXIT with actual IRQ identifiers, nesting and interrupt-mask semantics; define BLOCK/UNBLOCK and owned mutex/semaphore/queue identifiers.
- Include source trace-ring overflow count, dropped event sequence count, optional timing-latency measurement and post-GAP resynchronization.
- Distinguish task CPU exclusive time, nested ISR exclusive time, actually observed idle and unknown source gaps. Never fabricate idle.
- Include clock epoch/reset, 32-bit DWT wrap handling and independently verified effective cycles-per-microsecond, not just receive-time clock.
- Reserve a versioned protocol v2 and maintain a backward compatible v1 decoder; unknown v1 types MUST be flagged, not silently ignored.

## Qt-neutral output (proposal)
Every message should include: envelope schema version, source firmware SHA, trace session and boot/clock epoch, event timestamp in cycles and normalized us, task/ISR object identifiers, event kind, frame sequence, CRC status, source overflow status, time quality and GAP warning. Offline JSONL/CSV exports and tests can be implemented without Qt. Native Qt timeline and dashboard must use approved schema.

Integration cannot be marked complete until STM32 firmware, QNX native UART collector, live UDP/Qt display, C0-C3 experiments and prolonged stability test are verified on the same captured source stream.
