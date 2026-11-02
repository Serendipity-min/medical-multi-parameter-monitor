#include "mic_format.h"
#include <assert.h>
#include <stdio.h>

int main(void) {
    assert(mic_sample24(0x7fff, 0xff00) == 8388607);
    assert(mic_sample24(0x8000, 0x0000) == -8388608);
    assert(mic_sample24(0xffff, 0xff00) == -1);
    assert(mic_sample24(0x0000, 0x0100) == 1);
    assert(mic_pcm16(0x7fff, 0xff00) == 32767);
    assert(mic_pcm16(0x8000, 0x0000) == -32768);
    assert(mic_pcm16(0xffff, 0xff00) == -1);
    /* 左/右槽各含两个半字，故意给右槽不同符号，不能按半字交错当单声道。 */
    const uint16_t frames[] = {0x1234,0x5600,0xfedc,0xba00,0x8000,0,0x7fff,0xff00};
    assert(mic_sample24(frames[0], frames[1]) == 0x123456);
    assert(mic_sample24(frames[2], frames[3]) == -74566);
    assert(mic_pcm16(frames[4], frames[5]) == -32768);
    assert(mic_pcm16(frames[6], frames[7]) == 32767);
    assert(mic_sample24(0x1234, 0x56ff) == 0x123456);
    assert(mic_crc32("123456789", 9) == 0xcbf43926u);
    puts("HOST_I2S_FORMAT_PASS: signed24/PCM16/stereo-slot/padding/CRC; no hardware");
    return 0;
}
