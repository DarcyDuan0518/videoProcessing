# 简化报告与候选移动流程

## 目标

将每个源视频目录的报告固定为一个不带时间戳的 CSV；下一次成功完成识别时覆盖同一路径的旧报告。候选移动脚本不再要求在配置中填写报告路径，也不要求传入命令行参数，而是按当前 `launch` 配置自动读取该固定报告。

## 实施步骤

1. 更新 `video_sorter.py` 的配置模型与报告路径逻辑。
   - 删除已不再使用的 `launch.report_name_prefix` 和 `deletion.report_path` 默认项及其校验。
   - 省略 `--output-dir` 时直接使用 `launch.output_dir`，不再创建时间戳子目录。
   - 将报告命名固定为 `report_<源视频目录名>.csv`，例如 `reports\report_20260906.csv`。
   - 保留命令行 `--output-dir` 覆盖能力；在指定的输出目录中使用同一稳定文件名。
   - 在全部结果已生成后才替换报告文件，避免识别中断或失败时清空上一份完整报告；成功运行会直接以新报告覆盖旧报告。
   - 更新命令行帮助与控制台说明，说明报告会覆盖同源目录的上一份报告。

2. 更新 `scripts/move_candidates_to_removable_folder.ps1`。
   - 移除对 `deletion.report_path` 的读取、校验和路径解析。
   - 从 `launch.input_dir` 和 `launch.output_dir` 解析固定报告位置：`<output_dir>\report_<输入目录名>.csv`。
   - 继续验证输入目录、报告存在性、CSV 扩展名、相对路径边界、重复路径、目标冲突及已不存在源文件。
   - 继续仅接受 `status=ok` 且 `result=可删除候选` 的行，并保留预览、精确确认文本和审计日志；候选文件移动仍是外部可见的文件系统操作，需要明确确认。

3. 更新 `config.json`。
   - 删除 `launch.report_name_prefix` 与 `deletion.report_path`。
   - 将中文说明改为：报告固定输出至 `launch.output_dir` 并覆盖同源目录的旧报告；移动脚本自动使用此固定报告。

4. 更新启动器和文档。
   - 修改 `move_candidates_to_removable_folder.bat` 的提示，移除 `deletion.report_path`，说明其自动使用当前输入目录对应的固定报告。
   - 修改 `README.md`、`docs/CONFIGURATION.md`、`docs/DEPLOYMENT.md` 及 `docs/AGENT_PROMPT.md`，移除时间戳目录、报告路径填写和“不可自动选择报告”的说明；记录固定命名、覆盖行为、自动关联移动报告与仍需人工确认的安全边界。

5. 验证。
   - 运行 Python 编译和 JSON 解析检查。
   - 使用现有两视频夹运行两次到临时报告目录，确认只生成/覆盖 `report_<源目录>.csv`，没有时间戳子目录或旧报告残留。
   - 使用 PowerShell 解析候选移动脚本并检查其派生的固定报告路径；不对真实视频执行移动确认。
   - 运行 `git diff --check`，确保无空白错误。
