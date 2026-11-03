# M0 原三板接线与职责

本轮不搬动传感器或屏。A42608：HKB-08B+及血氧组件/两屏；B41516：ECG/RESP、GY641及HR/RR/独立温度屏；C：双CAN、ESP、MIC及TW-TTS。

- B+C：B.CAN1 ↔ C.CAN2；A断电且总线隔离。
- A+B+C：A.CAN1 ↔ C.CAN1，B.CAN1 ↔ C.CAN2，两段独立500kbit/s总线。
- 每段收发器H对H/L对L/参考地，两端120Ω。历史约60Ω；本轮实际确认另记。线长、支线、线材和收发器精确型号当前UNKNOWN，不推定距离能力。
- ECG60：R→RA、L→LA、F→RL；RR18：断电后L→LL；仅SKX非人体、电池且充电USB断开。
- GY641及独立温度屏沿用B原接线（屏USART3 PB10/PB11），探头对桌面。
- C MIC：VCC→3V3、GND→GND、L/R→GND、WS→PA4、SCK→PC10、SD→PC12；100nF及100kΩ已由负责人核实。TTS沿用PA2/PA3及既有供电/喇叭。
- 运行窗口J-Link只在B；C以原USB_UART观察，不用USB_OTG。A/B固件不修改。
- 血压只由负责人在已确认安全非人体气路手动启动；不自动充气。

最终现场：负责人确认A/B/C及模块全部断电熄灭，C USB_UART及J-Link电脑端USB已拔；J-Link板端留B。两段CAN仍接，黄L留LL，R→RA/F→RL。最后刺激为RR18、独立波形周期30、1.5R、窒息0。TTS模块与喇叭已分开放置，电气接线未改；磁场影响未证实。SKX及手机热点最终开关未单独确认。
