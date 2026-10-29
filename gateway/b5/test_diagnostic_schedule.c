/* 编译实际网络主程序的诊断调度；只替换控制台和可用空档，不连接设备。 */
static int unused_network_main(void);
#define main unused_network_main
#ifndef DIAGNOSTIC_MAIN_SOURCE
#define DIAGNOSTIC_MAIN_SOURCE "network_main.c"
#endif
#include DIAGNOSTIC_MAIN_SOURCE
#undef main
#include <assert.h>
#include <stdlib.h>

volatile uint32_t g_uptime_ms;
volatile B4HwDiag b4_hw_diag[2];
static unsigned counts[2], lines, temperature;
static uint32_t last[2], gap[2], base_tick, console_ms, evaluation_start=45000;
static int available=1;
int platform_console_busy(void){return 0;}
int platform_at_synchronized(void){return available;}
uint32_t platform_uart_errors_total(void){return 0;}
void platform_io_snapshot(EspIoMetrics *out){memset(out,0,sizeof(*out));}
void gateway_mqtt_metrics(GatewayMqttMetrics *out){memset(out,0,sizeof(*out));}
void console(const char *line){
    uint32_t at=g_uptime_ms-base_tick;
    if(!strncmp(line,"B5 TEMP_ENTRY ",14) && at>=evaluation_start && at<evaluation_start+300000u)temperature++;
    for(unsigned i=0;i<2;i++){
        const char *prefix=i?"B5 QUEUE ":"B5 DIAG ";
        if(strncmp(line,prefix,strlen(prefix)))continue;
        if(counts[i] && at-last[i]>gap[i])gap[i]=at-last[i];
        last[i]=at;
        if(at>=evaluation_start && at<evaluation_start+300000u)counts[i]++;
    }
    unsigned duration=(unsigned)((strlen(line)*87u+999u)/1000u);
    if(duration>console_ms)console_ms=duration;
    g_uptime_ms+=duration;
    lines++;
}
int main(int argc,char **argv){
    unsigned mode=argc>1?(unsigned)atoi(argv[1]):0;
    base_tick=mode==1?0xffff0000u:0;
    g_uptime_ms=base_tick;
    FILE *replay=mode==3 && argc==4?fopen(argv[2],"r"):NULL;
    if(mode==3){assert(replay);evaluation_start=(uint32_t)strtoul(argv[3],NULL,10);}
    uint32_t source_at=0;
    for(uint32_t at=0;mode==3?fscanf(replay,"%u",&at)==1:at<360000;at+=100){
        g_uptime_ms=base_tick+at;
        if(mode==3 && !source_at)source_at=at;
        while(gateway.router.temp_written<(at-source_at)/1000u){
            MpRouter *r=&gateway.router;
            if(r->temp_written-r->temp_reported>=8){r->temp_reported++;r->temp_trace_lost++;}
            r->temp_entry[r->temp_written++%8]=(B5TempEntry){0};
        }
        publisher.pending=mode==3?false:at%1000u<550u;
        publisher.deferred=false;
        available=mode==3 || at%1000u>=600u;
        if(mode==2 && (at>=99750u && at<102266u))publisher.pending=true;
        unsigned before=lines;
        diagnostic_idle();
        assert(lines-before<=1);
        if(publisher.pending || !available)assert(lines==before);
    }
    if(replay)fclose(replay);
    printf("REAL_NETWORK_MAIN_DIAGNOSTICS diag=%u queue=%u max_gap=%lu/%lu console_ms=%lu temp=%u lost=%lu mode=%u\n",
        counts[0],counts[1],(unsigned long)gap[0],(unsigned long)gap[1],(unsigned long)console_ms,temperature,(unsigned long)gateway.router.temp_trace_lost,mode);
    fflush(stdout);
#ifdef EXPECT_DIAGNOSTIC_DEFECT
    assert(counts[0]<58 || counts[1]<58 || gap[0]>8000 || gap[1]>8000);
#else
    assert(counts[0]>=58 && counts[1]>=58 && gap[0]<=8000 && gap[1]<=8000);
    assert(temperature>=295 && !gateway.router.temp_trace_lost);
#endif
    assert(console_ms<=27);
    return 0;
}
