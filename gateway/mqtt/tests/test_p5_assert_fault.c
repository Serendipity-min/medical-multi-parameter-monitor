/* 常规故障处置单测：用 longjmp 观测 noreturn 停机终点，不注入硬件故障。 */
#include <assert.h>
#include <setjmp.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern volatile uint32_t gateway_assert_latched;
extern void __assert_func(const char *, int, const char *, const char *) __attribute__((noreturn));
static jmp_buf stop;
static unsigned char captured[64];
static unsigned count, polls;
static int disabled, halted, unavailable;
int gateway_assert_tx_ready(void)
{
    assert(disabled);
    polls++;
    return !unavailable;
}
void gateway_assert_tx_write(unsigned char value)
{
    assert(disabled && count < sizeof(captured) - 1);
    captured[count++] = value;
}
void gateway_assert_disable_interrupts(void) { disabled = 1; }
void gateway_assert_halt(void) __attribute__((noreturn));
void gateway_assert_halt(void)
{
    halted = 1;
    longjmp(stop, 1);
}
static void invoke(void)
{
    if (!setjmp(stop))
        __assert_func("synthetic-file", 17, "synthetic-function", "synthetic-expression");
    assert(halted && gateway_assert_latched == 1);
}
int main(void)
{
    invoke();
    assert(!strcmp((const char *)captured, "GW ASSERT_FATAL\r\n"));
    puts("PASS assert_fixed_marker_then_halt");
    assert(!strstr((const char *)captured, "synthetic"));
    puts("PASS assert_input_strings_not_logged");
    assert(disabled && polls == count);
    puts("PASS assert_interrupts_disabled_before_uart");
    count = polls = 0; disabled = halted = 0; unavailable = 1;
    memset(captured, 0, sizeof(captured));
    invoke();
    assert(!count && polls == 8192);
    puts("PASS assert_unavailable_uart_has_bounded_attempt");
    return 0;
}
