#include "stm32f4xx.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_usart.h"
#include "mic_format.h"
#include "mic_api.h"
#include <stdio.h>
#include <string.h>

extern int physical_clock_ready(void);
#ifdef MIC_SHARED_RUNTIME
extern volatile uint32_t g_uptime_ms;
#define uptime g_uptime_ms
#elif defined(MIC_NETWORK_BENCH)
volatile uint32_t g_uptime_ms;
#define uptime g_uptime_ms
#else
static volatile uint32_t uptime;
#endif
static volatile uint16_t dma_words[2][MIC_BLOCK_WORDS];
static uint16_t staging[MIC_BLOCK_WORDS], raw_head[64];
#ifdef MIC_SHARED_RUNTIME
/* CCM仅供CPU访问，I²S DMA仍写普通SRAM的dma_words。录满前不发布PCM。 */
static int16_t pcm[MIC_SAMPLES] __attribute__((section(".ccm_audio"), aligned(8)));
#else
static int16_t pcm[MIC_SAMPLES];
#endif
static volatile uint32_t irq_cycles[300], blocks, dma_errors, overruns;
static uint16_t recorded_blocks[200];
static uint32_t decode_cycles_max;
static volatile int pending = -1;
static unsigned frames, state; /* 0=空闲，1=采集，2=完成，3=错误 */
static uint32_t began_at;
static uint32_t left_abs, right_abs, right_nonzero, zero24, clip24, low24, fault_flags;

#ifndef MIC_SHARED_RUNTIME
void SysTick_Handler(void) { ++uptime; }
#endif

void DMA1_Stream0_IRQHandler(void) {
    uint32_t flags = DMA1->LISR;
    DMA1->LIFCR = 0x3du;
    if (flags & 0x0du) ++dma_errors;
    if (flags & (1u << 5)) {
        if (blocks < 300u) irq_cycles[blocks] = DWT->CYCCNT;
        ++blocks;
        if (pending != -1) ++overruns;
        pending = (DMA1_Stream0->CR & DMA_SxCR_CT) ? 0 : 1;
    }
}

static void put(uint8_t c) {
    while (!(USART1->SR & USART_SR_TXE)) {}
    USART1->DR = c;
}
static void text(const char *s) { while (*s) put((uint8_t)*s++); }
static void number(uint32_t n) { char b[16]; snprintf(b, sizeof b, "%lu", (unsigned long)n); text(b); }
static void field(const char *name, uint32_t n) { text(name); number(n); }

static void stop(void) {
    __disable_irq();
    SPI3->CR2 = 0;
    DMA1_Stream0->CR &= ~DMA_SxCR_EN;
    SPI3->I2SCFGR &= ~SPI_I2SCFGR_I2SE;
    DMA1->LIFCR = 0x3du; NVIC_ClearPendingIRQ(DMA1_Stream0_IRQn);
    __enable_irq();
    GPIOF->BSRRL = GPIO_Pin_9;
}

static int initialize(void) {
    GPIO_InitTypeDef gpio;
#ifndef MIC_SHARED_RUNTIME
    USART_InitTypeDef uart;
#endif
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA | RCC_AHB1Periph_GPIOC |
                         RCC_AHB1Periph_GPIOF | RCC_AHB1Periph_DMA1, ENABLE);
#ifndef MIC_SHARED_RUNTIME
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);
#endif
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_SPI3, ENABLE);
    GPIO_StructInit(&gpio); gpio.GPIO_Mode = GPIO_Mode_AF; gpio.GPIO_Speed = GPIO_Speed_25MHz;
#ifndef MIC_SHARED_RUNTIME
    gpio.GPIO_Pin = GPIO_Pin_9 | GPIO_Pin_10;
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource9, GPIO_AF_USART1);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource10, GPIO_AF_USART1); GPIO_Init(GPIOA, &gpio);
    USART_StructInit(&uart); uart.USART_BaudRate = 115200; USART_Init(USART1, &uart); USART_Cmd(USART1, ENABLE);
