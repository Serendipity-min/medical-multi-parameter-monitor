# G2-A R2现场豁免附件｜ESP保持在板

本附件只补充唯一应用申请卡 `AUTH-B5-G2A-FRESH-001-R2.md`，不替换其42552B候选、三扇区、180秒和异常停止边界。

负责人先要求“ESP8266暂不移除开发板，执行完G2A进行G2BMEM-AP桥”，随后对精确范围答复“批准豁免”：本次ESP保持现状供电，仅安装C sector0/1/2一次，sector3/options/sector7/11不写，不发AT/B5START、不启动云服务；安装启动须保持DISARMED，通过后仅做SDK与原始DAP只读交叉核验。

因此本次如实记 `ESP_isolated=false / ESP_isolation_waived_by_owner=true`。模块自主联网状态仍UNKNOWN；软件不发AT不等于模块已电气隔离。板图第5页P1 VCC/CH_PD直连3.3V的事实保留；先前冷态拔模块的电气附件未批准、未执行，本轮不拔ESP。

## 独立的一次事务

| 事务 | 一次性scope与限制 |
|---|---|
| 应用安装 | `B5_G2A_C012_OWNER_ESP_PRESENT_POWERED_EXCEPTION`；仅install，不含restore。完整before/options/UID/运行合格后，halt/download/reset/go各≤1，180秒、不重试；全片符合预期才正常器件reset及真实PC/MSP入口核对，最后实际读B5状态4B全零 |
| MEM-AP只读核验 | `B5_G2B_MEMAP_READONLY_NO_HALT_NO_FLASH_UNLOCK`；仅G2-A真实通过且DISARMED后启用，独立连接/输出/180秒。仅AP SELECT/CSW/TAR传输设置，禁DRW写及一切目标内存/Flash控制写；显式halt/reset/go、KEYR/擦除/编程均0 |

新入口 `node-b/tools/b5_g2_site.py`复用冻结的 `b4_swd_install.execute/InstallLink` 与已审MEM-AP桥；不改旧工具的ESP门禁、不把false改成true，不改BIO_V2或固件。新增入口默认禁用，真实私有授权绑定原R2卡、工具/DLL、既有42552B包、当前C只读证据、豁免事实、有效期和唯一EFS输出；本附件通过本轮冻结清单关联，不追溯改写已消费的授权。旧安装卡不能消费此新scope，配置写入器也不能消费本次只读许可。

新增门禁的8项必要离线检查通过，不重跑既有27项writer、3项配置C校验或Host/ARM/TLS/UI矩阵。真实工具SHA、授权SHA、返回与执行结果见本轮 `node-b/evidence/B5-G2A-ADMISSION/`；私有UID/原件/配置/SDK日志仅EFS。

## 保持未授权

G2-B sector3真实写入、R-CFG/R-APP实际恢复、G1独立服务启动、G3 B5START及云窗、R-CLOUD撤销均未批准。本次ESP豁免不自动扩展到这些后续事务，也不能由只读桥通过推导已具备配置写入权限。

任何ROM/HALT/意外复位、UID/Flash/options漂移、原生错误或期限不足即停止并保留原件，不追加复位、下载或恢复。正常安装后工具计划内的一次暂停/复位不冒称CPU根因实验；CPU ROM根因继续UNRESOLVED。
