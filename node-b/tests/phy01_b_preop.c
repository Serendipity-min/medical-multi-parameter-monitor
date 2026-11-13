/* 真实B生产者与CANopenNode：PREOP不发波形，BIO采样仍持续。 */
#include "CANopen.h"
#include "b_canopen_app.h"
#include "bio_v2.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
extern void b4_host_now(uint32_t);
extern void b4_host_wire(FILE *);
extern void b4_host_receive(uint32_t,uint8_t,const uint8_t *);
static void sync_time(uint32_t now) {
    uint64_t relative=1577836800000ULL+now-441763200000ULL;
    uint8_t data[6];CO_setUint32(data,relative%86400000u);CO_setUint16(data+4,relative/86400000u);
    b4_host_receive(0x100,6,data);
}
int main(void) {
    FILE *wire=tmpfile();assert(wire);b4_host_wire(wire);BioV2_Init(0);CanOpen_Init();
    unsigned seq=0;
    for(uint32_t now=0;now<8000;now++) {
        b4_host_now(now);
        if(now==1000 || now==6000) {
            uint8_t nmt[2]={now==1000?128:1,2};b4_host_receive(0,2,nmt);
        }
        if(now%1000==0)sync_time(now);
        if(now%4==0) {
            BioV2_Process(200000+(int)(now%1000)*10,640000,now,++seq,0);
            BCan_Sample(now,seq,0);
        }
        CanOpen_Task(now);
    }
    assert(g_bio_v2.samples==2000 && !g_bio_v2.discontinuities && !g_b_can.comm_reset);
    rewind(wire);unsigned at,id,n,preop_hb=0,before=0,after=0;
    while(fscanf(wire,"%u %u %u",&at,&id,&n)==3) {
        unsigned data[8]={0};for(unsigned i=0;i<n;i++)assert(fscanf(wire,"%u",&data[i])==1);
        if(1000<=at && at<6000) {
            assert(id!=0x182 && id!=0x282 && id!=0x382 && id!=0x482 && id!=0x682);
            if(id==0x702 && n==1 && data[0]==127)preop_hb++;
        }
        if(id==0x182 && at<1000)before++;
        if(id==0x182 && at>=6000)after++;
    }
    assert(preop_hb>=8 && before>=240 && after>=490);fclose(wire);
    puts("B_PREOP_PDO_SUPPRESSED_BIO_CONTINUES_AND_OP_RECOVERS_PASS");return 0;
}
