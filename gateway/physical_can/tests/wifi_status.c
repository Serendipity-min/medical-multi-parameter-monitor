/* 合成关联信息只核对数值提取边界，不涉及真实SSID/BSSID或扫描AP。 */
#include "wifi_status.h"
#include <assert.h>
#include <stdio.h>

int main(void)
{
    int ch=-1,rssi=1;
    assert(gateway_sleep_mode("\r\n+SLEEP:3\r\nOK\r\n")==3);
    assert(gateway_sleep_mode("+SLEEP:0\r\n")==0);
    assert(gateway_sleep_mode("+SLEEP:9\r\n")==-1);
    assert(gateway_sleep_mode("+SLEEP:3bad\r\n")==-1);
    assert(gateway_sleep_mode("ERROR\r\n")==-1);
    assert(gateway_wifi_signal("+CWJAP:\"synthetic\",\"00:00:00:00:00:00\",6,-40,0,1,3,0,0\r\nOK\r\n",&ch,&rssi));
    assert(ch==6 && rssi==-40);
    assert(gateway_wifi_signal("+CWJAP:\"synthetic\",\"00:00:00:00:00:00\",1,-127\r\n",&ch,&rssi));
    assert(!gateway_wifi_signal("+CWJAP:\"synthetic\",\"00:00:00:00:00:00\",99,-40\r\n",&ch,&rssi));
    assert(!gateway_wifi_signal("+CWJAP:\"synthetic\",\"00:00:00:00:00:00\",6,-200\r\n",&ch,&rssi));
    assert(!gateway_wifi_signal("+CWJAP:malformed\r\n",&ch,&rssi));
    puts("WiFi numeric-only status / bounds / unsupported mode PASS");
    return 0;
}