#endif
    gpio.GPIO_Pin = GPIO_Pin_4; GPIO_PinAFConfig(GPIOA, GPIO_PinSource4, GPIO_AF_SPI3); GPIO_Init(GPIOA, &gpio);
    gpio.GPIO_Pin = GPIO_Pin_10; GPIO_PinAFConfig(GPIOC, GPIO_PinSource10, GPIO_AF_SPI3); GPIO_Init(GPIOC, &gpio);
    gpio.GPIO_Pin = GPIO_Pin_12; gpio.GPIO_PuPd = GPIO_PuPd_DOWN;
    GPIO_PinAFConfig(GPIOC, GPIO_PinSource12, GPIO_AF_SPI3); GPIO_Init(GPIOC, &gpio);
    gpio.GPIO_Pin = GPIO_Pin_9; gpio.GPIO_Mode = GPIO_Mode_OUT; gpio.GPIO_PuPd = GPIO_PuPd_NOPULL;
    GPIO_Init(GPIOF, &gpio); GPIOF->BSRRL = GPIO_Pin_9;
    /* 只设置独立音频PLL；SYSCLK保持原8MHz HSE，不复位全局RCC。 */
    if (!physical_clock_ready() || (RCC->CR & (RCC_CR_PLLON | RCC_CR_PLLI2SON))) return 0;
    RCC->PLLCFGR = (RCC->PLLCFGR & ~RCC_PLLCFGR_PLLM) | 8u | RCC_PLLCFGR_PLLSRC_HSE;
    RCC->PLLI2SCFGR = (256u << 6) | (5u << 28);
    RCC->CFGR &= ~RCC_CFGR_I2SSRC;
    RCC->CR |= RCC_CR_PLLI2SON;
    unsigned budget = 1000000u;
    while (!(RCC->CR & RCC_CR_PLLI2SRDY)) if (!--budget) return 0;
    /* 51.2MHz / (64 * (2*25)) = 16kHz；24bit/32slot，Philips，Master Receive。 */
    SPI3->I2SPR = 25u;
    SPI3->I2SCFGR = SPI_I2SCFGR_I2SMOD | SPI_I2SCFGR_I2SCFG | SPI_I2SCFGR_DATLEN_0 | SPI_I2SCFGR_CHLEN;
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk; DWT->CYCCNT = 0; DWT->CTRL |= 1u;
#ifdef MIC_SHARED_RUNTIME
    /* 共享入口不重配SysTick/控制台；音频IRQ低于CAN的抢占级3。 */
    NVIC_SetPriority(DMA1_Stream0_IRQn, 8);
#else
    if (SysTick_Config(SystemCoreClock / 1000u)) return 0;
    NVIC_SetPriority(DMA1_Stream0_IRQn, 2);
#endif
    NVIC_EnableIRQ(DMA1_Stream0_IRQn);
    return 1;
}

static void start(void) {
    began_at = uptime;
    frames = state = left_abs = right_abs = right_nonzero = zero24 = clip24 = low24 = 0;
    fault_flags = 0;
    decode_cycles_max = 0;
    blocks = dma_errors = overruns = 0; pending = -1;
    memset(raw_head, 0, sizeof raw_head);
    DMA1_Stream0->CR = 0; DMA1->LIFCR = 0x3du;
    DMA1_Stream0->PAR = (uint32_t)&SPI3->DR;
    DMA1_Stream0->M0AR = (uint32_t)dma_words[0]; DMA1_Stream0->M1AR = (uint32_t)dma_words[1];
    DMA1_Stream0->NDTR = MIC_BLOCK_WORDS;
    DMA1_Stream0->FCR = DMA_SxFCR_FEIE;
    DMA1_Stream0->CR = DMA_SxCR_DBM | DMA_SxCR_CIRC | DMA_SxCR_MINC |
        DMA_SxCR_PSIZE_0 | DMA_SxCR_MSIZE_0 | DMA_SxCR_PL_1 |
        DMA_SxCR_TCIE | DMA_SxCR_TEIE | DMA_SxCR_DMEIE;
    (void)SPI3->DR; (void)SPI3->SR;
    state = 1;
#ifdef MP_ABC_APPLIANCE
    GPIOF->BSRRL = GPIO_Pin_9;
#else
    GPIOF->BSRRH = GPIO_Pin_9;
#endif
    DMA1_Stream0->CR |= DMA_SxCR_EN; SPI3->CR2 = SPI_CR2_RXDMAEN;
    SPI3->I2SCFGR |= SPI_I2SCFGR_I2SE;
}

static void consume(void) {
    uint32_t decode_began = DWT->CYCCNT;
    __disable_irq(); int index = pending; uint32_t generation = blocks; __enable_irq();
    if (index < 0) return;
    if (((DMA1_Stream0->CR & DMA_SxCR_CT) ? 1 : 0) == index) { ++overruns; return; }
    for (unsigned i = 0; i < MIC_BLOCK_WORDS; ++i) staging[i] = dma_words[index][i];
    __disable_irq();
    if (generation != blocks || ((DMA1_Stream0->CR & DMA_SxCR_CT) ? 1 : 0) == index) ++overruns;
    pending = -1; __enable_irq();
    if (overruns || dma_errors || generation <= 50u) return;
#ifdef MP_ABC_APPLIANCE
    /* 预热期间不亮录音灯，灯亮后才开始保留PCM。 */
    if(!frames)GPIOF->BSRRH = GPIO_Pin_9;
#endif
    if (frames / MIC_BLOCK_FRAMES < 200u) recorded_blocks[frames / MIC_BLOCK_FRAMES] = (uint16_t)generation;
    for (unsigned i = 0; i < MIC_BLOCK_FRAMES && frames < MIC_SAMPLES; ++i) {
        const uint16_t *v = staging + 4u * i;
        int32_t l = mic_sample24(v[0], v[1]);
        int16_t s = mic_pcm16(v[0], v[1]), r = mic_pcm16(v[2], v[3]);
        if (frames < 16u) memcpy(raw_head + frames * 4u, v, 8);
        pcm[frames++] = s;
        left_abs += s < 0 ? -(int32_t)s : s; right_abs += r < 0 ? -(int32_t)r : r;
        right_nonzero += mic_sample24(v[2], v[3]) != 0; zero24 += l == 0;
        clip24 += l >= 8388352 || l <= -8388352; low24 += (v[1] & 0xff00u) != 0;
    }
    uint32_t duration = DWT->CYCCNT - decode_began;
    if (duration > decode_cycles_max) decode_cycles_max = duration;
}

