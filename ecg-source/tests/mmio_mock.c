#include "mmio_mock.h"
#include "source_driver.h"
#include <string.h>
MockRcc src_mock_rcc;MockGpio src_mock_gpio;MockTim src_mock_tim;MockDac src_mock_dac;
MockStream src_mock_stream;MockDma src_mock_dma;MockDebug src_mock_debug;
uint32_t SystemCoreClock,src_mock_primask,src_mock_stuck,src_mock_reset_blocked;
uint32_t src_mock_ug_while_trigger,src_mock_irq_enables;
static uint32_t cursor;
uint32_t __get_PRIMASK(void){return src_mock_primask;}
void __disable_irq(void){src_mock_primask=1;}
void __set_PRIMASK(uint32_t value){src_mock_primask=value;}
void __DMB(void){}void __DSB(void){}void SystemCoreClockUpdate(void){}
void NVIC_ClearPendingIRQ(int irq){(void)irq;}
void NVIC_SetPriority(int irq,uint32_t priority){(void)irq;(void)priority;}
void NVIC_EnableIRQ(int irq){(void)irq;src_mock_irq_enables++;}
void SrcMock_Reset(void)
{
    memset(&src_mock_rcc,0,sizeof(src_mock_rcc));memset(&src_mock_gpio,0,sizeof(src_mock_gpio));
    memset(&src_mock_tim,0,sizeof(src_mock_tim));memset(&src_mock_dac,0,sizeof(src_mock_dac));
    memset(&src_mock_stream,0,sizeof(src_mock_stream));memset(&src_mock_dma,0,sizeof(src_mock_dma));
    memset(&src_mock_debug,0,sizeof(src_mock_debug));
    SystemCoreClock=168000000;src_mock_rcc.CFGR=(5u<<10)|8u;
    src_mock_primask=src_mock_stuck=src_mock_reset_blocked=0;
    src_mock_ug_while_trigger=src_mock_irq_enables=cursor=0;
}
void SrcMock_Write(volatile uint32_t *address,uint32_t value)
{
    /* 复刻所需的W1C/停用/复位语义；模型强制停用失败用来验证有界故障分支。 */
    if(address==&DMA1_Stream5->CR && src_mock_stuck && (DMA1_Stream5->CR&1u) && !(value&1u))value|=1u;
    if(address==&DMA1_Stream5->NDTR)cursor=0;
    if(address==&DMA1->HIFCR)DMA1->HISR&=~value;
    if(address==&DAC->SR){DAC->SR&=~value;return;}
    if(address==&RCC->AHB1RSTR && value&(1u<<21) && !src_mock_reset_blocked)
        memset(&src_mock_stream,0,sizeof(src_mock_stream));
    *address=value;
    if(address==&DAC->DHR12R1 && !(DAC->CR&(1u<<2)))DAC->DOR1=value;
    if(address==&DAC->DHR12R2)DAC->DOR2=value;
}
void SrcMock_WriteTimer(volatile uint16_t *address,uint16_t value)
{
    if(address==&TIM6->EGR && value&1u && DAC->CR&(1u<<2))src_mock_ug_while_trigger++;
    *address=value;
}
uint32_t SrcMock_Trigger(void)
{
    uint32_t result;
    if(!(TIM6->CR1&1u) || !(DAC->CR&1u) || !(DAC->CR&(1u<<2)))return 0xffffffffu;
    result=DAC->DHR12R1;DAC->DOR1=result;
    /* 软件模型按“输出预装码→DMA补下点”的顺序，不从M0AR截断的Host指针取内存。 */
    if((DAC->CR&(1u<<12)) && (DMA1_Stream5->CR&1u)) {
        DAC->DHR12R1=g_source_dma_buffer[cursor++];
        if(cursor==g_source_diag.table_length) {
            cursor=0;DMA1->HISR|=1u<<11;DMA1_Stream5_IRQHandler();
        }
    }
    return result;
}
