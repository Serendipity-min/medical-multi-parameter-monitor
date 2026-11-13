#include "gy641.h"
#include <assert.h>
#include <stdio.h>
static uint8_t example[12]={0xa4,3,7,7,0x62,0x0c,0xeb,0x0c,0x3f,0x0e,0x20,0x87};
static void frame(Gy641 *s,uint32_t now) {
    for(unsigned i=0;i<12;i++) assert(gy641_feed(s,example[i],now)==(i==11));
}
int main(void) {
    Gy641 s;uint16_t value;gy641_init(&s);assert(!gy641_object(&s,0,&value));
    frame(&s,100);assert(s.frames==1 && s.emissivity==98 && s.object_centi==3307);
    assert(s.ambient_centi==3135 && s.body_centi==3616);
    assert(gy641_object(&s,2600,&value) && value==3307);assert(!gy641_object(&s,2601,&value));
    example[11]^=1;for(unsigned i=0;i<12;i++)gy641_feed(&s,example[i],3000);
    assert(s.checksum_errors==1 && s.frames==1);example[11]^=1;
    for(unsigned i=0;i<4;i++)gy641_feed(&s,(uint8_t[]){0xa4,3,7,6}[i],3100);
    assert(s.header_errors==1);frame(&s,3200);assert(s.frames==2);
    for(unsigned i=0;i<6;i++)gy641_feed(&s,example[i],3300);
    for(unsigned i=6;i<12;i++)gy641_feed(&s,example[i],3301);
    assert(s.frames==3 && s.last_ms==3301);
    gy641_init(&s);frame(&s,0xfffffff0u);assert(gy641_object(&s,100,&value));
    s.object_centi=10000;assert(gy641_object(&s,100,&value) && value==10000);
    s.object_centi=10001;assert(!gy641_object(&s,100,&value));
    s.object_centi=0xffff;assert(!gy641_object(&s,100,&value));
    s.object_centi=0;assert(gy641_object(&s,100,&value) && !value);
    s.emissivity=0;assert(!gy641_object(&s,100,&value));
    puts("GY641_PASS vendor_12B_header07 checksum fragmented resync stale wrap object_only uncalibrated limits_no_sensor_writes");
    return 0;
}
