/**
 * @file    main.c
 * @brief   ADS1292 心电/呼吸 + 大彩 DN050 串口屏（心率呼吸监护 UI 工程版）
 *
 * 串口分配：
 *   USART1 PA9/PA10 115200 -> 串口屏（与体温工程同一条屏线，接线不变）
 *   ADS1292：PA0=PWDN PG15=START PA2=CS PA3=DRDY PA5/6/7=SPI1；PA1释放为输入
 *
 * 主循环处理界面与 CAN；实时采集独立在 DRDY 中断：
 *   1) queue_find_cmd  解析屏发来的整条指令（按钮/换页/RTC）
 *   2) HrPage_Task     每次主循环调用，界面按 1s/10s/60s/30s 分频；
 *      250Hz 原始帧由 DRDY 中断采集入队，FrameFeed 按采集时戳消费
 *
 * 时基分工（三个互不干扰）：
 *   SysTick 10ms -> 屏层 timer_tick_count（ulitity.c）
 *   TIM2 1ms     -> 算法 TimeBase_GetMs（timer.c）
 *   DWT CYCCNT   -> ADS1292 命令时序延时（systick.c）
 */
#include "hmi_driver.h"
#include "cmd_queue.h"
#include "cmd_process.h"
#include "hw_config.h"
#include "ulitity.h"
#include "systick.h"
#include "timer.h"
#include "spi.h"
#include "ads1292.h"
#include "bio_v2.h"
#include "hr_page.h"
#include "beep.h"
#include "canopen.h"

static uint8 cmd_buffer[CMD_MAX_SIZE];    // 屏指令缓存

int main(void)
{
    uint32 now_ms = 0;
    qsize  size;

    // ---- 初始化（顺序不能乱） ----
    Interrupts_Config();                  // NVIC 优先级分组（须最先，外设中断使能前定好优先级）
    systicket_init();                     // SysTick 10ms 节拍（屏层用）
    TimeBase_Init();                      // TIM2 1ms 时基（算法用）
    SysTick_Init();                       // DWT 微秒延时（ADS1292 时序用）
    UartInit(HMI_BAUDRATE);               // 串口屏 USART1 @115200
    queue_reset();                        // 清屏指令接收队列
    delay_ms(300);                        // 等屏自身初始化完再发指令
    SPI1_Init();                          // 必须先于 ADS1292_Init：ADS1292 通过 SPI1 通信
    ADS1292_Init();                       // 内部含 1s 基准建立延时
    BioV2_Init(TimeBase_GetMs());          // 独立新算法；不链接旧处理链
    BEEP_Init();                          // PF8 蜂鸣器 TIM13 PWM
    HrPage_Init();                        // 刷初始界面 + 读屏 RTC（放最后，依赖串口与采集均就绪）
    CanOpen_Init();                       // CAN1 1M + CANopen 从站(NodeID=3)

    while (1)
    {
        // 1. 屏 -> MCU：按钮/换页/RTC 等指令
        // 队列里没有整条指令时返回 0，不阻塞后续采集刷新
        size = queue_find_cmd(cmd_buffer, CMD_MAX_SIZE);
        if (size > 0)
        {
            if (cmd_buffer[1] == 0x07)    // 屏要求 MCU 软复位
            {
                __disable_fault_irq();
                NVIC_SystemReset();
            }
            ProcessMessage((PCTRL_MSG)cmd_buffer, size);
        }

        // 2. 采集 + 界面刷新（内部 1s/10s/60s/30s 分频）
        // 10ms 节拍数换算为毫秒时间戳，供 Task 内部分频判断
        now_ms = timer_tick_count * 10;
        HrPage_Task(now_ms);

        // 3. CANopen 从站：收 NMT/SDO，发心跳/TPDO1/EMCY
        CanOpen_Task(now_ms);
    }
}
