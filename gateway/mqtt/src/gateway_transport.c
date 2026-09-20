/* 复用第一阶段已验证的 ESP SSL/CA/时间校验，只在外部配置中保存凭据。 */
#include "gateway_transport.h"
#include "gateway_config.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static Network network;
static MQTTClient client;
static unsigned char tx_buffer[2048],rx_buffer[512];
static uint32_t epoch,epoch_tick;
static const GatewayConfig *config=GATEWAY_CONFIG;
_Static_assert(sizeof(GatewayConfig)==312,"configuration layout changed");
int gateway_config_valid(void){return config->magic==GATEWAY_CONFIG_MAGIC&&!config->host[64]&&!config->ssid[32]&&!config->wifi_password[64]&&!config->password[64]&&!config->username[32]&&!config->client_id[40];}
uint32_t gateway_epoch(void){return epoch+(uint32_t)(g_uptime_ms-epoch_tick)/1000;}
static int step(const char *name, const char *command, uint32_t timeout)
{
  int ok = at_command(command, timeout);
  console(ok ? "GW OK " : "GW FAIL "); console(name); console("\r\n");
  return ok;
}
int gateway_mqtt_open(const MpFrame *will_frame){
  char will[512];if(!mp_json(will_frame,will,sizeof(will)))return 0;
  MQTTClientInit(&client,&network,5000,tx_buffer,sizeof(tx_buffer),rx_buffer,sizeof(rx_buffer));
  MQTTPacket_connectData options=MQTTPacket_connectData_initializer;
  options.MQTTVersion=4;options.keepAliveInterval=15;options.cleansession=1;
  options.clientID.cstring=(char*)config->client_id;options.username.cstring=(char*)config->username;options.password.cstring=(char*)config->password;
  options.willFlag=1;options.will.qos=1;options.will.retained=1;options.will.topicName.cstring="mpm/v1/GW-C-001/status";options.will.message.cstring=will;
  int ok=MQTTConnect(&client,&options)==SUCCESS;memset(will,0,sizeof(will));
  console(ok?"GW MQTT_CONNECTED\r\n":"GW FAIL MQTT_CONNECT\r\n");return ok;
}
int gateway_mqtt_publish(const MpFrame *frame){
  static char payload[2048];char topic[120];int length=mp_json(frame,payload,sizeof(payload));
  if(!length||!mp_topic(frame,topic,sizeof(topic)))return 0;
  MQTTMessage message={0};message.qos=frame->rate&&!frame->replay?QOS0:QOS1;
  /* 沿用实时波形 QoS0；标量/状态/REPLAY 使用 QoS1。只有 QoS1 成功意味着 PUBACK。 */
  message.retained=frame->stream==MP_NODE_STATUS||frame->stream==MP_GATEWAY_STATUS;
  message.payload=payload;message.payloadlen=(size_t)length;
  return MQTTPublish(&client,topic,&message)==SUCCESS;
}
int gateway_mqtt_yield(void){return MQTTYield(&client,5)==SUCCESS&&MQTTIsConnected(&client);}
void gateway_network_close(void){(void)at_command("AT+CIPCLOSE",2000);}
int gateway_network_open(void)
{
  char command[256];
  network_init(&network);
  if (!step("AT", "AT", 2000) || !step("ECHO", "ATE0", 2000) ||
      !step("VOLATILE", "AT+SYSSTORE=0", 2000) || !step("STA", "AT+CWMODE=1", 3000)) return 0;
  (void)snprintf(command, sizeof(command), "AT+CWJAP=\"%s\",\"%s\"", config->ssid, config->wifi_password);
  if (!step("WIFI", command, 30000)) return 0;
  (void)at_command("AT+CIPCLOSE", 2000);
  if (!step("SINGLE", "AT+CIPMUX=0", 2000) || !step("PASSIVE", "AT+CIPRECVMODE=1", 2000)) return 0;
  /* 模块时间必须有效；不能用过时的编译时间冒充采集时间。 */
  (void)at_command("AT+CIPSNTPCFG=1,0", 2000);
  int time_ok = 0;
  for (unsigned int attempt = 0; attempt < 15U; ++attempt) {
    if (at_command("AT+SYSTIMESTAMP?", 2000)) {
      const char *value = strstr(at_response(), "+SYSTIMESTAMP:");
      if (value) {
        epoch = (uint32_t)strtoul(value + 14, NULL, 10);
        if (epoch >= config->minimum_epoch) { epoch_tick = g_uptime_ms; time_ok = 1; break; }
      }
    }
    delay_ms(1000);
  }
  if (!time_ok) { console("GW FAIL TIME\r\n"); return 0; }
  if (!step("CA_VERIFY", "AT+CIPSSLCCONF=2,0,0", 2000)) return 0;
  (void)snprintf(command, sizeof(command), "AT+CIPSSLCCN=\"%s\"", config->host);
  if (!step("CERT_NAME", command, 2000)) return 0;
  /* 此模块存在 SNI 优先的行为，两个名称必须绑定同一个外部配置目标。 */
  (void)snprintf(command, sizeof(command), "AT+CIPSSLCSNI=\"%s\"", config->host);
  if (!step("SNI", command, 2000)) return 0;
  (void)snprintf(command, sizeof(command), "AT+CIPSTART=\"SSL\",\"%s\",8883", config->host);
  int ok = step("TLS", command, 30000);
  memset(command, 0, sizeof(command));
  return ok;
}
