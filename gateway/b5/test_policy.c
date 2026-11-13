/* 测试真实序列化/Router/策略；既不探测设备，也不把QoS0成功当Broker确认。 */
#include "b5_policy.h"
#include "../storage/router.h"
#include "core_mqtt_serializer.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
int b5_network_stopped(void) { return 0; }
int main(void) {
    assert(b5_identity_allowed("b5-c-isolated","b5-gateway"));
    assert(!b5_identity_allowed("synthetic-client","b5-gateway"));
    MpFrame f={0};f.node=2;f.stream=MP_ECG;f.rate=250;f.count=100;f.valid=true;
    f.timestamp=1800000000000ULL;f.epoch=UINT32_MAX;f.boot=UINT32_MAX;f.seq=UINT32_MAX;
    for(unsigned i=0;i<100;i++)f.values[i]=INT32_MIN;
    assert(b5_prepare_publish(&f,f.timestamp));char text[2048],topic[120];
    int n=mp_json(&f,text,sizeof(text));assert(n>0 && n<2048 && strstr(text,"\"MOCK\"") && strstr(text,"\"synthetic\":true"));
    assert(mp_topic(&f,topic,sizeof(topic)) && strstr(topic,"/GW-B5-001/"));
    MQTTPublishInfo_t message={0};message.qos=MQTTQoS0;message.pPayload=text;message.payloadLength=(size_t)n;
    message.pTopicName=topic;message.topicNameLength=(uint16_t)strlen(topic);
    size_t remaining,total;assert(MQTT_GetPublishPacketSize(&message,&remaining,&total)==MQTTSuccess && total<=2048);
    printf("WORST100_JSON=%d MQTT_PACKET=%lu\n",n,(unsigned long)total);
    f.stream=MP_HR;f.rate=0;f.count=1;f.values[0]=6000;f.valid=false;
    assert(mp_json(&f,text,sizeof(text)) && strstr(text,"\"value\":null"));
    f.valid=true;uint64_t stamp=f.timestamp;assert(b5_prepare_publish(&f,stamp+5001) && f.replay && f.timestamp==stamp);
    assert(mp_topic(&f,topic,sizeof(topic)) && strstr(topic,"/replay/"));
    f.replay=false;f.stream=MP_NODE_STATUS;assert(!b5_prepare_publish(&f,stamp+5001));
    f.timestamp=0;assert(!b5_prepare_publish(&f,stamp));
    MpRouter r;mp_router_init(&r);
    f.timestamp=stamp;f.stream=MP_HR;f.valid=true;
    for(unsigned i=0;i<1000;i++){f.seq=i;mp_router_put(&r,&f);}
    assert(r.cn==64 && r.dropped==936 && r.ln==0);
    mp_router_online(&r,true);assert(!mp_router_take(&r,&f,10000));
    f.seq=1001;mp_router_put(&r,&f);assert(mp_router_take(&r,&f,10000) && !f.replay);
    mp_router_ack(&r,&f,true);assert(mp_router_take(&r,&f,12000) && f.replay && f.timestamp==stamp);
    puts("POLICY_PASS identity MOCK units 2048B expiry bounded_cache reconnect_replay");return 0;
}
