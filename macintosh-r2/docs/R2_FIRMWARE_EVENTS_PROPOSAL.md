# CSI4900 Proposed STM32 Trace Extensions (Macintosh -> Xavier review)
Status: DRAFT - no actual STM32 firmware modification. Based on the available November 15 source. This is a protocol design proposal, not an approved UART wire format or a running hardware implementation.

## Source baseline and reason for an extension
- Xavier's trace_buffer.h only defines TASK_SWITCH_IN=1 and TASK_SWITCH_OUT=2.
- His TraceEvent struct includes type, objectId, parameter, timestamp, sequence.
- trace_transport.c sends 13-byte v1 records but DOES NOT send TraceEvent.sequence and does not transmit TraceBuffer_GetOverflowCount.
- The current trace Record function uses FreeRTOS task-name/priority lookup. That code is NOT ISR-safe and must not be called from ISR callbacks.
- The UART transmitter is a separate lower-priority task, which is the right direction; do not block/send UART bytes directly in an interrupt.
- The existing v1 sender may stop midframe on a 20 ms HAL_GetTick timeout; the collector must detect truncated frames and resynchronize.

## Proposed normalized events (not yet wire IDs)
| Event | Subject ID | Other fields required | Semantics |
|---|---|---|---|
| RELEASE | stable task | activation ID, timestamp | A new period/job becomes ready; no inference from switch-in |
| COMPLETE | task | activation ID | Exactly that job finishes (not same as switch-out) |
| SWITCH_IN | task or explicit idle | prior CPU context | Task begins occupying CPU |
| SWITCH_OUT | task or explicit idle | reason: preempt/yield/block/terminate | Task leaves CPU; do not assume preemption |
| BLOCK / UNBLOCK | task | object type, object ID, optional target | Waiting interval on queue/semaphore/mutex |
| ISR_ENTER / ISR_EXIT | stable ISR/vector ID | nesting context | Bracket ISR active time, even during nested interrupt |
| MUTEX_WAIT / MUTEX_ACQUIRED / MUTEX_RELEASED | stable mutex | owner task, waiter task, base/current priorities | Distinguish normal waiting from priority-inversion sequence |
| PRIORITY_INHERIT / PRIORITY_RESTORE | task | prior/new effective priority, causing mutex | Establish whether inheritance occurred |
| QUEUE_WAIT / QUEUE_WAKE | stable queue | task, wait reason, status | Distinguish queue blocking/release |
| SEMAPHORE_WAIT / SEMAPHORE_SIGNAL | semaphore | task/ISR caller and result | Explain unblocking attribution |
| IDLE_ENTER / IDLE_EXIT | explicit idle actor | timebase | Observed idle; unknown time is not idle |
| TRACE_LOSS | source | cumulative dropped records, event-sequence discontinuity | Explicitly invalidate metrics over lost regions |
| TIMEBASE_EPOCH | source | reset identity, tick frequency, epoch | Prevent false 32-bit-wrap interpretations |

Avoid choosing on-wire type numbers or packing fields until Xavier confirms protocol versioning. Keep version 1 decoder unchanged; add version 2 only with shared golden binary fixtures and an explicit compatibility policy.

## Firmware instrumentation design
1. Provide a single O(1), bounded append API with two safe call paths: task context and ISR context. ISR path accepts an explicit ISR ID and never calls pcTaskGetName, uxTaskPriorityGet or blocking HAL routines. Do not use task-only FreeRTOS APIs in ISR.
2. Protect head/tail/sequence/counter operations for relevant execution contexts. Cortex-M interrupt priority, FreeRTOS critical section semantics and any NMI/HardFault exclusions must be reviewed. Do not simply wrap everything in a generic mutex.
3. Capture a monotonic cycle timestamp at the hook entry and append a compact fixed-length event; no printf, heap allocation, sleeping, UART poll, network operations or unbounded name hashing in the critical path.
4. Allocate stable IDs at task/object creation or via an explicit registered lookup; avoid transient name hashes as sole identity if collisions/truncation possible.
5. Distinguish source event sequence from UART frame sequence. Expose overflow/dropped records with monotonic counters even when a record cannot be buffered.
6. Define event ordering at the exact same timestamp. ISR enter/exit and task switches need a deterministic tie policy or stream order preserved.
7. Provide a separate periodic reference measurement using an STM32 hardware timer independent of DWT trace timing. Verify that timer is available, configure it against an actual stable clock, estimate timer read overhead independently, and capture paired task/ISR markers. Avoid claiming independence when both values use the same counter.
8. Report actual SystemCoreClock/DWT cycles-per-microsecond from running firmware and detect clock changes, wrap, reset. The existing v1 reference assumes 16 MHz only because the reviewed snapshot does.

## Validation and performance budget
- Unit tests: normal task activation, context switching, nested ISRs, mutex waiter/owner, inherited priority, queue/semaphore blocking, explicit idle, overflowing ring, event/frame gaps, timebase reset.
- Verify no UART transmission happens in ISR; count trace source loss, midframe transmission failure, receive CRC errors and resync independently.
- Sustained UART capacity at 115200 8N1 is about 11,520 bytes/second before framing overhead; protocol extensions that increase record size must be measured for overflow under realistic ISR rates. Do not silently assume 8 records/frame or a 32-byte event is sustainable.
- Controlled priority inversion must demonstrate owner/waiter priority, competing runnable medium-priority actor and/or inheritance resolution; mere BLOCK_TOO_LONG is insufficient to prove inversion.
- C0-C3: collect comparable workloads without instrumentation, task hooks only, task+ISR+sync hooks, then full live UART/QNX/Qt. Report added hook execution time and trace drop fraction.

## Hand-off steps
- Xavier: deliver current firmware source (Nov 15 snapshot may be stale), clock configuration, full QNX collector and Qt GUI interfaces.
- Macintosh: review registration and ISR-safe writer design, integrate the normalized event sink into the new R2 QNX metrics module, and supply tests for all event types after the protocol is agreed.
- Joint: approve a versioned wire codec, event IDs, object identity, drop counter and UDP record schema before editing Xavier's files. Do not edit the official mainline in this proposal.
