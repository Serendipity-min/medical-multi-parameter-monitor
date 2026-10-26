/* 真实驱动调用的管理门禁：健康的未接A口不能重开隔离台架协议。 */
#include "b4_resources.h"
#include <assert.h>
int main(void) {
    assert(!b4_hw_protocol_link_up(0,0));
    assert(!b4_hw_protocol_link_up(1,0));
    assert(b4_hw_protocol_link_up(1,1));
    assert(!b4_hw_protocol_link_up(2,1));
#if defined(B4_CAPTURE_SERIAL)
    assert(!b4_hw_protocol_link_up(0,1));
#else
    assert(b4_hw_protocol_link_up(0,1));
#endif
    return 0;
}
