# 自动移动候选并移除审计输出

## 目标

双击候选移动 BAT 后，立即根据当前固定检查报告移动合格候选，不要求输入确认文本，也不生成移动审计 CSV。用户已明确授权这项移动操作。

## 实施步骤

1. 精简 `scripts/move_candidates_to_removable_folder.ps1`。
   - 移除确认前缀、`Read-Host`、取消分支、审计行构造函数、审计列表和所有 `Export-Csv` 调用。
   - 保留自动定位当前固定报告、仅选择 `status=ok` / `result=可删除候选`、源/目标边界校验、重复路径排除、源不存在静默跳过、目标冲突不覆盖、目录创建和 `Move-Item`。
   - 对每个实际移动或失败继续在控制台打印结果；结束时打印移动、已不存在、目标已存在、其他跳过与失败的汇总，但不写入任何移动报告。
   - 保留失败隔离，单个文件移动失败不会阻断其余候选。

2. 更新 `move_candidates_to_removable_folder.bat`。
   - 删除预览和精确确认文本提示。
   - 明确提示：脚本会立即按当前报告移动候选至可删除文件夹。

3. 更新配置说明与文档。
   - 在 `config.json`、`README.md`、`docs/CONFIGURATION.md`、`docs/DEPLOYMENT.md` 和 `docs/AGENT_PROMPT.md` 中移除确认文本、预览和审计 CSV 说明。
   - 保留人工复核检查报告的建议，以及“不覆盖、跳过缺失源文件、可删除目录排除扫描”的行为描述。

4. 验证。
   - 通过 PowerShell 5.1 语法验证脚本并确认其仍是 UTF-8 with BOM。
   - 以隔离的临时文件和固定 CSV 夹构造小型测试，验证候选会直接移动、非候选不会移动、且不会创建 `move_to_removable_audit_*.csv`。
   - 不对当前 20260906 的真实候选运行脚本。
   - 运行 Python/JSON 验证（如受影响）和 `git diff --check`。
