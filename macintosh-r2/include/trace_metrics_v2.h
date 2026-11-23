/* CSI4900 Macintosh R2 metrics: separate from the unchanged R1 API.
 * Single-core normalized event stream, microseconds, explicit trace quality.
 * No raw UART protocol claims; data must be validated and sorted by collector.
 */
#ifndef CSI4900_METRICS_V2_H
#define CSI4900_METRICS_V2_H
#include <stdint.h>
#include <stdio.h>
#define M2_MAX_TASKS 32
#define M2_MAX_ISRS 16
#define M2_MAX_DEPTH 8
#define M2_MAX_WINDOWS 100000
typedef enum {
 M2_RELEASE, M2_SWITCH_IN, M2_SWITCH_OUT, M2_COMPLETE,
 M2_BLOCK, M2_UNBLOCK, M2_ISR_ENTER, M2_ISR_EXIT, M2_GAP
} m2_event_type;
typedef struct { uint64_t ts; m2_event_type type; int id; } m2_event;
typedef struct {
 int configured, active, blocked;
 uint64_t cpu_us;
} m2_task;
typedef struct {
 int configured;
 uint64_t budget_us, calls, inclusive_us, exclusive_us, max_us, over_budget, incomplete;
} m2_isr;
typedef struct { int id; uint64_t entered_us; } m2_frame;
typedef struct {
 m2_task tasks[M2_MAX_TASKS]; m2_isr isrs[M2_MAX_ISRS];
 m2_frame stack[M2_MAX_DEPTH]; int depth, running, idle_id;
 uint64_t first, previous, window_start, window_end, window_us, windows;
 uint64_t task_total, isr_total, idle_total, unknown_total;
 uint64_t w_task[M2_MAX_TASKS], w_isr[M2_MAX_ISRS];
 uint64_t w_tasks, w_isrs, w_idle, w_unknown;
 uint64_t gaps, warnings;
 int started, w_gap, had_error;
 FILE *out;
} m2_engine;
void m2_init(m2_engine *m, FILE *out, uint64_t window_us);
int m2_config_task(m2_engine *m, int id);
int m2_config_idle(m2_engine *m, int id);
int m2_config_isr(m2_engine *m, int id, uint64_t budget_us);
int m2_feed(m2_engine *m, const m2_event *ev);
int m2_finish(m2_engine *m);
int m2_parse_type(const char *name, m2_event_type *out);
#endif
