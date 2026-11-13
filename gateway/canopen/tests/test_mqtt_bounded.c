#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "MQTTPacket.h"

/* 合同冻结的本机输入；不生成随机样本，不连接真实 MQTT 或开发板。 */

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

    /* QoS1 帧必须保留两字节 Packet ID；只有 topic 的固定样本应被拒绝。 */
    unsigned char missing_id[5] = {0x32, 3, 0x00, 0x01, 't'};
    rc = MQTTDeserialize_publish(&dup, &qos, &retained, &packetid, &topicName,
                                 &payload, &payloadlen, missing_id, sizeof(missing_id));
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

static void test_connack_deserialization_bounds(void)
{
    unsigned char session_present = 0, result = 0;
    unsigned char truncated[] = {0x20, 2, 0};
    unsigned char declared_too_long[] = {0x20, 10, 0, 0};
    unsigned char valid[] = {0x20, 2, 0, 0};

    /* 同时覆盖实际截断、声明长度超出实际、完整正常报文。 */
    assert(MQTTDeserialize_connack(&session_present, &result, truncated,
                                   sizeof(truncated)) == 0);
    assert(MQTTDeserialize_connack(&session_present, &result, declared_too_long,
                                   sizeof(declared_too_long)) == 0);
    assert(MQTTDeserialize_connack(&session_present, &result, valid, sizeof(valid)) == 1);
    assert(session_present == 0 && result == 0);
    printf("PASS: test_connack_deserialization_bounds\n");
}

static void test_suback_deserialization_bounds(void)
{
    unsigned short packetid = 0;
    int count = 0, qos = -1;
    unsigned char truncated[] = {0x90, 3, 0};
    unsigned char declared_too_long[] = {0x90, 10, 0, 42, 1};
    unsigned char valid[] = {0x90, 3, 0, 42, 1};

    /* 输出数组容量固定为 1，正常样本必须完整返回 packetid 和授予 QoS。 */
    assert(MQTTDeserialize_suback(&packetid, 1, &count, &qos, truncated,
                                  sizeof(truncated)) == 0);
    assert(MQTTDeserialize_suback(&packetid, 1, &count, &qos, declared_too_long,
                                  sizeof(declared_too_long)) == 0);
    assert(MQTTDeserialize_suback(&packetid, 1, &count, &qos, valid, sizeof(valid)) == 1);
    assert(packetid == 42 && count == 1 && qos == 1);
    printf("PASS: test_suback_deserialization_bounds\n");
}

static void test_unsuback_deserialization_bounds(void)
{
    unsigned short packetid = 0;
    unsigned char truncated[] = {0xb0, 2, 0};
    unsigned char declared_too_long[] = {0xb0, 10, 0, 42};
    unsigned char valid[] = {0xb0, 2, 0, 42};

    /* 包装器必须保留 ACK 解析失败状态，不能仅凭报文类型改回成功。 */
    assert(MQTTDeserialize_unsuback(&packetid, truncated, sizeof(truncated)) == 0);
    assert(MQTTDeserialize_unsuback(&packetid, declared_too_long,
                                    sizeof(declared_too_long)) == 0);
    assert(MQTTDeserialize_unsuback(&packetid, valid, sizeof(valid)) == 1);
    assert(packetid == 42);
    printf("PASS: test_unsuback_deserialization_bounds\n");
}

static const unsigned char *reader_data;
static size_t reader_size, reader_offset;
static unsigned int reader_calls;

static int fixed_read(unsigned char *buffer, int length)
{
    ++reader_calls;
    assert(length >= 0);
    if ((size_t)length > reader_size - reader_offset)
        return 0;
    memcpy(buffer, reader_data + reader_offset, (size_t)length);
    reader_offset += (size_t)length;
    return length;
}

static void set_reader(const unsigned char *data, size_t size)
{
    reader_data = data;
    reader_size = size;
    reader_offset = 0;
    reader_calls = 0;
}

static void test_packet_read_error_propagation(void)
{
    unsigned char buffer[16];
    const unsigned char truncated[] = {0x40, 0x80};
    const unsigned char five_byte_length[] = {0x40, 0x80, 0x80, 0x80, 0x80, 0x80};
    const unsigned char declared_too_long[] = {0x40, 10, 0, 42};
    const unsigned char valid[] = {0x40, 2, 0, 42};

    set_reader(valid, sizeof(valid));
    assert(MQTTPacket_read(NULL, sizeof(buffer), fixed_read) < 0);
    assert(reader_calls == 0);
    assert(MQTTPacket_read(buffer, 0, fixed_read) < 0);
    assert(reader_calls == 0);

    /* 解码失败后不允许回填长度，也不允许额外读取 payload。 */
    memset(buffer, 0xa5, sizeof(buffer));
    set_reader(truncated, sizeof(truncated));
    assert(MQTTPacket_read(buffer, sizeof(buffer), fixed_read) < 0);
    assert(reader_calls == 3 && buffer[1] == 0xa5);

    memset(buffer, 0xa5, sizeof(buffer));
    set_reader(five_byte_length, sizeof(five_byte_length));
    assert(MQTTPacket_read(buffer, sizeof(buffer), fixed_read) < 0);
    assert(reader_calls == 5 && buffer[1] == 0xa5);

    set_reader(declared_too_long, sizeof(declared_too_long));
    assert(MQTTPacket_read(buffer, sizeof(buffer), fixed_read) < 0);
    assert(reader_calls == 3);

    set_reader(valid, sizeof(valid));
    assert(MQTTPacket_read(buffer, sizeof(buffer), fixed_read) == PUBACK);
    assert(memcmp(buffer, valid, sizeof(valid)) == 0);
    printf("PASS: test_packet_read_error_propagation\n");
}

int main(void)
{
    printf("=== Starting MQTT Bounded Deserialization Regression Tests ===\n");
    test_remaining_length_bounds();
    test_publish_deserialization_bounds();
    test_ack_deserialization_bounds();
    test_connack_deserialization_bounds();
    test_suback_deserialization_bounds();
    test_unsuback_deserialization_bounds();
    test_packet_read_error_propagation();
    printf("PASS: 29 fixed parser/reader cases\n");
    return 0;
}
