# Windows + NVIDIA 部署与使用

本工具用于在另一台存放全量视频的 Windows 电脑上离线筛选视频。默认只生成 CSV 清单，**不会删除、移动、覆盖或修改任意源视频**。

## 1. 前置条件

- Windows 10/11；
- NVIDIA 显卡及可正常工作的显卡驱动；
- Python 3.10、3.11 或 3.12（推荐 3.11）；
- 足够的磁盘空间：原视频目录之外，预留模型、Python 环境和报告空间；
- 视频文件名应包含录制日期时间，或准备在配置中关闭夜间规则。

安装 Python 时勾选 **Add python.exe to PATH**。在 PowerShell 执行：

```powershell
py --version
nvidia-smi
```

若两条命令均能成功，继续下一步。

## 2. 一键安装

将整个项目文件夹复制到全量视频电脑，例如 `D:\Tools\claude-videoProcessing`。打开 PowerShell 并执行：

```powershell
cd D:\Tools\claude-videoProcessing
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1
```

脚本会创建 `.venv` 虚拟环境并安装 `requirements.txt` 中的所有 Python 库：

- `ultralytics`：YOLO 人体检测；
- `opencv-python`：读取视频与抽帧；
- `PyYAML`：读取 YAML 配置；
- `torch` / `torchvision`：由 Ultralytics 依赖安装，负责 GPU 推理。

首次分析会下载 `yolo11n.pt` 模型权重。若目标电脑不能联网，请在有网络的电脑先运行一次，再将已下载的权重文件复制到目标电脑并把 `model` 配置成该权重的绝对路径。

## 3. 验证 NVIDIA GPU 是否可用

执行：

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA unavailable')"
```

预期第一行是 `True`。若为 `False`，请根据 **PyTorch 官方 Start Locally** 页面按显卡驱动支持的 CUDA 版本，安装匹配的 GPU wheel；然后重新运行上述验证命令。

例如，官方页面给出 CUDA 12.4 wheel 时，可执行（版本以官网当前命令为准）：

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

不要盲目固定 CUDA 版本；应以该电脑的驱动和 PyTorch 官方说明为准。若只能使用 CPU，安装阶段使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1 -CpuOnly
```

CPU 可以运行，但处理上千个视频会明显更慢。

## 4. 配置

复制示例并编辑：

```powershell
Copy-Item .\config.example.yaml .\config.yaml
notepad .\config.yaml
```

重点确认：

1. `filename_time.regex` 必须匹配视频文件名中的日期、时间。例如默认规则匹配 `Camera_20260907_221530.mp4`。
2. `night.start` 与 `night.end`：夜间时段，可跨日，如 `22:00` 到 `07:00`。
3. `night.keep_videos_with_person`：
   - `false`：夜间视频即使检测到人，也进入可删除候选；
   - `true`：夜间检测到人的视频保留，只有无人视频进入候选。
4. `sample_interval_seconds`：每隔多少秒抽一帧。值越小，漏检概率越低但耗时越长。
5. `baby_*`：只是“小人框”启发式筛选，不能把结果当作婴儿身份的可靠结论。

更多字段含义见 [CONFIGURATION.md](CONFIGURATION.md)。

## 5. 先用少量视频测试

建议复制 10–20 段、包含白天/夜间/有人/无人场景的视频到测试目录：

```powershell
.\.venv\Scripts\python.exe .\video_sorter.py `
  --input-dir "D:\CameraTest" `
  --config .\config.yaml `
  --output-dir .\reports\test
```

检查 CSV 与原视频是否相符；再调节抽帧间隔、阈值和夜间规则。

## 6. 运行全量目录

确认测试结果后：

```powershell
.\.venv\Scripts\python.exe .\video_sorter.py `
  --input-dir "E:\CameraArchive" `
  --config .\config.yaml `
  --output-dir .\reports\2026-09-07
```

可中断后重新运行；报告会根据本次扫描结果覆盖同名 CSV。因此建议每次运行使用新的输出目录。

## 7. 输出与人工复核

报告以 `UTF-8 with BOM` 写入，可用 Excel 打开：

| 文件 | 含义 |
| --- | --- |
| `summary.csv` | 每个视频的完整状态、采样统计与结果。 |
| `no_person_files.csv` | 未在任何采样帧中检测到人的文件。 |
| `possible_baby_files.csv` | 命中婴儿启发式条件的文件，必须人工复核。 |
| `possible_no_baby_files.csv` | 未命中婴儿启发式条件但检测到人的文件，必须人工复核。 |
| `deletion_candidates.csv` | 按无人或配置的夜间规则形成的候选，**不代表可直接删除**。 |
| `errors.csv` | 无法读取或推理失败的文件；请不要把它们作为删除候选。 |

建议先抽查候选清单，尤其是：红外夜视、婴儿被抱着、远景、小目标、多人、画面遮挡和异常文件。确认无误后，再由人工或另行制作的、带确认步骤的清理脚本处理；本项目当前版本没有任何删除命令。
