// @file    canopen.c
// @brief   心率节点 CANopen 从站实现（CiA 301 精简子集）
// 数据通路：HrPage_GetVitals() → 对象字典 0x2100 → TPDO1(0x183) → 主机
// 配置通路：主机 SDO 写 0x2100:06~09 → HrPage_SetLimits() → 刷屏
#include "canopen.h"
#include "can.h"
#include "hr_page.h"
#include <string.h>

// ---------------- 对象字典：只有能被 SDO 写回的项才用变量，其余直接读宏 ----------------
static uint32_t s_tpdo_cob   = CO_COB_TPDO1;  // 0x1800:01，可写；SDO 的两个 COB-ID 固定
static uint16_t s_hb_time    = 1000;  // 0x1017 心跳周期 ms，0 = 关闭
static uint8_t  s_tpdo_trans = 254;   // 0x1800:02 254 事件触发(厂商)，255 = 周期
static uint16_t s_tpdo_inhib = 0;     // 0x1800:03 抑制时间，单位 0.1ms
static uint16_t s_tpdo_timer = 1000;  // 0x1800:05 事件定时器，单位 ms

// 0x1A00 TPDO1 映射：心率 + 呼吸 + 状态 + 报警 + 质量 = 7 字节
static uint32_t s_tpdo_map[8] = {
    0x21000110,  // 0x2100:01 心率 int16
    0x21000210,  // 0x2100:02 呼吸 int16
    0x21000308,  // 0x2100:03 状态 uint8
    0x21000408,  // 0x2100:04 报警 uint8
    0x21000508   // 0x2100:05 质量 uint8
};
static uint8_t  s_tpdo_mapn = 5;

// ---------------- 运行状态 ----------------
static uint8_t  s_nmt = CO_NMT_PREOP;
static uint32_t s_hb_t;
static uint32_t s_tpdo_t;  // 事件定时器时基
static uint32_t s_tpdo_last;  // 上次发送时刻（抑制时间用）
static uint8_t  s_tpdo_prev[8];  // 上次发送内容（变化触发用）
static uint8_t  s_tpdo_prevn;
static uint16_t s_emcy_prev = CO_EMCY_NONE;
static CoStats_t s_st;
static uint8_t  s_selftest = 0xFF;  // 上电回环自测结果：0xFF=未测 1=通过 0=失败

// SDO 分段上传状态
static uint8_t  s_seg_buf[24];
static uint8_t  s_seg_len;  // >0 = 有分段上传在进行（同时充当忙标志）
static uint8_t  s_seg_pos;

// 把 16 位数按小端写入
static void Put16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v & 0xFF);
    p[1] = (uint8_t)(v >> 8);
}
// 32 位写 4 字节
static void Put32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v & 0xFF);
    p[1] = (uint8_t)((v >> 8) & 0xFF);
    p[2] = (uint8_t)((v >> 16) & 0xFF);
    p[3] = (uint8_t)((v >> 24) & 0xFF);
}
// 从 2 字节读出 16 位
static uint16_t Get16(const uint8_t *p)
{
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}
// 从 4 字节读出 32 位
static uint32_t Get32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

