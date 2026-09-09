# 修复移动脚本 Windows PowerShell 编码错误

## 根因

`move_candidates_to_removable_folder.bat` 使用 Windows 自带的 `powershell.exe`（PowerShell 5.1）运行脚本。该版本会将**不带 UTF-8 BOM** 的 `.ps1` 文件按系统 ANSI 代码页读取。移动脚本包含中文提示和用于筛选 CSV 的 `可删除候选` 字符串，结果 UTF-8 字节被错误解码、引号结构被破坏，从而在脚本解析阶段报 `Unexpected token` 等语法错误。

已通过以 `powershell.exe -NoProfile -NonInteractive -File` 直接运行脚本复现；错误发生在任何文件移动之前。

## 实施步骤

1. 将 `scripts/move_candidates_to_removable_folder.ps1` 保存为 **UTF-8 with BOM**。
   - 保留现有自动定位固定报告、路径边界校验、候选筛选、预览、确认和审计逻辑。
   - 不更改候选视频，不执行实际移动。

2. 验证 Windows PowerShell 5.1 的实际执行路径。
   - 使用与 BAT 相同的 `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File` 解析并运行脚本。
   - 预期不再出现 `Unexpected token` / 乱码语法错误；非交互环境可能在确认输入处停止，这是预期的，并且在确认前不应移动任何文件。

3. 再次运行 PowerShell 语法检查和 `git diff --check`，确认修复没有引入其他问题。
