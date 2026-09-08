# 家庭监控视频筛选工具

此项目用于在**本地、离线**批量分析家庭监控视频：

- 识别视频中是否出现过人；
- 标记疑似包含婴儿和疑似未包含婴儿的视频，供人工检查；
- 根据文件名中的录制时间与可配置的夜间规则，生成“可删除候选”清单；
- **默认绝不移动或删除原视频**，只输出报告与清单。

> 这是初步筛选工具，不应用于安全、医疗或育儿判断。婴儿在远景、遮挡、弱光或红外画面中容易漏检，因此所有候选清单均须人工复核。

## 文档

- [部署与使用说明](docs/DEPLOYMENT.md)：另一台 Windows + NVIDIA 电脑的一键安装与运行步骤。
- [配置参考](docs/CONFIGURATION.md)：唯一的 `config.json` 配置文件、采样频率、文件名时间规则、夜间保留策略和检测阈值。
- [Agent 需求提示词](docs/AGENT_PROMPT.md)：将当前需求整理为可直接交给 Agent 的提示词。

## 快速开始

### Windows：双击启动（推荐）

首次按 [部署与使用说明](docs/DEPLOYMENT.md) 创建 `.venv` 和完成 GPU 验证后，双击根目录的 [`run_video_sorter.bat`](run_video_sorter.bat)。脚本会询问视频目录、配置文件和报告名称，并在窗口中显示：

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

运行后检查 `reports` 目录内的 `summary.csv`、`no_person_files.csv`、`possible_no_baby_files.csv` 与 `deletion_candidates.csv`。

## 实现概览

- Python + [Ultralytics YOLO](https://docs.ultralytics.com/) 进行本地推理；默认模型为 `yolo11n.pt`，启动时可能首次下载模型权重。
- 每个视频按固定间隔采样若干帧，而不是逐帧分析，以适应上千个十几分钟的视频文件。
- “人”基于 COCO 类别 `person`；“婴儿”是基于人框大小、位置与检测持续性的**启发式推断**，不是可靠的年龄分类。
- 可删除候选由“无人”或“夜间且夜间保留关闭”构成；规则见配置文件，默认只写清单。