// ---------------- 对象字典读 ----------------
// 返回 1 = 成功，*len 为字节数；0 = 对象不存在
static uint8_t Co_ObjRead(uint16_t idx, uint8_t sub, uint8_t *out, uint8_t *len)
{
    HrVitals_t v;      //用于临时存放从传感器取到的心率数据
    uint8_t n = 0;     // 本次读取返回的字节数，先置 0

    switch (idx)
    {
		// 0x1000 设备类型
		case CO_IDX_DEV_TYPE:
			if (sub != 0) { return 0; }        // 该对象只有子索引 0，其它非法
			Put32(out, CO_DEV_TYPE); n = 4;    // 32 位设备类型，写入 4 字节
			break;

		// 0x1001 错误寄存器
		case CO_IDX_ERROR_REG:
			if (sub != 0) { return 0; }       
			// 如果曾经发过 EMCY（s_emcy_prev 不是 NONE），就置错误位，否则为 0
			out[0] = (s_emcy_prev != CO_EMCY_NONE) ? (uint8_t)CO_ERR_BITS : 0;
			n = 1;                             // 1 字节
			break;

		// 0x1005 SYNC 的 COB-ID
		case CO_IDX_COB_SYNC:
			if (sub != 0) { return 0; }       
			Put32(out, CO_COB_SYNC); n = 4;    // 32 位 COB-ID，本节点不用 SYNC，回固定值
			break;

		// 0x1008 设备名称（字符串）
		case CO_IDX_DEV_NAME:
			if (sub != 0) { return 0; }       
			// sizeof 包含末尾 '\0'，要减 1；CANopen 字符串不带结束符
			n = (uint8_t)(sizeof(CO_DEV_NAME) - 1);
			memcpy(out, CO_DEV_NAME, n);       // 拷贝字符串内容
			break;

		// 0x1009 硬件版本（字符串）
		case CO_IDX_HW_VER:
			if (sub != 0) { return 0; }       
			n = (uint8_t)(sizeof(CO_HW_VER) - 1);  // 去掉末尾 '\0'
			memcpy(out, CO_HW_VER, n);
			break;

		// 0x100A 软件版本（字符串）
		case CO_IDX_SW_VER:
			if (sub != 0) { return 0; }    
			n = (uint8_t)(sizeof(CO_SW_VER) - 1);  // 去掉末尾 '\0'
			memcpy(out, CO_SW_VER, n);
			break;

		// 0x1017 心跳周期（ms）
		case CO_IDX_HB_TIME:
			if (sub != 0) { return 0; }     
			Put16(out, s_hb_time); n = 2;      // 16 位，2 字节
			break;

		// 0x1018 设备标识（厂商/产品/版本/序列号）
		case CO_IDX_IDENTITY:
			if (sub == 0)      { out[0] = 4; n = 1; }               // 子索引 0 = 条目个数 4
			else if (sub == 1) { Put32(out, CO_VENDOR_ID);    n = 4; }  // 厂商 ID
			else if (sub == 2) { Put32(out, CO_PRODUCT_CODE); n = 4; }  // 产品代码
			else if (sub == 3) { Put32(out, CO_REVISION);     n = 4; }  // 版本号
			else if (sub == 4) { Put32(out, CO_SERIAL);       n = 4; }  // 序列号
			else { return 0; }                                          // 其它子索引非法
			break;

		// 0x1200 SDO 服务端参数
		case CO_IDX_SDO_SRV:
			if (sub == 0)      { out[0] = 2; n = 1; }               // 子索引 0 = 条目个数 2
			else if (sub == 1) { Put32(out, CO_COB_SDO_RX); n = 4; } // 接收 SDO 的 COB-ID
			else if (sub == 2) { Put32(out, CO_COB_SDO_TX); n = 4; } // 发送 SDO 的 COB-ID
			else { return 0; }                                        // 其它子索引非法
			break;

		// 0x1800 TPDO1 通信参数
		case CO_IDX_TPDO1_COMM:
			if (sub == 0)      { out[0] = 5; n = 1; }               // 子索引 0 = 条目个数 5
			else if (sub == 1) { Put32(out, s_tpdo_cob);   n = 4; } // TPDO 的 COB-ID
			else if (sub == 2) { out[0] = s_tpdo_trans;    n = 1; } // 传输类型（254 事件/255 周期）
			else if (sub == 3) { Put16(out, s_tpdo_inhib); n = 2; } // 抑制时间（0.1ms）
			else if (sub == 4) { Put16(out, 0);            n = 2; } // 保留项，固定 0
			else if (sub == 5) { Put16(out, s_tpdo_timer); n = 2; } // 事件定时器（ms）
			else { return 0; }                                        // 其它子索引非法
			break;

		// 0x1A00 TPDO1 映射参数
		case CO_IDX_TPDO1_MAP:
			if (sub == 0) { out[0] = s_tpdo_mapn; n = 1; }          // 子索引 0 = 当前映射条目数
			else if ((sub >= 1) && (sub <= s_tpdo_mapn))            // 子索引 1~N 对应映射项
			{
				Put32(out, s_tpdo_map[sub - 1]); n = 4;             // 数组下标从 0 开始，sub-1
			}
			else { return 0; }                                       // 超出当前条目数，非法
			break;

		// 0x2100 厂商自定义：心率监护对象
		case CO_IDX_HR_OBJ:
			HrPage_GetVitals(&v);   // 先向应用层取最新的心率/呼吸等数据
			switch (sub)            // 再按子索引分派具体条目
			{
				case CO_APP_BPM:       Put16(out, (uint16_t)v.bpm); n = 2; break; // 心率，2 字节
				case CO_APP_RPM:       Put16(out, (uint16_t)v.rpm); n = 2; break; // 呼吸，2 字节
				case CO_APP_STATUS:
					// 状态字节：把 4 个 bool 标志拼成 bit0~bit3
					out[0] = (uint8_t)((v.hr_valid ? CO_STATUS_HR_VALID : 0) |  // bit: 心率有效
									   (v.rr_valid ? CO_STATUS_RR_VALID : 0) |  // bit: 呼吸有效
									   (v.probe    ? CO_STATUS_PROBE    : 0) |  // bit: 探头在位
									   (v.running  ? CO_STATUS_RUNNING  : 0));  // bit: 正在运行
					n = 1;   // 1 字节
					break;
				case CO_APP_ALARM:     out[0] = v.alarm;   n = 1; break;  // 报警字节，1 字节
				case CO_APP_QUALITY:   out[0] = v.quality; n = 1; break;  // 信号质量，1 字节
				case CO_APP_HR_LIM_HI: Put16(out, (uint16_t)v.hr_hi); n = 2; break; // 心率上限
				case CO_APP_HR_LIM_LO: Put16(out, (uint16_t)v.hr_lo); n = 2; break; // 心率下限
				case CO_APP_RR_LIM_HI: Put16(out, (uint16_t)v.rr_hi); n = 2; break; // 呼吸上限
				case CO_APP_RR_LIM_LO: Put16(out, (uint16_t)v.rr_lo); n = 2; break; // 呼吸下限
				default: return 0;  
			}
			break;

		// 未知索引
		default:
			return 0;   // 对象不存在，返回失败
    }

    *len = n;    // 把本次读取的字节数回传给调用者
    return 1;    // 成功
}

