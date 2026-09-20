# 调用与项目适配

集中执行器位于本技能根目录向上查找到的 `tools/security_gate`。在 Windows 中由 `gate.py` 经系统目录下的 wsl.exe 转到 HERA-C3；Linux/CI 直接调用 Python 3.11+。

```text
python scripts/invoke.py doctor --repo <project>
python scripts/invoke.py quick --repo <project> --authorize
python scripts/invoke.py pr --repo <project> --profile <profile.json> --base <commit> --authorize
python scripts/invoke.py release --repo <project> --dry-run
```

仅已有授权时使用扫描示例。`--profile medical-monitor` 只适配医疗项目；其他项目在 `.security-gate.json` 配置 source_roots、requirements、npm_roots、first_party_c、compile_capture 和 commands。构建使用独立快照；测试解释器由 `prepare.py` 准备，不修改项目运行 venv。

完整安装、CI、人工 checklist、导出说明由执行器 README 维护。
