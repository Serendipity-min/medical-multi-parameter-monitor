/* Gateway-C 第一阶段：Paho MQTT 在 STM32 运行，ESP 仅提供已验证的 SSL Socket。 */
#include "gateway_platform.h"
#include "gateway_config.h"
#include "canopen_adapter.h"
#include "MQTTClient.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

static unsigned char tx_buffer[2048], rx_buffer[512];
static MQTTClient client;
static Network network;
static char payload_buffer[1800], session[40];
static uint32_t epoch, epoch_tick, sequence, connection_count;
static const GatewayConfig *config = GATEWAY_CONFIG;
_Static_assert(sizeof(GatewayConfig) == 312, "configuration layout changed");

static const char *timestamp_string(void)
{
  static char text[24];
  uint32_t elapsed = (uint32_t)(g_uptime_ms - epoch_tick);
  /* newlib-nano 的精简 printf 不保证支持 long long，分段格式化毫秒时间戳。 */
  (void)snprintf(text, sizeof(text), "%lu%03lu", (unsigned long)(epoch + elapsed/1000U), (unsigned long)(elapsed%1000U));
  return text;
}
static int step(const char *name, const char *command, uint32_t timeout)
{
  int ok = at_command(command, timeout);
  console(ok ? "GW OK " : "GW FAIL "); console(name); console("\r\n");
  return ok;
}
static int start_network(void)
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
static int publish(const char *node, const char *kind, const char *stream, enum QoS qos, int retained)
{
  char topic[120];
  if (!node) (void)snprintf(topic, sizeof(topic), "mpm/v1/GW-C-001/status");
  else if (!stream) (void)snprintf(topic, sizeof(topic), "mpm/v1/GW-C-001/%s/%s", node, kind);
  else (void)snprintf(topic, sizeof(topic), "mpm/v1/GW-C-001/%s/%s/%s", node, kind, stream);
  MQTTMessage message = {0};
  message.qos = qos; message.retained = (unsigned char)retained;
  message.payload = payload_buffer; message.payloadlen = strlen(payload_buffer);
  return MQTTPublish(&client, topic, &message) == SUCCESS;
}
static int begin_payload(const char *unit, const char *value)
{
  return snprintf(payload_buffer, sizeof(payload_buffer),
    "{\"timestamp\":%s,\"seq\":%lu,\"session_id\":\"%s\",\"validity\":\"VALID\",\"source\":\"MOCK\",\"synthetic\":true,\"unit\":\"%s\",\"value\":%s",
    timestamp_string(), (unsigned long)sequence, session, unit, value);
}
static int scalar(const char *node, const char *stream, const char *unit, const char *value)
{
  int length = begin_payload(unit, value);
  if (length < 0 || (unsigned int)length + 2U >= sizeof(payload_buffer)) return 0;
  strcat(payload_buffer, "}");
  return publish(node, "telemetry", stream, QOS1, 0);
}
static int status(const char *node)
{
  int length = begin_payload("state", "\"ONLINE\"");
  if (length < 0 || (unsigned int)length + 2U >= sizeof(payload_buffer)) return 0;
  strcat(payload_buffer, "}");
  return publish(node, "status", NULL, QOS1, 1);
}
static int wave(const char *node, const char *stream, unsigned int rate)
{
  unsigned int offset = (unsigned int)begin_payload(strcmp(stream,"ecg") == 0 ? "mV" : "relative", "null");
  if (offset >= sizeof(payload_buffer)) return 0;
  int written = snprintf(payload_buffer + offset, sizeof(payload_buffer)-offset, ",\"sample_rate\":%u,\"samples\":[", rate);
  if (written < 0 || (unsigned int)written >= sizeof(payload_buffer)-offset) return 0;
  offset += (unsigned int)written;
  for (unsigned int i = 0; i < rate; ++i) {
    float t = (float)sequence + (float)i / (float)rate;
    float phase = fmodf(t * 1.2f, 1.0f), value;
    if (strcmp(stream, "ecg") == 0) {
      float d = (phase - .25f) / .025f;
      value = .1f*sinf(6.2831853f*phase) + expf(-d*d);
    } else if (strcmp(stream,"ppg") == 0) {
      value = sinf(3.1415926f*phase); value = value*value*value;
    } else value = .8f*sinf(1.5707963f*t);
    int fixed = (int)(value*100.0f), magnitude = abs(fixed);
    written = snprintf(payload_buffer+offset, sizeof(payload_buffer)-offset,
      "%s%s%d.%02d", i ? "," : "", fixed < 0 ? "-" : "", magnitude/100, magnitude%100);
    if (written < 0 || (unsigned int)written >= sizeof(payload_buffer)-offset) return 0;
    offset += (unsigned int)written;
  }
  if (offset+3U >= sizeof(payload_buffer)) return 0;
  memcpy(payload_buffer+offset, "]}", 3);
  return publish(node, "telemetry", stream, QOS0, 0);
}
static int connect_mqtt(void)
{
  char will[256];
  (void)snprintf(session, sizeof(session), "gw-%lu-%lu", (unsigned long)epoch, (unsigned long)++connection_count);
  (void)snprintf(will, sizeof(will),
    "{\"timestamp\":%s,\"seq\":9007199254740991,\"session_id\":\"%s\",\"validity\":\"OFFLINE\",\"source\":\"MOCK\",\"synthetic\":true,\"value\":\"OFFLINE\",\"unit\":\"state\"}",
    timestamp_string(), session);
  MQTTClientInit(&client, &network, 5000, tx_buffer, sizeof(tx_buffer), rx_buffer, sizeof(rx_buffer));
  MQTTPacket_connectData options = MQTTPacket_connectData_initializer;
  options.MQTTVersion = 4; options.keepAliveInterval = 15; options.cleansession = 1;
  options.clientID.cstring = (char *)config->client_id;
  options.username.cstring = (char *)config->username; options.password.cstring = (char *)config->password;
  options.willFlag = 1; options.will.qos = 1; options.will.retained = 1;
  options.will.topicName.cstring = "mpm/v1/GW-C-001/status"; options.will.message.cstring = will;
  int ok = MQTTConnect(&client, &options) == SUCCESS;
  memset(will, 0, sizeof(will));
  console(ok ? "GW MQTT_CONNECTED\r\n" : "GW FAIL MQTT_CONNECT\r\n");
  return ok;
}
int main(void)
{
  platform_init(); console("GW BOOT PAHO MQTT311 SYNTHETIC\r\n");
  if (config->magic != GATEWAY_CONFIG_MAGIC || config->host[64] || config->ssid[32] ||
      config->wifi_password[64] || config->password[64] || config->username[32] || config->client_id[40]) {
    console("GW CONFIG_REQUIRED\r\n"); while (1) { }
  }
  while (1) {
    if (!start_network() || !connect_mqtt()) { delay_ms(3000); continue; }
    sequence = 0;
    while (MQTTIsConnected(&client)) {
      uint32_t began = g_uptime_ms;
      /* 即使发布一轮超过一秒也能响应本地断网演练；等待 LWT 到达后再重连。 */
      if (console_char() == 'D') {
        (void)at_command("AT+CWQAP", 3000);
        console("GW WIFI_TEST_DISCONNECTED\r\n"); delay_ms(30000); break;
      }
      if (!status(NULL) || !status("NODE-A") || !status("NODE-B") ||
          !scalar("NODE-B","hr","bpm","73.0") || !scalar("NODE-B","rr","breaths/min","16.0") ||
          !scalar("NODE-B","temp","degC","36.7") || !scalar("NODE-A","spo2","%","97.0") ||
          !scalar("NODE-A","pr","bpm","73.0") || !scalar("NODE-A","nibp","mmHg","[116.0,74.0]") ||
          !wave("NODE-B","ecg",250) || !wave("NODE-A","ppg",50) || !wave("NODE-B","resp",50)) break;
      sequence++;
      if (sequence % 5U == 0) { console("GW PUBLISH_OK\r\n"); }
      /* 本地断网入口在循环边界处理；等待期间维持 MQTT Keepalive。 */
      while ((uint32_t)(g_uptime_ms-began) < 1000U) {
        if (MQTTYield(&client, 10) != SUCCESS) break;
      }
    }
    console("GW RECONNECT\r\n");
    (void)at_command("AT+CIPCLOSE", 2000); delay_ms(2000);
  }
}