// ---------------- 对象字典写 ----------------
// 返回 0 = 成功；非 0 = SDO 中止码
static uint32_t Co_ObjWrite(uint16_t idx, uint8_t sub, const uint8_t *in, uint8_t len)
{
    HrVitals_t v;
    int16_t hh, hl, rh, rl;

    switch (idx)
    {
    case CO_IDX_HB_TIME:
        if ((sub != 0) || (len != 2)) { return 0x06010000; }
        s_hb_time = Get16(in);
        break;

    case CO_IDX_TPDO1_COMM:
        if (sub == 1)
        {
            if (len != 4) { return 0x06010000; }
            s_tpdo_cob = Get32(in) & 0x7FF;  // 只支持 11 位标准帧
            break;
        }
        if (sub == 2) { if (len != 1) { return 0x06010000; } s_tpdo_trans = in[0]; break; }
        if (sub == 3) { if (len != 2) { return 0x06010000; } s_tpdo_inhib = Get16(in); break; }
        if (sub == 5) { if (len != 2) { return 0x06010000; } s_tpdo_timer = Get16(in); break; }
        return 0x06010000;

    case CO_IDX_TPDO1_MAP:
        if (sub == 0)
        {
            if (len != 1) { return 0x06010000; }
            if (in[0] > 8) { return 0x06090030; }
            s_tpdo_mapn = in[0];
            break;
        }
        if ((sub >= 1) && (sub <= 8))
        {
            if (len != 4) { return 0x06010000; }
            s_tpdo_map[sub - 1] = Get32(in);
            break;
        }
        return 0x06010000;

    case CO_IDX_HR_OBJ:
        // 只有 4 个限值对象可写，其余只读
        if ((sub != CO_APP_HR_LIM_HI) && (sub != CO_APP_HR_LIM_LO) &&
            (sub != CO_APP_RR_LIM_HI) && (sub != CO_APP_RR_LIM_LO))
        {
            return 0x06010001;  // 只读对象
        }
        if (len != 2) { return 0x06010000; }
        HrPage_GetVitals(&v);  // 取当前值，只改其中一个
        hh = v.hr_hi; hl = v.hr_lo; rh = v.rr_hi; rl = v.rr_lo;
        if      (sub == CO_APP_HR_LIM_HI) { hh = (int16_t)Get16(in); }
        else if (sub == CO_APP_HR_LIM_LO) { hl = (int16_t)Get16(in); }
        else if (sub == CO_APP_RR_LIM_HI) { rh = (int16_t)Get16(in); }
        else                              { rl = (int16_t)Get16(in); }
        HrPage_SetLimits(hh, hl, rh, rl);  // 内部按屏规则夹紧
        break;

    default:
        return 0x06010000;  // 对象不支持写
    }
    return 0;
}

