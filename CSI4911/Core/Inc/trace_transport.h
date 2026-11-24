#ifndef TRACE_TRANSPORT_H
#define TRACE_TRANSPORT_H

#include <stdint.h>

void TraceTransport_Init(void);
void TraceTransport_SendPending(void);
uint32_t TraceTransport_GetErrorCount(void);

#endif
