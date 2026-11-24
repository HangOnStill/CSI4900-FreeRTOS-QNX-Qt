/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * File Name          : freertos.c
  * Description        : Code for freertos applications
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "trace_buffer.h"
#include "trace_transport.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN Variables */

/* USER CODE END Variables */

/* Private function prototypes -----------------------------------------------*/
/* USER CODE BEGIN FunctionPrototypes */

/* USER CODE END FunctionPrototypes */

/* Private application code --------------------------------------------------*/
/* USER CODE BEGIN Application */
#include "cmsis_os.h" // Required for CMSIS-RTOS v2 API

/* Task function prototypes */
void StartTask_Sensor(void *argument);
void StartTask_Control(void *argument);
void StartTask_Logger(void *argument);
void StartTask_Communication(void *argument);

const osThreadAttr_t sensorTask_attributes = {
  .name = "SensorTask",
  .stack_size = 512 * 4, // Changed from 128 to 512
  .priority = (osPriority_t) osPriorityLow,
};
const osThreadAttr_t controlTask_attributes = {
  .name = "ControlTask",
  .stack_size = 512 * 4, // Changed from 128 to 512
  .priority = (osPriority_t) osPriorityNormal,
};
const osThreadAttr_t loggerTask_attributes = {
  .name = "LoggerTask",
  .stack_size = 512 * 4, // Changed from 128 to 512
  .priority = (osPriority_t) osPriorityHigh,
};
const osThreadAttr_t communicationTask_attributes = {
  .name = "CommunicationTask",
  .stack_size = 512 * 4,
  .priority = (osPriority_t) osPriorityNormal,
};

volatile uint32_t sensorReleaseCount;
volatile uint32_t controlReleaseCount;
volatile uint32_t loggerReleaseCount;
volatile uint32_t communicationReleaseCount;

static void RunPeriodicTask(volatile uint32_t *releaseCount,
                            uint32_t period,
                            GPIO_TypeDef *gpioPort,
                            uint16_t gpioPin)
{
  uint32_t nextRelease = osKernelGetTickCount();

  for (;;)
  {
    nextRelease += period;
    (*releaseCount)++;
    HAL_GPIO_TogglePin(gpioPort, gpioPin);
    osDelayUntil(nextRelease);
  }
}

/* This function is called automatically by main.c before the scheduler starts */
void MX_FREERTOS_Init(void) {
  Trace_Init();
  TraceTransport_Init();
  osThreadNew(StartTask_Sensor, NULL, &sensorTask_attributes);
  osThreadNew(StartTask_Control, NULL, &controlTask_attributes);
  osThreadNew(StartTask_Logger, NULL, &loggerTask_attributes);
  osThreadNew(StartTask_Communication, NULL, &communicationTask_attributes);
}

void StartTask_Sensor(void *argument)
{
  (void)argument;
  RunPeriodicTask(&sensorReleaseCount, 100U, LD1_GPIO_Port, LD1_Pin);
}

void StartTask_Control(void *argument)
{
  (void)argument;
  RunPeriodicTask(&controlReleaseCount, 250U, LD2_GPIO_Port, LD2_Pin);
}

void StartTask_Logger(void *argument)
{
  (void)argument;
  RunPeriodicTask(&loggerReleaseCount, 500U, LD3_GPIO_Port, LD3_Pin);
}

void StartTask_Communication(void *argument)
{
  uint32_t nextRelease = osKernelGetTickCount();

  (void)argument;
  for (;;)
  {
    nextRelease += 10U;
    communicationReleaseCount++;
    TraceTransport_SendPending();
    osDelayUntil(nextRelease);
  }
}

/* USER CODE END Application */

