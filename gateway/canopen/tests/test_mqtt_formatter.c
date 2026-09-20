#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "MQTTFormat.h"

int main(void)
{
    MQTTPacket_connectData options = MQTTPacket_connectData_initializer;
    char output[256];
    char short_output[8];
    const char synthetic_password[] = "fixed-unit-test-value";

    /* 只检查已知 CONNECT formatter 修补和脱敏；样本是固定假值。 */
    options.clientID.lenstring.data = "host-test";
    options.clientID.lenstring.len = 9;
    options.password.lenstring.data = (char *)synthetic_password;
    options.password.lenstring.len = (int)strlen(synthetic_password);
    int result = MQTTStringFormat_connect(output, sizeof(output), &options);
    assert(result >= 0 && result < (int)sizeof(output));
    assert(strstr(output, "[REDACTED]") != NULL);
    assert(strstr(output, synthetic_password) == NULL);

    /* 使用已有小缓冲区问题的固定回归，末尾必须正确 NUL 终止。 */
    memset(short_output, 0xa5, sizeof(short_output));
    result = MQTTStringFormat_connect(short_output, sizeof(short_output), &options);
    assert(result >= 0 && result < (int)sizeof(short_output));
    assert(short_output[sizeof(short_output) - 1] == '\0');

    /* C 字符串形式也不得输出密码；当前 formatter 对这种形式省略该字段。 */
    options.password.lenstring.data = NULL;
    options.password.lenstring.len = 0;
    options.password.cstring = (char *)synthetic_password;
    result = MQTTStringFormat_connect(output, sizeof(output), &options);
    assert(result >= 0 && result < (int)sizeof(output));
    assert(strstr(output, synthetic_password) == NULL);
    puts("PASS: 3 fixed CONNECT formatter cases");
    return 0;
}
