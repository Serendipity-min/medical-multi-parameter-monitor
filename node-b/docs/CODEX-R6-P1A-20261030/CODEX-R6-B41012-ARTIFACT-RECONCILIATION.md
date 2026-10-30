# B41012 同次构建身份对账

唯一新增构建目录：`node-b/build/b4-arm-20261030T075345488870Z`。不是从两次旧构建挑选产物拼接。原命令 `python -X utf8 -B node-b/tools/build_b4_arm.py --temp --candidate-r6`，真实退出0，Keil/ARMCC5.06u7 build960，0错误/0警告。

| 同次产物 | 字节 | SHA256 |
|---|---:|---|
| B5_TEMP_NODE_B.bin | 41012 | 1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d |
| firmware/OBJ/BIO_V2.axf | 811816 | 420b72333690b347349f353b9f5d94184e239bec989b663034c586087f603805 |
| symbols.txt | 108998 | e9b54c3837924b52a7f23c891a396d0a5d6b529d11eb9bf26cfa55b0cbf31aea |
| firmware/USER/Listings/BIO_V2.map | 282332 | c51e39163b8b58ab7894c873698354576db816241546d4d7c374f3192253faf6 |
| firmware/build.log | 1552 | 40209164ba1c4df2f62317adc9f44e16e8c3848587ea6ebcf911ef9c3d67ccf9 |
| hr_page.candidate.c及实际编译源码 | 各41042 | f7e6bc7e052660589f83ae6b04e0df0d0090421f39cd619eabfda3dbd06f6daf |

回执包含完整编译输入SHA清单、工具SHA、构建器原件和资源：Code37388、RO3148、RW1492、ZI19172。新BIN和生成源码分别与既有归档逐字节一致；旧14项清单/制品未覆盖。完整链见 `integrity-03.json`。

旧两次AXF分别为e11219c4…/3e9d4d32…，新AXF又为420b7233…。进一步只读比较已定位：所有可加载节和.comment以外的整个文件字节相同；差异仅为非加载.comment中的编译临时标识及记录顺序，注释token归一后的多重集合相同。符号表仅构建目录名称归一后即相同，全部编译输入SHA也相同。详见artifact-file-comparison-02/03，先保留严格顺序检查exit1，再保留定位后比较exit0。归一化仅用于解释，不改原文件或原始SHA。

未将新AXF/symbols替换到原R6 Profile：其引用仍是历史e11219c4…/07e2166e…。PI未来须选择并冻结完整一致的调试制品链，不能因内容解释清楚便自动替换身份。

应用BIN复现不等于硬件合格；未安装候选、未读当前板。B40928B原部署未动。回滚材料仍仅为既有历史恢复原件，未执行新恢复或制造新全片指纹。

## WCET证据界限

八锚点在冻结源中各命中一次，生成源码与编译输入一致。但FrameFeed包含FIFO耗尽、BioV2_Process、BCan_Sample、CanOpen_Task及同步GraphChannelDataAdd；串口SendChar存在无本地超时的TXE/TC等待。Python模型零成本出队不覆盖这些真实工作。模型0越界只能记 `WCET_MODEL_ONLY`，实际CPU最坏耗时、队列/采样在真实负载下的连续性均 `NOT_MEASURED`。详见 [静态证据分析](audit-context/EVIDENCE-DOSSIER.md)。
