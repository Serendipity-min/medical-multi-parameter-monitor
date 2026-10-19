/* 版本提取仅允许有界数字串，厂商扩展/地址/设备标识不能进入公开诊断。 */
#include "at_version.h"
#include <assert.h>
#include <string.h>
int main(void) {
    char out[32];
    assert(gateway_at_version("AT version:2.2.0.0(test extension)\r\nOK\r\n",out));
    assert(strcmp(out,"2.2.0.0")==0);
    assert(!gateway_at_version("SDK version:3.3\r\nOK\r\n",out));
    assert(!gateway_at_version("AT version:.bad",out));
    assert(!gateway_at_version("AT version:123456789012345678901234567890123456",out));
    assert(!gateway_at_version("AT version:\r\n",out));
    return 0;
}
