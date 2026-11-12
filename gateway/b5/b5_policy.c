#include "b5_policy.h"
#include <string.h>
int b5_identity_allowed(const char *client, const char *user) {
    return !strcmp(client, B5_CLIENT_ID) && !strcmp(user, B5_USERNAME);
}
int b5_prepare_publish(MpFrame *f, uint64_t now) {
#ifdef MP_FORMAL_CLOUD
    f->synthetic = f->stream >= MP_NODE_STATUS;
#else
    f->synthetic = true;
#endif
    if (f->timestamp > now + 1000u || !f->timestamp) return 0;
    if (now > f->timestamp && now - f->timestamp > 5000u) {
        if (f->stream == MP_GATEWAY_STATUS || f->stream == MP_NODE_STATUS) return 0;
        f->replay = true;
    }
    return 1;
}