// ---------------- 发送：心跳 / EMCY ----------------
static void Co_SendHeartbeat(void)
{
    uint8_t d[1];

    d[0] = s_nmt;
    CAN1_Send_Msg(CO_COB_HEARTBEAT, d, 1);
    s_st.hb_tx++;
}

static void Co_SendEmcy(uint16_t code)
{
    uint8_t d[8];

    Put16(d, code);
    d[2] = (code != CO_EMCY_NONE) ? (uint8_t)CO_ERR_BITS : 0;
    d[3] = 0; d[4] = 0; d[5] = 0; d[6] = 0; d[7] = 0;
    CAN1_Send_Msg(CO_COB_EMCY, d, 8);
    s_st.emcy_tx++;
}

// TPDO1 打包,按 0x1A00 映射表拼装；返回字节数，0 = 失败
static uint8_t Co_BuildTpdo1(uint8_t *buf)
{
    uint8_t tmp[24];
    uint8_t i, l, n = 0;
    uint32_t e;
    uint16_t idx;
    uint8_t sub, bits;

    for (i = 0; i < s_tpdo_mapn; i++)
    {
        e = s_tpdo_map[i];
        if (e == 0) { continue; }
        idx  = (uint16_t)((e >> 16) & 0xFFFF);
        sub  = (uint8_t)((e >> 8) & 0xFF);
        bits = (uint8_t)(e & 0xFF);
        l = 0;
        if (Co_ObjRead(idx, sub, tmp, &l) == 0) { return 0; } // 去对象字典读
        if (l != (uint8_t)(bits / 8))           { return 0; }  // 映射长度与对象不符
        if ((uint8_t)(n + l) > 8)               { return 0; }
        memcpy(&buf[n], tmp, l);
        n = (uint8_t)(n + l);
    }
    return n;
}

