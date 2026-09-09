# 配置参考

项目只使用根目录中的一个配置文件：`config.json`。它是 **UTF-8 JSON** 文件，支持中文说明和中文字符串；可用 Windows 记事本编辑。

> 请不要删除英文参数键；它们由程序读取。修改字符串时保留双引号，最后一个字段后不要添加逗号。`true` / `false` 必须使用小写英文；禁用可选项时使用 `null`。

## 当前视频文件名的时间规则

当前 `config.json` 已适配测试视频命名格式：

```text
video_0446_0_10_20260905165246_20260905165756.mp4
                  ^^^^^^^^^^^^^^ 第一个时间戳：录制开始时间
```

对应配置片段：

```json
"filename_time": {
  "enabled": true,
  "regex": "(?P<date>\\d{8})(?P<time>\\d{6})",
  "date_format": "%Y%m%d",
  "time_format": "%H%M%S"
}
```

`regex` 必须定义 `date` 和 `time` 两个命名分组。如果无法从文件名取得可靠的录制时间，把 `enabled` 改为 `false`；此时 `is_night` 会显示 `unknown`，程序不会只因夜间规则将文件写入删除候选。

例如文件名为 `Camera_20260907_221530.mp4`，可改为：

```json
"filename_time": {
  "enabled": true,
  "regex": "(?P<date>\\d{8})[_-]?(?P<time>\\d{6})",
  "date_format": "%Y%m%d",
  "time_format": "%H%M%S"
}
```

## 启动文件夹与检查报告

双击 `run_video_sorter.bat` 时，视频输入目录和报告输出目录都从 `launch` 读取，不会询问任何输入参数：

```json
"launch": {
  "input_dir": "data",
  "output_dir": "reports"
}
```

- `input_dir`：要扫描的视频根目录。可写绝对路径，如 `E:\\CameraArchive`；也可写相对路径，如默认的 `data`，相对 `config.json` 所在目录。
- `output_dir`：检查报告目录。每个源视频目录仅对应一个固定报告文件；每次成功完成检查会直接覆盖该源目录的旧报告。

例如，要处理 `E:\CameraArchive` 并把报告保存到 `D:\VideoReports`，设置为：

```json
"launch": {
  "input_dir": "E:\\CameraArchive",
  "output_dir": "D:\\VideoReports"
}
```

临时测试时仍可通过命令行覆盖这些设置：

```powershell
.\.venv\Scripts\python.exe .\video_sorter.py `
  --input-dir "D:\CameraTest" `
  --config .\config.json `
  --output-dir .\reports\manual-test
