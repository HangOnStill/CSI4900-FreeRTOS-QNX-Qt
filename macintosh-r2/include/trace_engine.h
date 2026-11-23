#ifndef CSI4900_TRACE_ENGINE_H
#define CSI4900_TRACE_ENGINE_H
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#define TRACE_MAX_TASKS 32
#define TRACE_MAX_ISRS 16
#define TRACE_MAX_ISR_DEPTH 8

typedef enum {
 EV_RELEASE, EV_SWITCH_IN, EV_SWITCH_OUT, EV_COMPLETE,
 EV_BLOCK, EV_UNBLOCK, EV_ISR_ENTER, EV_ISR_EXIT, EV_GAP
} trace_event_type;
typedef struct {
 uint64_t ts_us;
 trace_event_type type;
 int id;
 int aux;
} trace_event;
typedef struct {
 int configured, id;
 uint64_t period_us, deadline_us, jitter_bound_us, block_bound_us;
 int active, running, blocked;
 uint64_t release_us, run_start_us, block_start_us, cpu_current_us, block_current_us;
 uint64_t last_release_us;
 int has_last_release;
 unsigned preempt_current;
 uint64_t completions, total_cpu_us, total_response_us, total_block_us;
 uint64_t deadline_misses, jitter_violations, block_violations;
 uint64_t preemptions, invalid_activations;
} trace_task;
typedef struct {
 int configured, id;
 uint64_t budget_us, calls, total_duration_us, max_duration_us, over_budget;
} trace_isr;
typedef struct {
 int id;
 uint64_t entered_us;
} trace_isr_frame;
typedef struct {
 trace_task tasks[TRACE_MAX_TASKS];
 trace_isr isrs[TRACE_MAX_ISRS];
 trace_isr_frame stack[TRACE_MAX_ISR_DEPTH];
 int depth, running_task;
 uint64_t first_ts, last_ts;
 int started, gap_seen;
 uint64_t gaps, warnings, parse_errors;
 FILE *out;
} trace_engine;
void trace_engine_init(trace_engine *, FILE *);
int trace_config_task(trace_engine *, int id, uint64_t period_us, uint64_t deadline_us, uint64_t jitter_bound_us, uint64_t block_bound_us);
int trace_config_isr(trace_engine *, int id, uint64_t budget_us);
int trace_feed(trace_engine *, const trace_event *);
void trace_finish(trace_engine *);
int trace_parse_type(const char *, trace_event_type *);
#endif
