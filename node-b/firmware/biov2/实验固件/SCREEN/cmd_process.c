/**
 * @file    cmd_process.c
 * @brief   屏指令分发 + 事件回调：把屏发来的帧拆成事件，转给 hr_page
 *
 * ProcessMessage 在官方例程里放在 main.c，这里独立成文件，main.c 保持精简。
 * 屏 -> MCU 的帧格式：EE <cmd_type> ... FF FC FF FF，由 cmd_queue.c 切帧。
 */
#include "cmd_process.h"
#include "hr_page.h"
#include "ulitity.h"

/*!
*  \brief  指令分发：按 cmd_type 拆帧，转成各 Notify 回调
*/
void ProcessMessage(PCTRL_MSG msg, uint16 size)
{
    uint8  cmd_type     = msg->cmd_type;
    uint8  ctrl_msg     = msg->ctrl_msg;
    uint8  control_type = msg->control_type;
    uint16 screen_id    = PTR2U16(&msg->screen_id);   // 帧内多字节整数均为大端序
    uint16 control_id   = PTR2U16(&msg->control_id);
    uint32 value        = PTR2U32(msg->param);

    (void)size;

    switch (cmd_type)
    {
    case NOTIFY_TOUCH_PRESS:
    case NOTIFY_TOUCH_RELEASE:
        // 触摸帧没有 screen/control 字段，x/y 从偏移 2 起（与官方例程一致）
        NotifyTouchXY(msg->cmd_type, PTR2U16((uint8 *)msg + 2), PTR2U16((uint8 *)msg + 4));
        break;

    case NOTIFY_WRITE_FLASH_OK:     NotifyWriteFlash(1); break;
    case NOTIFY_WRITE_FLASH_FAILD:  NotifyWriteFlash(0); break;
    case NOTIFY_READ_FLASH_OK:      NotifyReadFlash(1, (uint8 *)msg + 2, size - 6); break;   // 数据从偏移2起；长度=总长-帧头1-命令字1-帧尾4
    case NOTIFY_READ_FLASH_FAILD:   NotifyReadFlash(0, 0, 0); break;

    case NOTIFY_READ_RTC:           // RTC 数据从偏移 2 起，BCD 码
        NotifyReadRTC(((uint8 *)msg)[2], ((uint8 *)msg)[3], ((uint8 *)msg)[4],
                      ((uint8 *)msg)[5], ((uint8 *)msg)[6], ((uint8 *)msg)[7],
                      ((uint8 *)msg)[8]);
        break;

    case NOTIFY_CONTROL:
        if (ctrl_msg == MSG_GET_CURRENT_SCREEN)    // 画面 ID 变化通知，帧里不带控件字段
        {
            NotifyScreen(screen_id);
        }
        else
        {
            // 状态在 param[1]（指令集 2.15/2.19），param[1]=FF 的是无 Subtype 的帧
            uint8 bst = msg->param[1];

            if (bst == 0xFF) { bst = msg->param[0]; }

            // 按控件类型二次分发，统一带 screen_id/control_id 供业务层定位控件
            switch (control_type)
            {
            case kCtrlButton:    NotifyButton(screen_id, control_id, bst); break;
            case kCtrlText:      NotifyText(screen_id, control_id, msg->param); break;
            case kCtrlProgress:  NotifyProgress(screen_id, control_id, value); break;
            case kCtrlSlider:    NotifySlider(screen_id, control_id, value); break;
            case kCtrlMeter:     NotifyMeter(screen_id, control_id, value); break;
            case kCtrlMenu:      NotifyMenu(screen_id, control_id, msg->param[0], msg->param[1]); break;
            case kCtrlSelector:  NotifySelector(screen_id, control_id, msg->param[0]); break;
            case kCtrlRTC:       NotifyTimer(screen_id, control_id); break;
            default: break;
            }
        }
        break;

    case NOTIFY_HandShake:
        NOTIFYHandShake();
        break;

    default:
        break;
    }
}

// ================= 事件回调（转给 hr_page 业务层） =================

void NotifyScreen(uint16 screen_id)
{
    HrPage_NotifyScreen(screen_id);
}

void NotifyButton(uint16 screen_id, uint16 control_id, uint8 state)
{
    HrPage_OnButton(screen_id, control_id, state);
}

void NotifyReadRTC(uint8 year, uint8 month, uint8 week, uint8 day,
                   uint8 hour, uint8 minute, uint8 second)
{
    (void)week;
    HrPage_OnRtcTime(year, month, day, hour, minute, second,
                     timer_tick_count * 10);   // 屏RTC只到秒，毫秒位用本地节拍(10ms)补
}

// ---- 本工程用不到的回调，留空 ----
void NOTIFYHandShake(void) {}
void NotifyTouchXY(uint8 press, uint16 x, uint16 y)
{ (void)press; (void)x; (void)y; }
void NotifyText(uint16 screen_id, uint16 control_id, uint8 *str)
{
    HrPage_OnText(screen_id, control_id, str);
}
void NotifyProgress(uint16 screen_id, uint16 control_id, uint32 value)
{ (void)screen_id; (void)control_id; (void)value; }
void NotifySlider(uint16 screen_id, uint16 control_id, uint32 value)
{ (void)screen_id; (void)control_id; (void)value; }
void NotifyMeter(uint16 screen_id, uint16 control_id, uint32 value)
{ (void)screen_id; (void)control_id; (void)value; }
void NotifyMenu(uint16 screen_id, uint16 control_id, uint8 item, uint8 state)
{ (void)screen_id; (void)control_id; (void)item; (void)state; }
void NotifySelector(uint16 screen_id, uint16 control_id, uint8 item)
{ (void)screen_id; (void)control_id; (void)item; }
void NotifyTimer(uint16 screen_id, uint16 control_id)
{ (void)screen_id; (void)control_id; }
void NotifyReadFlash(uint8 status, uint8 *_data, uint16 length)
{ (void)status; (void)_data; (void)length; }
void NotifyWriteFlash(uint8 status)
{ (void)status; }
