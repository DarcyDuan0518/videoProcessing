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
- 配置文件使用 Python 内置 JSON 解析，不需要额外配置文件解析库。

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

使用项目根目录中唯一的 `config.json`，可直接编辑：

```powershell
notepad .\config.json
```

重点确认：

1. `launch.input_dir`：双击 `run_video_sorter.bat` 时要处理的视频根目录。可填绝对路径（例如 `E:\\CameraArchive`）或相对项目的 `data`。
2. `launch.output_dir`：CSV 检查报告目录；同一源视频目录每次成功检查都会覆盖该目录中的旧报告。
3. `filename_time.regex` 必须匹配视频文件名中的日期、时间。例如默认规则匹配 `Camera_20260907_221530.mp4`。
4. `night.direct_candidate_start` 与 `night.direct_candidate_end`：深夜直入可删除候选的时段，默认 `23:00` 到次日 `07:00`。`night.two_person_windows`：需同一帧至少检测到 2 人才保留的过渡时段，默认 `21:00`–`23:00` 与 `07:00`–`08:00`。
5. `night.keep_videos_with_person`：
   - `false`：应用深夜直入候选与过渡时段两人保留规则；其他时段检测到至少 1 人即保留；
   - `true`：忽略所有夜间与过渡时段规则，所有视频检测到至少 1 人即保留。
6. `sample_interval_seconds`：每隔多少秒抽一帧。值越小，漏检概率越低但耗时越长。
7. `deletion.target_folder_name`：人工复核后移动候选视频的源目录内子文件夹名称；扫描时会自动跳过该文件夹。

更多字段含义见 [CONFIGURATION.md](CONFIGURATION.md)。

## 7. 先用少量视频测试

建议复制 10–20 段、包含白天/夜间/有人/无人场景的视频到测试目录：

```powershell
.\.venv\Scripts\python.exe .\video_sorter.py `
  --input-dir "D:\CameraTest" `
  --config .\config.json `
  --output-dir .\reports\test
```

检查 CSV 与原视频是否相符；再调节抽帧间隔、阈值和夜间规则。

## 8. 运行全量目录

### 双击 BAT 启动器（推荐）

在完成依赖安装、GPU 验证并设置 `config.json` 的 `launch.input_dir` 与 `launch.output_dir` 后，双击项目根目录的 `run_video_sorter.bat`。它不会询问任何输入参数，而会：

1. 检查 `.venv`、主程序和唯一的 `config.json` 配置文件是否存在；
2. 从 `config.json` 读取视频输入目录和报告父目录；
3. 在 `launch.output_dir` 中生成或覆盖单一的、带源目录名的 CSV 报告文件；
4. 启动分析，实时显示当前文件编号、处理百分比、预计剩余时间及每个视频的初步结果；
5. 在完成时输出本次报告文件路径。

脚本不会删除、移动或修改视频。运行时保持黑色命令窗口打开；如需停止，请按 `Ctrl+C`。为得到完整报告，建议在中断后重新运行一次，而不是使用中断时产生的不完整结果。

### 命令行启动

确认测试结果后，也可在 PowerShell 手动执行：

```powershell
.\.venv\Scripts\python.exe .\video_sorter.py `
  --input-dir "E:\CameraArchive" `
  --config .\config.json `
  --output-dir .\reports\2026-09-07
```

可中断后重新运行；只有一次完整的成功分析完成后，才会覆盖 `launch.output_dir` 中与该源目录对应的固定报告。若中断或启动失败，上一份完整报告会保留。

## 9. 输出与人工复核

运行完成后会生成一个单一 CSV 报告，文件名包含源视频目录名，例如 `report_20260906.csv`。同一源视频目录的下一次成功检查会覆盖这份报告：

| 列 | 含义 |
| --- | --- |
| `relative_path` | 相对源视频目录的路径。 |
| `status` | `ok` 或 `error`。 |
| `processing_mode` | `inferred` 表示按普通规则进行人员识别；`two_person_required` 表示过渡时段且需同一采样帧至少 2 人才保留；`night_direct_candidate` 表示深夜直入候选、未读取视频。 |
| `sampled_frames` / `person_frames` | 成功采样帧数与检测到人的帧数。 |
| `result` | `检测到人`、`可删除候选` 或 `处理失败`。 |
| `notes` | 判定原因或错误信息。 |

报告中的可删除候选不代表可立即删除，必须人工复核。

## 10. 人工复核后移到可删除文件夹（可选）

> **请先人工逐项复核单一 CSV 报告中的 `可删除候选`。** 候选来自抽帧检测或夜间规则，可能漏检或误判；此操作会在源视频目录内移动文件，但不会删除文件。

1. 在 `config.json` 中确认 `launch.input_dir` 指向源视频根目录，`launch.output_dir` 指向检查报告目录。例如：

   ```json
   "launch": {
     "input_dir": "20260906",
     "output_dir": "reports"
   },
   "deletion": {
     "target_folder_name": "可删除"
   }
   ```

2. 人工复核 `reports\report_20260906.csv` 中的候选后，双击项目根目录的 `move_candidates_to_removable_folder.bat`；不需要拖放、填写报告路径、输入确认文本或输入其他参数。脚本会自动使用当前输入目录的固定报告，并立即开始移动合格候选。
3. 工具只接受报告内的相对路径，拒绝绝对路径、目录外路径和重复路径。源文件已经不存在时安静跳过；目标路径已存在时绝不覆盖，也不会阻断其他候选。
4. 文件会移动到 `<源视频目录>\可删除\` 内，并保留原始相对目录结构。脚本自动创建缺少的目录；后续识别会跳过该文件夹及其所有子文件夹。
5. 脚本不生成移动审计 CSV；控制台会显示每个移动结果及最终的已移动、跳过和失败汇总。
