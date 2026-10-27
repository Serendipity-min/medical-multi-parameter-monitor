# AUTH-B5-R-APP-001 R2｜配置先恢复后，仅恢复C24104应用

`enabled=false; owner_approved=false; executions=0`。单独批准，不是安装/配置/云窗的自动收尾。

1. 要求R-CFG先独立通过，全片before=`3eaf583a703137b09665da5d2bfd7e860cd3a2208bf659b631d7ee4d0541545c`，即B5应用＋原sector3。ESP保持电气隔离；C运行/UID/保护/完整Flash/options核验合格，否则停。ROM/HALT不自动复位。
2. 使用G2-RO新鲜应用包manifest `3782fc9caa0f921cc51001191df0ac90e2633710e89f56bae017d2e3d35e73fc` 和冻结应用安装/恢复器，scope=`B5_C_SECTOR012_MOCK_INSTALL_OR_RESTORE_NO_CONFIG_WRITE`，phase=restore。独立一次EFS授权必须绑定工具/DLL/SHA、输出、有效期、现场条件与本卡，不能复用G2-A授权。
3. 仅恢复sector0/1/2整49152B原件，不写配置、options、sector7/11或其他区；无整片擦除或解保护。单连接180秒，halt/download/reset/go各≤1、不重试。全片/options/身份符合目标后才正常器件reset≤1、真实PC/MSP匹配Flash向量后Go≤1。
4. after=`b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98`；options=`52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`；sector3=`1698c8783b4fbdd1bc7fc5a8641babc7b499b58a65be54e7b36c65c6c5b88313`。全片字节一致才签本目标恢复PASS。

默认目标为10月26日真实读回的**C24104检查点**，不是历史H3，也不恢复正式联网。若PI另要H3，必须另绑对应完整镜像/配置及电气准入，不能换目标继续用本卡。云账号撤销使用原独立R-CLOUD卡，仍未授权。
