# 家庭监控视频筛选工具

此项目用于在**本地、离线**批量分析家庭监控视频：

- 识别视频中是否出现过人；
- 根据文件名中的录制时间与可配置的夜间规则，生成“可删除候选”清单；
- 默认只生成报告；复核后可将候选移动到源目录内的可配置文件夹。

> 这是初步筛选工具，不应用于安全、医疗或其他高风险判断。远景、遮挡、弱光或红外画面可能导致漏检，因此所有候选清单均须人工复核。

## 文档

- [部署与使用说明](docs/DEPLOYMENT.md)：另一台 Windows + NVIDIA 电脑的一键安装与运行步骤。
- [配置参考](docs/CONFIGURATION.md)：唯一的 `config.json` 配置文件、采样频率、文件名时间规则、夜间保留策略和检测阈值。
- [Agent 需求提示词](docs/AGENT_PROMPT.md)：将当前需求整理为可直接交给 Agent 的提示词。

## 快速开始

### Windows：双击启动（推荐）

首次按 [部署与使用说明](docs/DEPLOYMENT.md) 创建 `.venv` 和完成 GPU 验证后，在 `config.json` 的 `launch` 中设置视频和报告文件夹，然后双击根目录的 [`run_video_sorter.bat`](run_video_sorter.bat)。脚本不会询问输入参数，并在窗口中显示：

- 当前处理的视频编号；
- 总完成百分比；
- 根据已完成视频估算的剩余时间；
- 每段视频完成后的初步结果。

正常完成后会自动打开本次报告目录。该脚本不执行删除或移动操作。

### 命令行方式

```powershell
# 首次部署：在项目根目录执行
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1

# 编辑唯一的 JSON 配置文件；可直接编辑中文说明和参数
notepad .\config.json

# 仅生成报告（不会删除、移动或修改视频）
.\.venv\Scripts\python.exe .\video_sorter.py `
  --input-dir "D:\Camera\2026-09" `
  --config .\config.json `
  --output-dir .\reports\2026-09
```

运行后检查 `reports` 目录内以 `report_源视频目录名.csv` 命名的**单一报告**；同一源目录的下一次成功检查会覆盖该报告。报告中的 `可删除候选` 须经人工复核；确认后直接双击 [`move_candidates_to_removable_folder.bat`](move_candidates_to_removable_folder.bat)，脚本会自动读取当前源目录对应的检查报告，并将候选视频移到源视频目录下的 `可删除` 文件夹。详情见 [部署与使用说明](docs/DEPLOYMENT.md)。

## 实现概览

- Python + [Ultralytics YOLO](https://docs.ultralytics.com/) 进行本地推理；默认模型为 `yolo11n.pt`，启动时可能首次下载模型权重。
- 每个视频按固定间隔采样若干帧，而不是逐帧分析，以适应上千个十几分钟的视频文件。
- “人”基于 COCO 类别 `person`。
- 可删除候选由“无人”、“过渡时段最多仅 1 人”或“深夜直入候选”构成；规则见配置文件。
