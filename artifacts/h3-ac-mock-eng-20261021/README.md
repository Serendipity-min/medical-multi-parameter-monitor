# H3 A→C 工程固件冻结

**NON-HUMAN MOCK ONLY / NOT CLINICALLY CALIBRATED**

本包为既有 H3 验收二进制的原件复制，未重新编译、烧录或测量。基线为 `1878994f57a4c07263b4898d223ba810aa88210a`，冻结标签为 `h3-ac-mock-eng-20261021-r1`。具体字节数、SHA256、向量和编译器见 `firmware-manifest.json`，核验命令为 `sha256sum -c SHA256SUMS.txt`。

| 应用 | 目标与大小 | 作用范围 |
|---|---|---|
| node-a-h3ac-final.bin | Node-A / STM32F407ZGT6 / 50084B | A 自己的应用 sector0–3 |
| gateway-c-h3ac-8883-mock-final.bin | Gateway-C / STM32F407ZGT6 / 43172B | C 自己的应用 sector0–2，正式8883，MOCK/synthetic |

A/C是不同MCU。严禁对调镜像；C包不含sector3配置、Wi-Fi/MQTT凭据、完整Flash、sector7/11或options。应用BIN本身不能独立恢复C的持久网络身份；必须由负责人保管私有加密恢复包。此包不授予任何以后烧录权，恢复时重新核对角色/芯片身份、双读原件、保护区及精确扇区授权，不全片擦除。

配对协议包含0x281完成tick、0x381 SYS/DIA镜像、0x481 TIME锚及0x681扩展/有效位；NIBP从完成时间计龄，严格超过90000ms无当前值，启动会话变化不得复活旧结果。验收PPG连续359.701秒；PPG/SpO2/PR三流共同有效最长203.832秒。未验证临床精度、测试源校准或长期可靠性。

本轮不合并P4/B，也不启动B开发。未来B须独立工作区及B-H0/H1/H2准入，再经批准从P4建立integration/p4-h3-nodeb，明确合入本标签及B冻结提交。三板联调前重新检查Node-ID/PDO、500kbps、两端各120Ω（仅两个终端，断电跨H/L通常约60Ω）、公共参考地和独立供电；禁止三块板各120Ω直接并联。A移除后OFFLINE及读数隐藏是预期，不补数据假装在线。

正式8883仍需要已配置2.4GHz路由器/WAN及授时/TLS；网页静态壳与监护WSS/AI的独立鉴权不可混同。8884结项验证和残余风险以唯一新报告 `doc/H3/H3-AC-POSTCLOSE-ARCHIVE-AND-8884-VERIFICATION.md` 为准，原H3工程PASS不等于本轮全面安全PASS。
