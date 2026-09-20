/* 跨语言边界夹具：使用真实 RPDO 数据，由 Python Backend 独立解析。 */
#include "mp_adapter.h"
#include <assert.h>
#include <stdio.h>
static MpStack s;
static MpAdapter a;
static MpRouter r;

int main(void)
{
    assert(!mp_stack_init(&s, 1790000000));
    mp_adapter_init(&a);
    mp_router_init(&r);
    mp_router_online(&r, true);
    for (unsigned i = 0; i < 6100; i++)
    {
        mp_stack_tick(&s);
        mp_adapter_poll(&a, &s, &r);
        MpFrame f;
        while (mp_router_take(&r, &f, s.milliseconds))
        {
            char topic[128], body[2300];
            assert(mp_topic(&f, topic, sizeof(topic)));
            assert(mp_json(&f, body, sizeof(body)));
            printf("%s\t%s\n", topic, body);
            mp_router_ack(&r, &f, true);
        }
    }
    mp_stack_close(&s);
    return 0;
}
