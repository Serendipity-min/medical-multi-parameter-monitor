#include "main.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_usart.h"
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>

static inline void secure_memzero(void *ptr, size_t len)
{
    volatile unsigned char *p = (volatile unsigned char *)ptr;
    while (len--)
        *p++ = 0;
    __asm__ __volatile__("" : : "r"(ptr) : "memory");
}

extern volatile uint32_t g_uptime_ms;
static char response[4096];
static uint32_t response_length;
static uint32_t receive_errors;
static bool overflow;

/* 只开放固定查询，不提供 AT 透传、联网、复位、恢复出厂或持久化写入。 */
static const char *queries[] = {"AT",           "AT+GMR",     "AT+CWMODE?",
                                "AT+SYSFLASH?", "AT+SYSRAM?", "AT+SYSSTORE?"};

static void console_write(const char *s)
{
    while (*s)
    {
        while (USART_GetFlagStatus(USART1, USART_FLAG_TXE) == RESET)
        {
        }
        USART_SendData(USART1, (uint8_t)*s++);
    }
}

static void init_uart(void)
{
    GPIO_InitTypeDef gpio;
    USART_InitTypeDef uart;
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA | RCC_AHB1Periph_GPIOB, ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART3, ENABLE);
    GPIO_StructInit(&gpio);
    gpio.GPIO_Pin = GPIO_Pin_9 | GPIO_Pin_10;
    gpio.GPIO_Mode = GPIO_Mode_AF;
    gpio.GPIO_OType = GPIO_OType_PP;
    gpio.GPIO_PuPd = GPIO_PuPd_UP;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource9, GPIO_AF_USART1);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource10, GPIO_AF_USART1);
    GPIO_Init(GPIOA, &gpio);
    gpio.GPIO_Pin = GPIO_Pin_10 | GPIO_Pin_11;
    GPIO_PinAFConfig(GPIOB, GPIO_PinSource10, GPIO_AF_USART3);
    GPIO_PinAFConfig(GPIOB, GPIO_PinSource11, GPIO_AF_USART3);
    GPIO_Init(GPIOB, &gpio);
    USART_StructInit(&uart);
    uart.USART_BaudRate = 115200;
    USART_Init(USART1, &uart);
    USART_Init(USART3, &uart);
    USART_Cmd(USART1, ENABLE);
    USART_Cmd(USART3, ENABLE);
}

static bool drain_esp(void)
{
    /* 按 SR→DR 顺序清除接收错误，并显式记录溢出，不能把残缺回复判为完整。 */
    uint32_t status = USART3->SR;
    if (!(status & (USART_SR_RXNE | USART_SR_ORE | USART_SR_FE | USART_SR_NE)))
        return false;
    uint8_t byte = (uint8_t)USART3->DR;
    if (status & (USART_SR_ORE | USART_SR_FE | USART_SR_NE))
        receive_errors++;
    if (status & USART_SR_RXNE)
    {
        if (response_length < sizeof(response) - 1U)
            response[response_length++] = (char)byte;
        else
            overflow = true;
        return true;
    }
    return false;
}

/* 单次固定查询清空上一轮状态，完整收集结束标记后同时检查接收错误和容量溢出。 */
static bool query(const char *command)
{
    char meta[128];
    response_length = 0;
    receive_errors = 0;
    overflow = false;
    (void)USART3->SR;
    (void)USART3->DR;
    console_write("\r\nBEGIN ");
    console_write(command);
    console_write("\r\n");
    /* 发送期间也接收回显，防止 ESP 开启 echo 时接收寄存器溢出。 */
    for (uint32_t i = 0; i < strlen(command) + 2U; ++i)
    {
        while (USART_GetFlagStatus(USART3, USART_FLAG_TXE) == RESET)
            (void)drain_esp();
        (void)drain_esp();
        USART_SendData(USART3, i < strlen(command) ? (uint8_t)command[i]
                                                   : (i == strlen(command) ? '\r' : '\n'));
    }
    uint32_t start = g_uptime_ms, last = start;
    while ((uint32_t)(g_uptime_ms - start) < 15000U)
    {
        if (drain_esp())
            last = g_uptime_ms;
        response[response_length] = '\0';
        /* 扫描结果可能分批返回，必须等终止标记，不能把短暂空闲当作结束。 */
        /* 先判断空闲再搜索终止标记，避免 HSI 16MHz 下反复扫描字符串导致 UART 溢出。 */
        if (response_length && (uint32_t)(g_uptime_ms - last) >= 100U &&
            (strstr(response, "\r\nOK\r\n") || strstr(response, "\r\nERROR\r\n")))
            break;
    }
    response[response_length] = '\0';
    console_write(response);
    (void)snprintf(meta, sizeof(meta), "\r\nEND bytes=%lu errors=%lu overflow=%u\r\n",
                   (unsigned long)response_length, (unsigned long)receive_errors,
                   overflow ? 1U : 0U);
    console_write(meta);
    return receive_errors == 0 && !overflow && strstr(response, "\r\nOK\r\n") != NULL;
}

int main(void)
{
    init_uart();
    if (SysTick_Config(SystemCoreClock / 1000U))
        while (1)
        {
        }
    console_write("ESP_NETWORK_QUERY_READY; probe or scan <ssid>\r\n");
    char line[80];
    uint32_t length = 0;
    bool discard = false;
    while (1)
    {
        if (USART_GetFlagStatus(USART1, USART_FLAG_RXNE) == RESET)
            continue;
        char c = (char)USART_ReceiveData(USART1);
        if (c == '\r')
            continue;
        if (c == '\n')
        {
            line[length] = '\0';
            if (!discard && strcmp(line, "probe") == 0)
            {
                for (uint32_t i = 0; i < sizeof(queries) / sizeof(queries[0]); ++i)
                    query(queries[i]);
                console_write("PROBE_DONE\r\n");
            }
            else if (!discard && strcmp(line, "station") == 0)
            {
                /* 当前已确认 AP 模式；先关闭持久化，再临时启用 STA 以查询目标 AP。 */
                if (query("AT+SYSSTORE=0"))
                    (void)query("AT+CWMODE=1");
                console_write("STATION_DONE\r\n");
            }
            else if (!discard && strcmp(line, "restore-mode") == 0)
            {
                /* 配套上位机仅在事先读到 MODE=2、SYSSTORE=1 时调用此恢复入口。 */
                if (query("AT+CWMODE=2"))
                    (void)query("AT+SYSSTORE=1");
                console_write("RESTORE_MODE_DONE\r\n");
            }
            else if (!discard && strncmp(line, "scan ", 5) == 0 && strlen(line + 5) <= 32U)
            {
                /* SSID 仅经串口进入 RAM；限制引号、反斜杠和控制字符，不能注入 AT 指令。 */
                bool safe = strlen(line + 5) > 0U;
                for (uint32_t i = 5; line[i]; ++i)
                {
                    if ((uint8_t)line[i] < 32U || line[i] == '"' || line[i] == '\\')
                        safe = false;
                }
                if (safe)
                {
                    char command[64];
                    (void)snprintf(command, sizeof(command), "AT+CWLAP=\"%.32s\"", line + 5);
                    query(command);
                    secure_memzero(command, sizeof(command));
                    console_write("SCAN_DONE\r\n");
                }
                else
                    console_write("INVALID_SSID\r\n");
            }
            else
                console_write("UNKNOWN_COMMAND\r\n");
            length = 0;
            discard = false;
        }
        else if (!discard && length < sizeof(line) - 1U)
            line[length++] = c;
        else
            discard = true; /* 超长行整体丢弃，不执行被截断后的命令。 */
    }
}
