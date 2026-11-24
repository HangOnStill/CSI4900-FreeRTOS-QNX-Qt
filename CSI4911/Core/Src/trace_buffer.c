#include "trace_buffer.h"

#include "FreeRTOS.h"
#include "task.h"
#include "stm32l5xx.h"

#define TRACE_BUFFER_CAPACITY 128U

static TraceEvent traceBuffer[TRACE_BUFFER_CAPACITY];
static volatile uint32_t traceHead;
static volatile uint32_t traceTail;
static volatile uint32_t traceSequence;
static volatile uint32_t traceOverflowCount;

static uint32_t Trace_GetTimestamp(void)
{
  return DWT->CYCCNT;
}

static uint32_t Trace_GetTaskId(void)
{
  const char *name = pcTaskGetName(NULL);
  uint32_t hash = 2166136261U;

  while (*name != '\0')
  {
    hash ^= (uint8_t)*name;
    hash *= 16777619U;
    name++;
  }

  return hash;
}

static void Trace_Record(uint8_t type)
{
  uint32_t head = traceHead;
  uint32_t nextHead = (head + 1U) % TRACE_BUFFER_CAPACITY;
  TraceEvent *event;

  if (nextHead == traceTail)
  {
    traceOverflowCount++;
    return;
  }

  event = &traceBuffer[head];
  event->timestamp = Trace_GetTimestamp();
  event->sequence = traceSequence++;
  event->objectId = Trace_GetTaskId();
  event->parameter = (uint32_t)uxTaskPriorityGet(NULL);
  event->type = type;
  __DMB();
  traceHead = nextHead;
}

void Trace_Init(void)
{
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
  DWT->CYCCNT = 0U;
  DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
  traceHead = 0U;
  traceTail = 0U;
  traceSequence = 0U;
  traceOverflowCount = 0U;
}

bool TraceBuffer_Pop(TraceEvent *event)
{
  uint32_t tail;

  if (event == NULL)
  {
    return false;
  }

  tail = traceTail;
  if (tail == traceHead)
  {
    return false;
  }

  __DMB();
  *event = traceBuffer[tail];
  traceTail = (tail + 1U) % TRACE_BUFFER_CAPACITY;
  return true;
}

uint32_t TraceBuffer_GetOverflowCount(void)
{
  return traceOverflowCount;
}

uint32_t TraceBuffer_GetCount(void)
{
  uint32_t head = traceHead;
  uint32_t tail = traceTail;

  if (head >= tail)
  {
    return head - tail;
  }

  return TRACE_BUFFER_CAPACITY - tail + head;
}

void Trace_OnTaskSwitchedIn(void)
{
  Trace_Record(TRACE_EVENT_TASK_SWITCH_IN);
}

void Trace_OnTaskSwitchedOut(void)
{
  Trace_Record(TRACE_EVENT_TASK_SWITCH_OUT);
}
