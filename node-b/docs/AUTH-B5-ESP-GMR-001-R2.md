# AUTH-B5-ESP-GMR-001 R2｜一次人工正常复位后的版本查询，待批准

`enabled=false; owner_approved=false; executions=0`。R1实际在入口ROM停止，AT/GMR发送0，未读完整Flash，未复位/烧录；实际源码与两份ROM快照均保留，不能冒称已确定当前ESP版本。R1许可已消费。

本卡完整沿用[R1的固定AT/GMR权限、地址、115200/8N1、12字节上限和180秒监督](AUTH-B5-ESP-GMR-001-R1.md)，只增加**负责人仅短按C实体RESET一次**作为新事务的前置。当前J-Link已在C、C J5供电、B断电、C USB_UART断开；其他接线及ESP在板供电保持不变，不再冷转接，不重刷，不强设任何核心寄存器。

当前所有调试和串口会话均关闭。负责人批准本卡并实际完成一次C人工RESET后，才创建一笔新的单会话查询。若真实PC/VTOR仍在ROM、HALT或身份/保护/Flash异常，立即Close，不追加快照、不发AT、不再复位。复位恢复正常也只意味着可以继续查询，不意味着ROM根因已关闭。

R2修正了R1异常收尾在入口ROM后又读一份快照的问题：只有已进入UART查询后的纯协议失败才做健康收尾；ROM、SDK错误和短读不触发补读或恢复。R1原始行为及真实退出码不改写。新工具SHA、14项定向离线验证和禁用许可见[B5-ESP-GMR-R2-PREP](../evidence/B5-ESP-GMR-R2-PREP/bindings.json)。

仍仅向UART_DR写固定AT一次，成功后GMR一次；UART波特率/控制、GPIO、Flash/options/sector3、RAM、CPU控制均不写，工具显式halt/go/reset=0。原始响应仅存受限EFS；完整Flash/options前后匹配及DISARMED不变才签版本读取PASS。若未读到GMR，仍记UNKNOWN；不得为得到版本增加命令、变波特率、刷ESP或重启G3。

请只在批准后短按C RESET一次并回复完成事实，不接C USB、不动B/J-Link/CAN/P5/P7/BOOT。查询结束不自动恢复H3、配置或云端资源；已失败的G3保持原结果。