static void Co_TpdoTick(uint32_t now)
{
    uint8_t buf[8];
    uint8_t n;
    uint8_t change;

    if (s_tpdo_trans == 0xFF) { return; }  // 被主机禁止

    n = Co_BuildTpdo1(buf);
    if ((n == 0) || (n > 8)) { return; }

    change = (uint8_t)((n != s_tpdo_prevn) || (memcmp(buf, s_tpdo_prev, n) != 0));

    if ((s_tpdo_timer != 0) && ((now - s_tpdo_t) >= s_tpdo_timer))
    {
        s_tpdo_t = now;  // 周期到
    }
    else if ((change != 0) && ((now - s_tpdo_last) >= (uint32_t)(s_tpdo_inhib / 10)))
    {
        // 数据变化触发（抑制时间已过）
    }
    else
    {
        return;
    }

    CAN1_Send_Msg(s_tpdo_cob, buf, n);
    s_st.tpdo_tx++;
    memcpy(s_tpdo_prev, buf, n);
    s_tpdo_prevn = n;
    s_tpdo_last = now;
}

// 越限/导联脱落 EMCY：只在状态变化时发一帧（含恢复为 0x0000）
static void Co_EmcyTick(void)
{
    HrVitals_t v;
    uint16_t code = CO_EMCY_NONE;

    HrPage_GetVitals(&v);

    if (v.probe == 0)//导联脱落
    {
        code = CO_EMCY_LEAD_OFF;
    }
    else if ((v.alarm & 0x01) != 0)  // 心率异常
    {
        code = (v.bpm > v.hr_hi) ? CO_EMCY_HR_HI : CO_EMCY_HR_LO;
    }
    else if ((v.alarm & 0x02) != 0)  // 呼吸异常
    {
        code = (v.rpm > v.rr_hi) ? CO_EMCY_RR_HI : CO_EMCY_RR_LO;
    }

    if (code == s_emcy_prev) { return; }

    s_emcy_prev = code;  // 0x1001 错误寄存器由它推出（见 Co_ObjRead）
    Co_SendEmcy(code);
}

// ---------------- SDO 服务端 ----------------
// 发 0x80 命令 + 中止码
static void Co_SdoAbort(uint16_t idx, uint8_t sub, uint32_t code)
{
    uint8_t d[8];

    d[0] = 0x80;
    d[1] = (uint8_t)(idx & 0xFF);
    d[2] = (uint8_t)(idx >> 8);
    d[3] = sub;
    Put32(&d[4], code);
    CAN1_Send_Msg(CO_COB_SDO_TX, d, 8);
    s_st.sdo_abort++;
}
// 发 0x60，表示"写成功"
static void Co_SdoReplyDownload(uint16_t idx, uint8_t sub)
{
    uint8_t d[8];

    d[0] = 0x60;
    d[1] = (uint8_t)(idx & 0xFF);
    d[2] = (uint8_t)(idx >> 8);
    d[3] = sub;
    d[4] = 0; d[5] = 0; d[6] = 0; d[7] = 0;
    CAN1_Send_Msg(CO_COB_SDO_TX, d, 8);
}
// 发数据
static void Co_SdoReplyUpload(uint16_t idx, uint8_t sub, const uint8_t *data, uint8_t len)
{
    uint8_t d[8];
    uint8_t i;

    if (len <= 4)  // 加速传输
    {
        d[0] = (uint8_t)(0x43 | ((4 - len) << 2));
        d[1] = (uint8_t)(idx & 0xFF);
        d[2] = (uint8_t)(idx >> 8);
        d[3] = sub;
        for (i = 0; i < len; i++) { d[4 + i] = data[i]; }
        for (i = len; i < 4; i++) { d[4 + i] = 0; }
        CAN1_Send_Msg(CO_COB_SDO_TX, d, 8);
    }
    else  // 分段上传：先回总长度
    {
        if (len > sizeof(s_seg_buf)) { Co_SdoAbort(idx, sub, 0x06010000); return; }
        memcpy(s_seg_buf, data, len);
        s_seg_len = len;
        s_seg_pos = 0;

        d[0] = 0x41;
        d[1] = (uint8_t)(idx & 0xFF);
        d[2] = (uint8_t)(idx >> 8);
        d[3] = sub;
        Put32(&d[4], len);
        CAN1_Send_Msg(CO_COB_SDO_TX, d, 8);
    }
}

