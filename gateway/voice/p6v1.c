#include "p6v1.h"
#include "tts_frame.h"
#include <string.h>
static uint64_t be64(const uint8_t *p) {
    uint64_t v=0; for(unsigned i=0;i<8;i++)v=(v<<8)|p[i]; return v;
}
void voice_session(VoiceGuard *g, uint64_t now, bool ready) {
    /* 重连保留RAM高水位；冷启动重新授时并设置新会话下界，拒绝旧消息跨重启播放。 */
    g->armed=false; g->session=ready && now>=g->high_time && now<=UINT64_MAX-1001u;
    if(g->session) {g->floor=now+1001u;g->high_time=now;}
}
void voice_arm(VoiceGuard *g, uint64_t now) {
    if(!g->session || now<g->high_time || now>UINT64_MAX-1001u)return;
    /* 本地单次许可晚于订阅及授时；未来1秒范围旧包也不能获得新的播放许可。 */
    g->floor=now+1001u;g->high_time=now;g->armed=true;
}
VoiceResult voice_check(VoiceGuard *g,const char *topic,size_t tn,unsigned qos,bool retain,
    const uint8_t *p,size_t n,uint64_t now,uint32_t tick,VoiceMessage *m) {
    if(!g->session || !g->armed)return VOICE_OFF;
    if(now<g->high_time) {g->session=g->armed=false;return VOICE_TIME;}
    g->high_time=now;
    if(!topic || tn!=sizeof(VOICE_TOPIC)-1 || memcmp(topic,VOICE_TOPIC,tn) || qos!=1 || retain)return VOICE_AUTHORITY;
    if(!p || n<=VOICE_HEADER || n>VOICE_WIRE_MAX)return VOICE_SIZE;
    size_t length=((size_t)p[52]<<8)|p[53];
    if(memcmp(p,"P6V1",4) || length!=n-VOICE_HEADER)return VOICE_SIZE;
    uint64_t issued=be64(p+4),expires=be64(p+12);
    /* 不接受未来时间，不用减法回绕绕过TTL；UTC回退会锁掉语音但不影响监护。 */
    if(issued<g->floor || issued>now || expires<=issued || expires-issued>15000u || now>=expires || expires-now<1000u)return VOICE_TIME;
    if(issued<=g->last_issued)return VOICE_REPLAY;
    for(unsigned i=0;i<g->count;i++)if(!memcmp(g->ids[i],p+20,16))return VOICE_REPLAY;
    if(g->submitted && ((uint32_t)(tick-g->last_tick)<5000u || issued-g->last_issued<5000u))return VOICE_RATE;
    /* 共用唯一UTF-8/控制字符校验，临时帧只在栈上；没有堆分配或回调后悬空引用。 */
    uint8_t checked[TTS_FRAME_MAX];
    if(!tts_text_frame(checked,sizeof(checked),p+VOICE_HEADER,length))return VOICE_TEXT;
    /* 网络协议沿用P6的BMP白名单；本地TTS驱动保留原有合法四字节UTF-8能力。 */
    for(size_t i=VOICE_HEADER;i<n;i++)if(p[i]>=0xf0u)return VOICE_TEXT;
    *m=(VoiceMessage){issued,expires,p+20,p+36,p+VOICE_HEADER,length};return VOICE_OK;
}
void voice_commit(VoiceGuard *g,const VoiceMessage *m,uint32_t tick) {
    memcpy(g->ids[g->cursor],m->turn,16);g->cursor=(g->cursor+1u)%8u;
    if(g->count<8)g->count++;
    g->last_issued=m->issued;g->last_tick=tick;g->submitted=true;g->armed=false;
}