static void dump(void) {
    field("{\"state\":", state); field(",\"frames\":", frames); field(",\"rate\":", MIC_RATE);
    field(",\"bytes\":", frames * 2u); field(",\"crc32\":", mic_crc32(pcm, frames * 2u));
    field(",\"blocks\":", blocks); field(",\"dma_errors\":", dma_errors); field(",\"overruns\":", overruns);
    field(",\"fault_flags\":", fault_flags);
    field(",\"decode_cycles_max\":", decode_cycles_max);
    field(",\"left_abs\":", left_abs); field(",\"right_abs\":", right_abs); field(",\"right_nonzero\":", right_nonzero);
    field(",\"zero24\":", zero24); field(",\"clip24\":", clip24); field(",\"low24_nonzero\":", low24);
    field(",\"cpu_hz\":", SystemCoreClock); field(",\"PLLCFGR\":", RCC->PLLCFGR);
    field(",\"PLLI2SCFGR\":", RCC->PLLI2SCFGR); field(",\"I2SCFGR\":", SPI3->I2SCFGR);
    field(",\"I2SPR\":", SPI3->I2SPR); text(",\"raw_head\":[");
    for (unsigned i = 0; i < 64u; ++i) { if (i) put(','); number(raw_head[i]); }
    text("],\"irq_cycles\":[");
    for (unsigned i = 0; i < blocks && i < 300u; ++i) { if (i) put(','); number(irq_cycles[i]); }
    text("],\"recorded_blocks\":[");
    for (unsigned i = 0; i < frames / MIC_BLOCK_FRAMES; ++i) { if (i) put(','); number(recorded_blocks[i]); }
    text("]}\r\n");
    const uint8_t *p = (const uint8_t *)pcm;
    for (unsigned i = 0; i < frames * 2u; ++i) put(p[i]);
    text("\r\nMIC_END\r\n");
}

int mic_initialize(void) { return initialize(); }
void mic_record_begin(void) { start(); }
unsigned mic_record_state(void) { return state; }
const int16_t *mic_record_pcm(unsigned *count) { *count = frames; return pcm; }
void mic_record_export(void) { dump(); }
void mic_diagnostics(MicDiag *d) {
    *d = (MicDiag){frames, blocks, dma_errors, overruns, decode_cycles_max};
}
void mic_record_cancel(void) { stop(); fault_flags |= 16u; state = 3; text("MIC_OWNER_STOP\r\n"); }
void mic_record_poll(void) {
    if (state == 1) {
            consume();
            fault_flags = (dma_errors ? 1u : 0u) | (overruns ? 2u : 0u) |
                ((SPI3->SR & SPI_SR_OVR) ? 4u : 0u) | ((uptime - began_at > 3500u) ? 8u : 0u);
            if (fault_flags) {
                stop(); state = 3; text("MIC_CAPTURE_ERROR\r\n");
            } else if (frames == MIC_SAMPLES) { stop(); state = 2; text("MIC_DONE\r\n"); }
    }
}

void mic_record_finish(void) {
    mic_record_poll();
    if(state==1){stop();state=2;}
}

#ifndef MIC_NETWORK_BENCH
int main(void) {
    if (!initialize()) { text("MIC_CLOCK_FAIL\r\n"); for (;;) {} }
    text("MIC_BENCH_READY PA4_PC10_PC12 16000 S24_32 LEFT; R=record D=dump S=stop\r\n");
    for (;;) {
        mic_record_poll();
        if (USART1->SR & USART_SR_RXNE) {
            uint8_t c = (uint8_t)USART1->DR;
            if (c == 'S') mic_record_cancel();
            else if (c == 'R' && state != 1) { text("MIC_RECORDING\r\n"); start(); }
            else if (c == 'D' && state != 1) dump();
            else if (c == 'I' && state != 1) text("MIC_BENCH_ID PA4_PC10_PC12 16000 S24_32 LEFT\r\n");
        }
    }
}
#endif