static void Co_SdoRx(const uint8_t *d, uint8_t dlc)
{
    uint8_t  cs;
    uint16_t idx;
    uint8_t  sub;
    uint8_t  buf[24];
    uint8_t  len;
    uint8_t  remain, cnt, n, last, i;
    uint32_t abort;

    if (dlc < 4) { return; }

    cs  = d[0];
    idx = (uint16_t)(d[1] | ((uint16_t)d[2] << 8));
    sub = d[3];

    // 分段上传请求（主机催下一段）
    if ((cs & 0xF0) == 0x60)
    {
        if (s_seg_len == 0) { Co_SdoAbort(idx, sub, 0x05040001); return; }

        remain = (uint8_t)(s_seg_len - s_seg_pos);
        cnt    = (remain >= 7) ? 7 : remain;
        n      = (remain >= 7) ? 0 : (uint8_t)(7 - remain);
        last   = (remain <= 7) ? 1 : 0;

        buf[0] = (uint8_t)((n << 1) | last);
        for (i = 0; i < cnt; i++) { buf[1 + i] = s_seg_buf[s_seg_pos + i]; }
        for (i = cnt; i < 7; i++) { buf[1 + i] = 0; }
        CAN1_Send_Msg(CO_COB_SDO_TX, buf, 8);

        s_seg_pos = (uint8_t)(s_seg_pos + cnt);
        if (last != 0) { s_seg_len = 0; }  // 传完清忙标志
        return;
    }

    // 加速上传请求
    if (cs == 0x40)
    {
        s_st.sdo_rx++;
        len = 0;
        if (Co_ObjRead(idx, sub, buf, &len) != 0) { Co_SdoReplyUpload(idx, sub, buf, len); }
        else                                      { Co_SdoAbort(idx, sub, 0x06020000); }
        return;
    }

    // 加速下载
    if ((cs & 0xE0) == 0x20)
    {
        s_st.sdo_rx++;
        if ((cs & 0x02) == 0)  // e=0 → 分段下载，不支持
        {
            Co_SdoAbort(idx, sub, 0x05040001);
            return;
        }
        n = (uint8_t)((cs >> 2) & 0x03);
        abort = Co_ObjWrite(idx, sub, &d[4], (uint8_t)(4 - n));
        if (abort == 0) { Co_SdoReplyDownload(idx, sub); }
        else            { Co_SdoAbort(idx, sub, abort); }
        return;
    }

    Co_SdoAbort(idx, sub, 0x05040001);  // 命令无效
}

// ---------------- NMT 从站 ----------------
static void Co_ResetDefaults(void)
{
    s_hb_time    = 1000;
    s_tpdo_cob   = CO_COB_TPDO1;
    s_tpdo_trans = 254;
    s_tpdo_inhib = 0;
    s_tpdo_timer = 1000;

    s_tpdo_map[0] = 0x21000110;
    s_tpdo_map[1] = 0x21000210;
    s_tpdo_map[2] = 0x21000308;
    s_tpdo_map[3] = 0x21000408;
    s_tpdo_map[4] = 0x21000508;
    s_tpdo_mapn   = 5;

    s_seg_len    = 0;
    s_tpdo_prevn = 0;
    s_emcy_prev  = CO_EMCY_NONE;
}

static void Co_NmtRx(const uint8_t *d, uint8_t dlc, uint32_t now)
{
    uint8_t cmd, node, b;

    if (dlc < 2) { return; }
    cmd  = d[0];
    node = d[1];
    if ((node != 0) && (node != CO_NODE_ID)) { return; }

    s_st.nmt_cmd++;

    switch (cmd)
    {
    case CO_NMT_CMD_START:
        s_nmt = CO_NMT_OPERATIONAL;
        s_tpdo_t = now;
        break;

    case CO_NMT_CMD_STOP:
        s_nmt = CO_NMT_STOPPED;
        break;

    case CO_NMT_CMD_PREOP:
        s_nmt = CO_NMT_PREOP;
        break;

    case CO_NMT_CMD_RSTNODE:
    case CO_NMT_CMD_RSTCOMM:
    case CO_NMT_CMD_RSTAPP:
        Co_ResetDefaults();
        s_nmt = CO_NMT_PREOP;
        b = CO_NMT_BOOTUP;  // 复位后重发 Boot-up
        CAN1_Send_Msg(CO_COB_HEARTBEAT, &b, 1);
        s_st.hb_tx++;
        break;

    default:
        return;
    }

    Co_SendHeartbeat();  // 立刻回一次，主机不等周期
    s_hb_t = now;
}