```

## 可删除文件夹与移动配置

每个源视频目录的检查报告固定命名为：

```text
report_<源视频目录名>.csv
```

例如源目录为 `20260906`、报告目录为 `reports` 时，报告固定为：

```text
reports\report_20260906.csv
```

下次完成对 `20260906` 的检查时，程序会直接覆盖这个报告，不保留时间戳副本。识别过程未成功完成时，不会覆盖之前已有的完整报告。

人工复核报告中的 `可删除候选` 后，直接双击 `move_candidates_to_removable_folder.bat`。脚本会自动根据当前 `launch.input_dir` 和 `launch.output_dir` 读取对应的固定报告，不需要填写报告路径，也不接受命令行参数；它会立即开始移动其中的合格候选。

```json
"launch": {
  "input_dir": "20260906",
  "output_dir": "reports"
},
"deletion": {
  "target_folder_name": "可删除"
}
```

- `launch.input_dir`：源视频根目录；CSV 中的 `relative_path` 只能在这个目录下解析。
- `launch.output_dir`：固定检查报告所在目录。
- `deletion.target_folder_name`：源视频目录内存放候选文件的子文件夹。脚本自动创建它，并保留原始相对目录结构。例如 `camera-a\\clip.mp4` 会移动至 `可删除\\camera-a\\clip.mp4`。
- 扫描时会自动跳过名为 `target_folder_name` 的目录及其所有子目录，因此已移入的候选不会在下一次识别时被重复扫描。
- 候选源文件若已不存在，会标记为 `already_absent` 后安静跳过；目标路径已存在时标记为 `target_exists`，绝不覆盖，也会继续处理其他候选。

移动脚本不要求输入确认文本，也不会生成移动审计 CSV；控制台会显示每个文件的移动结果和最终汇总。

## 检测与性能

| 参数键 | 默认值 | 说明 |
| --- | --- | --- |
| `model` | `yolo11n.pt` | YOLO 权重路径或模型名。`n` 最快；可尝试 `yolo11s.pt` 获取更高精度。 |
| `recursive` | `true` | 是否扫描输入目录的子目录。 |
| `extensions` | mp4/avi/mov/mkv | 要处理的扩展名列表，大小写不敏感。 |
| `sample_interval_seconds` | `15` | 每隔几秒抽取一帧。更小能降低短暂出现的人被漏检的概率，但更慢。 |
| `max_samples_per_video` | `60` | 单段视频最多抽取的帧数，避免超长视频耗时失控。 |
| `person_confidence` | `0.35` | 人体置信度阈值。夜视漏检多可试 `0.25`；误检多可提高到 `0.45`。 |
| `inference.batch_size` | `8` | 每次 YOLO 调用内部使用的 GPU 批量上限。`full_video_batch: true` 时会将同一视频的完整采样帧列表一次交给 YOLO，再由这个值控制内部批次；单块 6 GB GPU 建议从 `8` 或 `16` 开始。若出现 CUDA 显存不足，依次改为 `8`、`4`、`2`、`1`。 |
| `inference.decoder_workers` | `2` | 并发读取与解码不同视频的 CPU 工作线程数。当前 E: 机械硬盘的两视频实测中，`2` 优于 `1`；输入位于本地 NVMe SSD 时可依次测试 `3`、`4`。不要超过 CPU 核心数，也不要启动多个完整程序进程。 |
| `inference.full_video_batch` | `true` | 先按固定间隔读取一个视频的全部采样帧，再将该完整帧列表一次交给 YOLO。适合持续向 GPU 提供大任务；与 `stop_after_person_detected: true` 不兼容。 |
| `inference.stop_after_person_detected` | `false` | 任一 GPU 推理批次检测到人后，停止该视频后续的抽帧与推理。用于只关心“是否有人”的快速筛选。启用时必须把 `full_video_batch` 设为 `false`。 |

YOLO 的 COCO `person` 类用于“是否有人”判定。普通时段任一采样帧检测到人即标记为“检测到人”；过渡时段要求同一采样帧至少检测到 2 人才保留；未检测到人、过渡时段最多仅 1 人或按深夜规则直接跳过识别的视频标记为“可删除候选”，均须人工复核。

程序会以有限数量的 CPU 解码线程预读不同视频，并使用一个 YOLO/CUDA 模型推理；当前 E: 机械硬盘上的两视频基准显示 `decoder_workers: 2` 比 `1` 更快，故默认使用 `2`。`full_video_batch: true` 时，CPU 先按固定间隔读取一个视频的全部采样帧，GPU 再通过一次 YOLO 调用接收该帧组，以 `batch_size` 限制内部显存批次；同时解码线程继续读取其他视频，形成解码—推理流水线。不要同时启动多个 `run_video_sorter.bat` 进程，它们会重复加载模型、争抢 6 GB 显存且通常更慢。

## 夜间保留规则

```json
"night": {
  "direct_candidate_start": "23:00",
  "direct_candidate_end": "07:00",
  "two_person_windows": [
    {"start": "21:00", "end": "23:00"},
    {"start": "07:00", "end": "08:00"}
  ],
  "keep_videos_with_person": false
}
```

以下所有时间段均为**开始时间包含、结束时间不包含**，并优先根据文件名中的录制开始时间判断：

- `keep_videos_with_person: false`：
  - `direct_candidate_start`–`direct_candidate_end`：默认 `23:00`–次日 `07:00`。深夜视频直接进入可删除候选，不读取或推理，`processing_mode` 为 `night_direct_candidate`。
  - `two_person_windows`：默认 `21:00`–`23:00`、`07:00`–`08:00`。这些过渡时段仍会推理，但只有**同一采样帧**检测到至少 2 人才保留；0 或 1 人均进入可删除候选，`processing_mode` 为 `two_person_required`。
  - 其余时间：正常推理，任一采样帧检测到至少 1 人即保留。
  - 文件名时间无法解析时：正常按“至少 1 人保留”推理，绝不会仅因时间规则成为候选。
- `keep_videos_with_person: true`：完全不判断这些时间段，所有视频均按普通规则推理；任一采样帧检测到至少 1 人即保留，`is_night` 为 `not_checked`。

## 报告编码

`reports.csv_encoding` 默认为 `utf-8-sig`，为了让 Windows Excel 正确识别中文。除非下游系统另有要求，不建议更改。
