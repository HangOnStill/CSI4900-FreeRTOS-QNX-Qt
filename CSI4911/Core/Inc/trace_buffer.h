#ifndef TRACE_BUFFER_H
#define TRACE_BUFFER_H

#include <stdbool.h>
#include <stdint.h>

typedef enum
{
  TRACE_EVENT_TASK_SWITCH_IN = 1U,
  TRACE_EVENT_TASK_SWITCH_OUT = 2U
} TraceEventType;

typedef struct
{
  uint32_t timestamp;
  uint32_t sequence;
  uint32_t objectId;
  uint32_t parameter;
  uint8_t type;
} TraceEvent;

void Trace_Init(void);
bool TraceBuffer_Pop(TraceEvent *event);
uint32_t TraceBuffer_GetOverflowCount(void);
uint32_t TraceBuffer_GetCount(void);
void Trace_OnTaskSwitchedIn(void);
void Trace_OnTaskSwitchedOut(void);

#endif