static void Co_ProcessRx(const CanFrame_t *f, uint32_t now)
{
    if (f->id == CO_COB_NMT)        { Co_NmtRx(f->data, f->dlc, now); }
    else if (f->id == CO_COB_SDO_RX) { Co_SdoRx(f->data, f->dlc); }
    // SYNC / 其它帧本节点不使用，忽略
}

// ---------------- 对外接口 ----------------
void CanOpen_Init(void)
{
    uint8_t b;

    CAN1_Config();
    s_selftest = CanOpen_SelfTest();  // 回环自测：不发总线也能验证驱动整条链路
    Co_ResetDefaults();

    s_nmt    = CO_NMT_PREOP;
    s_hb_t   = 0;
    s_tpdo_t = 0;
    s_tpdo_last = 0;
    memset(&s_st, 0, sizeof(s_st));

    b = CO_NMT_BOOTUP;  // 上电 Boot-up 心跳
    CAN1_Send_Msg(CO_COB_HEARTBEAT, &b, 1);
    s_st.hb_tx++;
}

void CanOpen_Task(uint32_t now_ms)
{
    static uint32_t s_tick;
    CanFrame_t f;

    if (now_ms == s_tick) { return; }  // 10ms 时基未变，不重复处理
    s_tick = now_ms;

    while (CAN1_Recv_Msg(&f) != 0)
    {
        Co_ProcessRx(&f, now_ms);
    }

    // 心跳：Pre-op / Operational / Stopped 都发
    if ((s_hb_time != 0) && ((now_ms - s_hb_t) >= s_hb_time))
    {
        s_hb_t = now_ms;
        Co_SendHeartbeat();
    }

    if (s_nmt != CO_NMT_STOPPED) { Co_EmcyTick(); }
    if (s_nmt == CO_NMT_OPERATIONAL) { Co_TpdoTick(now_ms); }
}

uint8_t CanOpen_GetNmtState(void)
{
    return s_nmt;
}

void CanOpen_GetStats(CoStats_t *s)
{
    if (s != 0) { *s = s_st; }
}

// 回环自测：切内部回环发一帧（ID 0x123，不过总线、不用接线），等它回到接收端，
// ID/长度/内容全对才算过；结束自动切回 Normal（SetMode 已修复中断重配，可放心调用）
uint8_t CanOpen_SelfTest(void)
{
    uint8_t buf[8];
    CanFrame_t f;
    uint32_t n;
    uint8_t i;
    uint8_t ok = 0;

    for (i = 0; i < 8; i++) { buf[i] = (uint8_t)(0x10 + i); }

    CAN1_SetMode(CAN_Mode_LoopBack);
    if (CAN1_Send_Msg(0x123, buf, 8) == 0)
    {
        for (n = 0; n < 3000000; n++)  // 约 50ms 超时，回环实际微秒级就到
        {
            if (CAN1_Recv_Msg(&f) != 0)
            {
                ok = (uint8_t)((f.id == 0x123) && (f.dlc == 8) &&
                               (memcmp(f.data, buf, 8) == 0));
                break;
            }
        }
    }
    CAN1_SetMode(CAN_Mode_Normal);
    return ok;
}

uint8_t CanOpen_GetSelfTest(void)
{
    return s_selftest;
}
