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

## 2. 安装前：更新并验证 NVIDIA 驱动

GPU 推理不需要单独安装 CUDA Toolkit；PyTorch 的 CUDA 安装包会包含所需运行时。**但 NVIDIA 驱动必须足够新，才能支持 PyTorch 所使用的 CUDA 版本。**

1. 打开 [NVIDIA 官方驱动下载页](https://www.nvidia.com/Download/index.aspx)，按全量视频电脑的实际显卡型号、Windows 版本和台式机/笔记本类型下载最新驱动。
2. 完成安装并重启电脑。
3. 在 PowerShell 执行：

```powershell
nvidia-smi
```

预期会显示 GPU 名称、`Driver Version` 与 `CUDA Version`。若提示找不到 `nvidia-smi`，可使用默认安装路径：

```powershell
& "C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
```

若两种方式都失败，请先修复或重装 NVIDIA 驱动，**不要继续安装 GPU 版 PyTorch**。

## 3. 创建 Python 虚拟环境

将整个项目文件夹复制到全量视频电脑，例如 `D:\Tools\claude-videoProcessing`。打开 PowerShell 并执行：

```powershell
cd D:\Tools\claude-videoProcessing
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

建议使用 Python 3.10、3.11 或 3.12（推荐 3.11）。安装 Python 时请勾选 **Add python.exe to PATH**。可用以下命令确认：

```powershell
py --version
```

## 4. 安装匹配的 GPU 版 PyTorch

打开 [PyTorch 官方 Start Locally 页面](https://pytorch.org/get-started/locally/)，选择：

- **Stable**；
- **Windows**；
- **Pip**；
- **Python**；
- 页面当前提供、且与已更新驱动相容的 CUDA 版本。

复制官网生成的命令。不要根据旧电脑或本文示例固定 CUDA 版本。假设官网当前给出 CUDA 12.6，则命令形如：

```powershell
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
```

若官网给出 CUDA 12.8，则命令会是：

```powershell
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

若此前已安装过 CPU 版 PyTorch，请先卸载，再执行官网提供的 GPU 安装命令：

```powershell
.\.venv\Scripts\python.exe -m pip uninstall -y torch torchvision
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
```

上例中的 `cu126` **仅为示例**，最后一条必须替换成 PyTorch 官方页面在安装当日给出的命令。

## 5. 安装项目其余依赖并验证 GPU

GPU 版 PyTorch 安装成功后，再安装本项目的其余依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

它会安装：

- `ultralytics`：YOLO 人体检测；
- `opencv-python`：读取视频与抽帧；
- `PyYAML`：读取 YAML 配置。

首次分析会下载 `yolo11n.pt` 模型权重。若目标电脑不能联网，请在有网络的电脑先运行一次，再将已下载的权重文件复制到目标电脑并把 `model` 配置成该权重的绝对路径。

执行以下命令验证 PyTorch 实际可以使用 GPU：

```powershell
.\.venv\Scripts\python.exe -c "import torch; print('PyTorch:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NOT AVAILABLE')"
```

成功结果应类似：

```text
PyTorch: 2.x.x+cu12x
CUDA available: True
GPU: NVIDIA ...
```

只有 `CUDA available: True` 时，程序才会使用 GPU。启动视频分析时还会显示：

```text
找到 N 个视频；推理设备：NVIDIA GPU
```

如果显示 `CPU` 或 `CUDA available: False`，请停止全量任务，检查 `nvidia-smi` 输出、显卡驱动是否已更新，以及是否用官网 GPU 命令覆盖了 CPU 版 PyTorch。

若必须只使用 CPU，可跳过本节的 GPU 安装，并运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1 -CpuOnly
```

CPU 可以运行，但处理上千个视频会明显更慢。

## 6. 配置

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

## 7. 先用少量视频测试

建议复制 10–20 段、包含白天/夜间/有人/无人场景的视频到测试目录：

```powershell
.\.venv\Scripts\python.exe .\video_sorter.py `
  --input-dir "D:\CameraTest" `
  --config .\config.yaml `
  --output-dir .\reports\test
```

检查 CSV 与原视频是否相符；再调节抽帧间隔、阈值和夜间规则。

## 8. 运行全量目录

### 双击 BAT 启动器（推荐）

在完成依赖安装、GPU 验证并检查 `config.yaml` 后，双击项目根目录的 `run_video_sorter.bat`。它会：

1. 检查 `.venv`、主程序和配置文件是否存在；首次运行时自动从 `config.example.yaml` 创建 `config.yaml`；
2. 询问视频输入目录（直接回车仅使用项目 `data` 测试目录）；
3. 询问配置文件路径（直接回车使用 `config.yaml`）；
4. 询问报告名称，并在 `reports` 下创建独立目录；
5. 启动分析，实时显示当前文件编号、处理百分比、预计剩余时间及每个视频的初步结果；
6. 分析成功后自动打开本次报告目录。

脚本不会删除、移动或修改视频。运行时保持黑色命令窗口打开；如需停止，请按 `Ctrl+C`。为得到完整报告，建议在中断后重新运行一次，而不是使用中断时产生的不完整结果。

### 命令行启动

确认测试结果后，也可在 PowerShell 手动执行：

```powershell
.\.venv\Scripts\python.exe .\video_sorter.py `
  --input-dir "E:\CameraArchive" `
  --config .\config.yaml `
  --output-dir .\reports\2026-09-07
```

可中断后重新运行；报告会根据本次扫描结果覆盖同名 CSV。因此建议每次运行使用新的输出目录。

## 9. 输出与人工复核

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
