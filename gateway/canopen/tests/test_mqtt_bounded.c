#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "MQTTPacket.h"

static void test_remaining_length_bounds(void)
{
    int value = 0;
    int rc;

    /* 1. NULL buffer */
    rc = MQTTPacket_decodeBufSafe(NULL, 10, &value);
    assert(rc < 0);

    /* 2. 0 length buffer */
    unsigned char buf1[4] = {0x00};
    rc = MQTTPacket_decodeBufSafe(buf1, 0, &value);
    assert(rc < 0);

    /* 3. Truncated remaining length: 1 byte with continuation bit set (0x80), but buflen is 1 */
    unsigned char truncated[1] = {0x80};
    rc = MQTTPacket_decodeBufSafe(truncated, sizeof(truncated), &value);
    assert(rc < 0);

    /* 4. Malformed 5-byte remaining length: all continuation bits set */
    unsigned char too_long[5] = {0x80, 0x80, 0x80, 0x80, 0x80};
    rc = MQTTPacket_decodeBufSafe(too_long, sizeof(too_long), &value);
    assert(rc < 0);

    /* 5. Valid 1-byte length: 64 */
    unsigned char valid1[1] = {64};
    rc = MQTTPacket_decodeBufSafe(valid1, sizeof(valid1), &value);
    assert(rc == 1);
    assert(value == 64);

    /* 6. Valid 2-byte length: 321 (0xC1, 0x02) */
    unsigned char valid2[2] = {0xC1, 0x02};
    rc = MQTTPacket_decodeBufSafe(valid2, sizeof(valid2), &value);
    assert(rc == 2);
    assert(value == 321);

    printf("PASS: test_remaining_length_bounds\n");
}

static void test_publish_deserialization_bounds(void)
{
    unsigned char dup = 0;
    int qos = 0;
    unsigned char retained = 0;
    unsigned short packetid = 0;
    MQTTString topicName = MQTTString_initializer;
    unsigned char *payload = NULL;
    int payloadlen = 0;
    int rc;

    /* 1. Truncated buffer: less than 2 bytes */
    unsigned char short_buf[1] = {0x30};
    rc = MQTTDeserialize_publish(&dup, &qos, &retained, &packetid, &topicName,
                                 &payload, &payloadlen, short_buf, sizeof(short_buf));
    assert(rc == 0);

    /* 2. Declared remaining length is 100, but buffer is only 4 bytes */
    unsigned char overflow_len[4] = {0x30, 100, 0x00, 0x01};
    rc = MQTTDeserialize_publish(&dup, &qos, &retained, &packetid, &topicName,
                                 &payload, &payloadlen, overflow_len, sizeof(overflow_len));
    assert(rc == 0);

    /* 3. Topic length exceeds remaining packet bytes */
    /* Header=0x30, rem_len=4, topic_len=10 (0x00, 0x0A) */
    unsigned char bad_topic[6] = {0x30, 4, 0x00, 0x0A, 'a', 'b'};
    rc = MQTTDeserialize_publish(&dup, &qos, &retained, &packetid, &topicName,
                                 &payload, &payloadlen, bad_topic, sizeof(bad_topic));
    assert(rc == 0);

    /* 4. Valid PUBLISH (QoS 0): Header=0x30, rem_len=7, topic="t" (len 1: 0x00, 0x01, 't'), payload="data" (4 bytes) */
    unsigned char valid_pub[9] = {0x30, 7, 0x00, 0x01, 't', 'd', 'a', 't', 'a'};
    rc = MQTTDeserialize_publish(&dup, &qos, &retained, &packetid, &topicName,
                                 &payload, &payloadlen, valid_pub, sizeof(valid_pub));
    assert(rc == 1);
    assert(qos == 0);
    assert(payloadlen == 4);
    assert(memcmp(payload, "data", 4) == 0);

    printf("PASS: test_publish_deserialization_bounds\n");
}

static void test_ack_deserialization_bounds(void)
{
    unsigned char type = 0;
    unsigned char dup = 0;
    unsigned short packetid = 0;
    int rc;

    /* 1. Truncated ACK: less than 3 bytes */
    unsigned char short_ack[2] = {0x40, 0x02};
    rc = MQTTDeserialize_ack(&type, &dup, &packetid, short_ack, sizeof(short_ack));
    assert(rc == 0);

    /* 2. Claimed rem_len=10, buffer only 4 bytes */
    unsigned char bad_ack[4] = {0x40, 10, 0x00, 0x01};
    rc = MQTTDeserialize_ack(&type, &dup, &packetid, bad_ack, sizeof(bad_ack));
    assert(rc == 0);

    /* 3. Valid PUBACK: Header=0x40, rem_len=2, packetid=0x002A (42) */
    unsigned char valid_ack[4] = {0x40, 2, 0x00, 0x2A};
    rc = MQTTDeserialize_ack(&type, &dup, &packetid, valid_ack, sizeof(valid_ack));
    assert(rc == 1);
    assert(type == PUBACK);
    assert(packetid == 42);

    printf("PASS: test_ack_deserialization_bounds\n");
}

int main(void)
{
    printf("=== Starting MQTT Bounded Deserialization Regression Tests ===\n");
    test_remaining_length_bounds();
    test_publish_deserialization_bounds();
    test_ack_deserialization_bounds();
    printf("=== All MQTT Bounded Deserialization Tests Passed! ===\n");
    return 0;
}
