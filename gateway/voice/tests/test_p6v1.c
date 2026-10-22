#include "p6v1.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned checks;
#define CHECK(x) do{checks++;assert(x);}while(0)
static void put64(uint8_t *p,uint64_t v){for(unsigned i=0;i<8;i++){p[7-i]=(uint8_t)v;v>>=8;}}
static void prepare(VoiceGuard *g,uint8_t *p){memset(g,0,sizeof(*g));voice_session(g,100000,true);voice_arm(g,100000);
    memset(p,0,VOICE_WIRE_MAX);memcpy(p,"P6V1",4);put64(p+4,102000);put64(p+12,117000);p[20]=1;p[36]=2;p[53]=3;memcpy(p+54,"abc",3);}
static VoiceResult test(VoiceGuard *g,uint8_t *p,size_t n,uint64_t now,uint32_t tick,VoiceMessage *m){return voice_check(g,VOICE_TOPIC,sizeof(VOICE_TOPIC)-1,1,false,p,n,now,tick,m);}
int main(void){VoiceGuard g;VoiceMessage m;uint8_t p[VOICE_WIRE_MAX];
    prepare(&g,p);CHECK(test(&g,p,57,102000,2000,&m)==VOICE_OK);voice_commit(&g,&m,2000);
    CHECK(test(&g,p,57,102001,2001,&m)==VOICE_OFF);voice_arm(&g,102001);
    CHECK(test(&g,p,57,103100,3100,&m)==VOICE_TIME);
    prepare(&g,p);CHECK(voice_check(&g,"x",1,1,false,p,57,102000,2000,&m)==VOICE_AUTHORITY);
    CHECK(voice_check(&g,VOICE_TOPIC,sizeof(VOICE_TOPIC)-1,0,false,p,57,102000,2000,&m)==VOICE_AUTHORITY);
    CHECK(voice_check(&g,VOICE_TOPIC,sizeof(VOICE_TOPIC)-1,1,true,p,57,102000,2000,&m)==VOICE_AUTHORITY);
    for(size_t n=0;n<57;n++){prepare(&g,p);CHECK(test(&g,p,n,102000,2000,&m)==VOICE_SIZE);}
    prepare(&g,p);p[0]='X';CHECK(test(&g,p,57,102000,2000,&m)==VOICE_SIZE);
    prepare(&g,p);put64(p+12,117001);CHECK(test(&g,p,57,102000,2000,&m)==VOICE_TIME);
    prepare(&g,p);CHECK(test(&g,p,57,117000,2000,&m)==VOICE_TIME);
    prepare(&g,p);CHECK(test(&g,p,57,101999,2000,&m)==VOICE_TIME);
    prepare(&g,p);put64(p+12,UINT64_MAX);CHECK(test(&g,p,57,102000,2000,&m)==VOICE_TIME);
    const uint8_t bad[][4]={{0xc0,0xaf,0},{0xed,0xa0,0x80},{0xf4,0x90,0x80,0x80},{0xe2,0x80,0x8b},{0xef,0xbb,0xbf},{0xef,0xb7,0x90},{0xef,0xbf,0xbe},{'[','v',']'},{'a',0,'b'}};
    for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++){prepare(&g,p);size_t n=i==2?4:3;p[53]=(uint8_t)n;memcpy(p+54,bad[i],n);CHECK(test(&g,p,54+n,102000,2000,&m)==VOICE_TEXT);}
    prepare(&g,p);p[53]=240;memset(p+54,'x',240);CHECK(test(&g,p,294,102000,2000,&m)==VOICE_OK);
    voice_commit(&g,&m,0xffffff00u);voice_session(&g,103000,true);voice_arm(&g,103000);
    put64(p+4,107000);put64(p+12,122000);CHECK(test(&g,p,294,107000,5000,&m)==VOICE_REPLAY);
    p[20]=3;CHECK(test(&g,p,294,107000,5000,&m)==VOICE_OK);
    voice_commit(&g,&m,5000);voice_session(&g,108000,true);voice_arm(&g,108000);p[20]=4;put64(p+4,110000);put64(p+12,125000);
    CHECK(test(&g,p,294,110000,7000,&m)==VOICE_RATE);
    CHECK(test(&g,p,294,109999,7000,&m)==VOICE_TIME);CHECK(!g.session);
    /* 模拟正常重启丢失RAM：新会话下界仍使之前有效TTL内的旧消息失效。 */
    memset(&g,0,sizeof(g));voice_session(&g,111000,true);voice_arm(&g,111000);
    CHECK(test(&g,p,294,112100,100,&m)==VOICE_TIME);
    printf("P6V1 negative checks=%u PASS; digest=fact_binding_not_authentication\n",checks);
}
