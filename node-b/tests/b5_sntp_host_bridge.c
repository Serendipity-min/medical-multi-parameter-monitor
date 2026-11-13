#include "sntp_sample.h"
__declspec(dllexport) int b5_check(const unsigned char *packet,size_t length,
    const unsigned char *request,uint32_t rtt,uint32_t minimum,uint64_t *sample) {
    return sntp_sample(packet,length,request,rtt,minimum,sample);
}
