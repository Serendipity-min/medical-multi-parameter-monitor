#ifndef MPM_MMIO_MOCK_H
#define MPM_MMIO_MOCK_H
#include <stdint.h>
/* 只供普通Host编译的寄存器模型；不宣称它模拟了DMA仲裁、DAC模拟转换或实时中断。 */
typedef struct {volatile uint32_t AHB1ENR,APB1ENR,CFGR,AHB1RSTR;} MockRcc;
typedef struct {volatile uint32_t MODER,PUPDR;} MockGpio;
/* Host也用16位字段加16位保留空间，防止模型隐藏真实ARM寄存器类型差异。 */
typedef struct {
    volatile uint16_t CR1;uint16_t r1;volatile uint16_t CR2;uint16_t r2;
    volatile uint16_t PSC;uint16_t r3;volatile uint32_t ARR;
    volatile uint32_t CNT;volatile uint16_t EGR;uint16_t r6;
    volatile uint16_t SR;uint16_t r7;
} MockTim;
typedef struct {volatile uint32_t CR,DHR12R1,DHR12R2,SR,DOR1,DOR2;} MockDac;
typedef struct {volatile uint32_t CR,PAR,M0AR,NDTR,FCR;} MockStream;
typedef struct {volatile uint32_t HISR,HIFCR;} MockDma;
typedef struct {volatile uint32_t APB1FZ;} MockDebug;
extern MockRcc src_mock_rcc;extern MockGpio src_mock_gpio;extern MockTim src_mock_tim;
extern MockDac src_mock_dac;extern MockStream src_mock_stream;extern MockDma src_mock_dma;
extern MockDebug src_mock_debug;
extern uint32_t SystemCoreClock,src_mock_primask,src_mock_stuck,src_mock_reset_blocked;
extern uint32_t src_mock_ug_while_trigger,src_mock_irq_enables;
#define RCC (&src_mock_rcc)
#define GPIOA (&src_mock_gpio)
#define TIM6 (&src_mock_tim)
#define DAC (&src_mock_dac)
#define DMA1_Stream5 (&src_mock_stream)
#define DMA1 (&src_mock_dma)
#define DBGMCU (&src_mock_debug)
#define DMA1_Stream5_IRQn 16
#define TIM6_DAC_IRQn 54
uint32_t __get_PRIMASK(void);void __disable_irq(void);void __set_PRIMASK(uint32_t value);
void __DMB(void);void __DSB(void);void SystemCoreClockUpdate(void);
void NVIC_ClearPendingIRQ(int irq);void NVIC_SetPriority(int irq,uint32_t priority);void NVIC_EnableIRQ(int irq);
void SrcMock_Write(volatile uint32_t *address,uint32_t value);
void SrcMock_WriteTimer(volatile uint16_t *address,uint16_t value);
void SrcMock_Reset(void);uint32_t SrcMock_Trigger(void);
#endif
