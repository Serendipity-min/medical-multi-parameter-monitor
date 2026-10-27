# AUTH-B5-G2B-SECTOR3-001 R3｜已连接MEM-AP流程、ESP在板，待独立写入批准

`enabled=false; owner_approved=false; executions=0`。本卡替代R2作为下一轮配置写入申请，R2与历史源码原件保留。G2-A实际安装及MEMAP第二只读窗口已通过；本轮只有离线改动，没有新实板连接。ESP保持在板供电，ESP_isolated=false，自主联网状态UNKNOWN。当前批准仅准备，不是写入许可。

## 字节与工具绑定

私有位置由忽略指针 `node-b/build/b5-g2b-package-private-pointer.json` 引用，明文凭据/UID/主机不放Git。配置包绑定SHA `20cba97d9587fd50f6ad9a98a19efc2812c62675e1304c646d88e771b9d2c73f`；原规划manifest SHA `082d3f89a251d1ad163ee36ad5e03f104d62eae948d2dec685ab1f1370e7236e`。写入器、protocol、独立监督器、依赖及DLL逐一绑定本轮 `node-b/evidence/B5-G2B-CONNECTED-PREP/bindings.json`；未来一次性授权必须完全匹配，不能仅指向可变文件名。

| 对象 | SHA256 |
|---|---|
| 原整sector3 | `1698c8783b4fbdd1bc7fc5a8641babc7b499b58a65be54e7b36c65c6c5b88313` |
| 新336B已提交记录 | `d098b53c8126832b38c2f91103dbc20ccff2d239a2618c8db0701ee00178d459` |
| 未提交整sector3 | `1154c71eddde32a90dc0c6c5825494ebaebe02979b125968789acf6d4e3a0049` |
| 已提交整sector3 | `260dba9243272dfa2f678a688b0f772e2dace3d41eff84e5d1ce9e3ab9f72dfc` |
| 写前全片，要求G2-A已通过 | `3eaf583a703137b09665da5d2bfd7e860cd3a2208bf659b631d7ee4d0541545c` |
| 未提交全片 | `259e366b6174e35fd53d33f1548dc721278ab3ac977fc298989488097c3f6fa1` |
| 写后全片 | `acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e` |
| 前后options，16B不写 | `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687` |

312B payload＋24B头全量重建，generation3→4，CRC与committed均由固件原C函数离线核验。仅在内存复用适用WiFi字段；云角色固定 `b5-gateway / b5-c-isolated / GW-B5-001 / 8883`，不得用GW-C-001。最低纪元已冻结在私有包，它是接受下界，不能当实时授时。sector3尾部16048B保留。

## 必须另获批准后才能执行

1. 负责人明确批准本卡及一次EFS授权，scope=`B5_G2B_SECTOR3_CONNECTED_CONTEXT_ESP_PRESENT`，phase=provision，entry_runtime_state_hex=`00000000`，绑定包/前后SHA、工具/DLL、C身份、最新现场附件、有效期、唯一输出。当前没有可执行的真实一次性授权实例；单元测试中的合成授权不具实板权限。
2. 新上电状态核对另获现场授权；ESP保持在板供电；未来批准须同时明确批准此次配置写入的ESP非隔离例外，不能复用G2-A豁免。私有授权须含ESP_isolated=false、ESP_present_powered_exception_approved=true、ESP_exception_scope=本卡scope；现场附件ESP_present_powered=true、ESP_isolated=false、ESP_autonomous_network=UNKNOWN。C供电稳定、J-Link在C，A/人体断开，USB/CAN/BOOT/RESET状态冻结。ROM/HALT/意外复位或新鲜原件漂移即停止，不复位、不重刷。原10月26日双备只作检查点，写前两次完整1MiB及两次16B options必须真正独立读取且一致。
3. 正常运行、C UID/保护、RDP、sector3 WRP、Flash控制状态、3.0–3.6V探针VTref、已冻结HSE8MHz/HCLK分频条件通过；先确认42552B与DISARMED，halt≤1后再确认DISARMED。sector7/11/应用/options不改，绝不解除保护。VTref不冒称精确VDD标定。
4. 已连接上下文的MEM-AP读路径在MEMAP_READONLY_02实际通过，raw Flash编程仍未验证。禁止CORESIGHT_Configure；IsConnected必须为1，CPUID/Flash头/CR/SR四项SDK基线全部读完后才进入原始DAP，禁止重新Connect。本次未来事务仍须在暂停状态只读比较AP IDR、CPUID、Flash前64B及控制寄存器与SDK读值；不一致在任何KEYR/擦写前停止。DP offset8读为RESEND，不能冒充SELECT；退出恢复CSW/TAR并规范化AP0/bank0。
5. 只擦sector3 `[0x0800C000,0x08010000)`一次；关闭/复位Flash数据缓存后再编程与验证。逐32位写绑定的未提交sector（跳过全FF字、offset20提交字）；整16KiB及CRC/尾部正确且保留至少110秒预算后，最后只写一次 `0x0800C014=0x54494D43`。预算不足则保持未提交并停止，不延长180秒，不承诺最坏SDK延迟下仍能完成。高层Download/Flash写接口均0，不触OPTKEYR/OPTCR，不写其他NVM地址。
6. 锁回Flash控制器，双读全片/options、核对身份及所有保护区；恢复原ACR。通过才允许普通器件reset≤1、真实PC/MSP与向量匹配后Go≤1，验证DISARMED。B5START/AT命令均0；不主动驱动ESP联网，但不能据此声明模块自主联网为0。单会话180秒独立硬停、重试0；每个原生返回、单调时间、在途API及消息指纹均记录。原生错误与非负短读分别裁定；原始DAP错误后停止锁生效，finally也不再发AP/DP清理访问。
7. 失败不自动修复NVM或回滚。仅在仍暂停、链路健康、没有原生错误/回调错误且非busy时，允许本卡内的PG清除/CR重锁及安全恢复原ACR；不含再次擦写、reset/go。监督器强杀后目标状态UNKNOWN，禁止重连清理。部分写状态须另读回、重新绑定与批准，不能套用完整成功态恢复包。

完成仅裁定配置字节与DISARMED启动，不裁定TLS/ESP可用、冷启动、CPU根因或真实上云。恢复顺序见[独立R-CFG](AUTH-B5-R-CFG-001-R3.md)，之后才可另批R-APP。

## 一次性启用附件

写入器SHA256 `5464387e61ecbd1d109539996e06648a0e47d0ac601f674a3e1d449a045e0c3d`。独立监督器仍为冻结的180秒实现，protocol/cache/提交字状态机未改；完整依赖见新bindings。card_sha256必须等于本卡文件字节SHA，不能指向R2或旧安装卡。授权须在PI明确批准后独占生成于受限EFS，含有效期、输出目录、现场附件SHA、完整工具/DLL与包绑定。`.used`独占消费一次，失败不再生成同窗许可。当前没有启用授权，不能用合成测试许可连接实板。

应用42552B不变，sector3只是本轮唯一NVM范围；G2-B成功也不自动执行G1-RESUME/G3/R-CFG/R-APP/R-CLOUD。ESP电气例外也不授权实际网络业务。
