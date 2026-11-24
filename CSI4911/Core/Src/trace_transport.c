#include "trace_transport.h"

#include "main.h"
#include "trace_buffer.h"

#define TRACE_FRAME_SYNC_0 0xA5U
#define TRACE_FRAME_SYNC_1 0x5AU
#define TRACE_PROTOCOL_VERSION 1U
#define TRACE_MAX_EVENTS_PER_FRAME 8U
#define TRACE_EVENT_WIRE_SIZE 13U
#define TRACE_FRAME_BUFFER_SIZE (2U + 1U + 2U + 4U + 1U + \
                                (TRACE_MAX_EVENTS_PER_FRAME * TRACE_EVENT_WIRE_SIZE) + 2U)
#define TRACE_UART_TIMEOUT_MS 20U

static uint32_t traceFrameSequence;
static uint32_t traceTransportErrorCount;
static uint8_t traceFrame[TRACE_FRAME_BUFFER_SIZE];

static uint16_t Trace_Crc16(const uint8_t *data, uint32_t length)
{
  uint16_t crc = 0xFFFFU;

  for (uint32_t index = 0U; index < length; index++)
  {
    crc ^= (uint16_t)data[index] << 8;
    for (uint8_t bit = 0U; bit < 8U; bit++)
    {
      if ((crc & 0x8000U) != 0U)
      {
        crc = (uint16_t)((crc << 1) ^ 0x1021U);
      }
      else
      {
        crc <<= 1;
      }
    }
  }

  return crc;
}

static void Trace_WriteU16(uint8_t *destination, uint16_t value)
{
  destination[0] = (uint8_t)value;
  destination[1] = (uint8_t)(value >> 8);
}

static void Trace_WriteU32(uint8_t *destination, uint32_t value)
{
  destination[0] = (uint8_t)value;
  destination[1] = (uint8_t)(value >> 8);
  destination[2] = (uint8_t)(value >> 16);
  destination[3] = (uint8_t)(value >> 24);
}

void TraceTransport_Init(void)
{
  GPIO_InitTypeDef gpioInit = {0};

  __HAL_RCC_GPIOG_CLK_ENABLE();
  __HAL_RCC_LPUART1_CLK_ENABLE();
  __HAL_RCC_LPUART1_CONFIG(RCC_LPUART1CLKSOURCE_PCLK1);

  gpioInit.Pin = GPIO_PIN_7 | GPIO_PIN_8;
  gpioInit.Mode = GPIO_MODE_AF_PP;
  gpioInit.Pull = GPIO_NOPULL;
  gpioInit.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
  gpioInit.Alternate = GPIO_AF8_LPUART1;
  HAL_GPIO_Init(GPIOG, &gpioInit);

  LPUART1->CR1 = 0U;
  LPUART1->CR2 = 0U;
  LPUART1->CR3 = 0U;
  LPUART1->BRR = (256U * HAL_RCC_GetPCLK1Freq()) / 115200U;
  LPUART1->CR1 = USART_CR1_TE | USART_CR1_UE;

  traceFrameSequence = 0U;
  traceTransportErrorCount = 0U;
}

void TraceTransport_SendPending(void)
{
  TraceEvent event;
  uint8_t eventCount = 0U;
  uint32_t offset = 10U;
  uint16_t crc;
  uint16_t frameLength;

  while ((eventCount < TRACE_MAX_EVENTS_PER_FRAME) &&
         TraceBuffer_Pop(&event))
  {
    traceFrame[offset++] = event.type;
    Trace_WriteU32(&traceFrame[offset], event.objectId);
    offset += 4U;
    Trace_WriteU32(&traceFrame[offset], event.timestamp);
    offset += 4U;
    Trace_WriteU32(&traceFrame[offset], event.parameter);
    offset += 4U;
    eventCount++;
  }

  if (eventCount == 0U)
  {
    return;
  }

  traceFrame[0] = TRACE_FRAME_SYNC_0;
  traceFrame[1] = TRACE_FRAME_SYNC_1;
  traceFrame[2] = TRACE_PROTOCOL_VERSION;
  Trace_WriteU32(&traceFrame[5], traceFrameSequence++);
  traceFrame[9] = eventCount;
  frameLength = (uint16_t)(1U + 2U + 4U + 1U +
                           ((uint16_t)eventCount * TRACE_EVENT_WIRE_SIZE) + 2U);
  Trace_WriteU16(&traceFrame[3], frameLength);
  crc = Trace_Crc16(&traceFrame[2], (uint32_t)(offset - 2U));
  Trace_WriteU16(&traceFrame[offset], crc);
  offset += 2U;

  uint32_t start = HAL_GetTick();
  for (uint32_t index = 0U; index < offset; index++)
  {
    while ((LPUART1->ISR & USART_ISR_TXE_TXFNF) == 0U)
    {
      if ((HAL_GetTick() - start) >= TRACE_UART_TIMEOUT_MS)
      {
        traceTransportErrorCount++;
        return;
      }
    }

    LPUART1->TDR = traceFrame[index];
  }
}

uint32_t TraceTransport_GetErrorCount(void)
{
  return traceTransportErrorCount;
}
