# 配置参考

配置文件为 YAML。推荐从根目录的 `config.example.yaml` 复制为 `config.yaml` 后修改。

## 检测与性能

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `model` | `yolo11n.pt` | YOLO 权重路径或模型名。`n` 最快；可尝试 `yolo11s.pt` 获取更高精度。 |
| `recursive` | `true` | 是否扫描输入目录的子目录。 |
| `extensions` | mp4/avi/mov/mkv | 要处理的扩展名列表，大小写不敏感。 |
| `sample_interval_seconds` | `15` | 每隔几秒抽取一帧。更小能降低短暂出现的人被漏检的概率，但更慢。 |
| `max_samples_per_video` | `60` | 单段视频最多抽取的帧数，避免超长视频耗时失控。 |
| `person_confidence` | `0.35` | 人体置信度阈值。夜视漏检多可试 `0.25`；误检多可提高到 `0.45`。 |

YOLO 的 COCO `person` 类用于“是否有人”判定。任一采样帧检测到人，即该视频视为有人。

## 婴儿启发式（可选）

通用 COCO YOLO 模型没有“婴儿”类别。因此本工具只把较小的人体框作为“可能婴儿”的线索：

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `baby_max_bbox_area_ratio` | `0.12` | 人框面积不高于画面面积的此比例，就算一个 baby-like 命中。设为 `null` 可禁用婴儿判断。 |
| `baby_min_detections` | `2` | 至少命中多少个采样帧，才标记“疑似有婴儿”。 |

此规则会把远处成人、被抱着的婴儿、被子覆盖的人等情况误判或漏判。它的用途只是优先级排序，不能据此删除重要视频。若后续需要高精度婴儿检测，应收集获得授权的、与该摄像头角度和光照相符的训练数据，训练与验证专用模型。

## 根据文件名识别录制时间

```yaml
filename_time:
  enabled: true
  regex: "(?P<date>\\d{8})[_-]?(?P<time>\\d{6})"
  date_format: "%Y%m%d"
  time_format: "%H%M%S"
```

`regex` 必须定义名为 `date` 和 `time` 的分组。默认适用：

```text
Camera_20260907_221530.mp4
              ^date   ^time
```

如果文件名是 `2026-09-07_22-15-30.mp4`，可以配置为：

```yaml
filename_time:
  enabled: true
  regex: "(?P<date>\\d{4}-\\d{2}-\\d{2})_(?P<time>\\d{2}-\\d{2}-\\d{2})"
  date_format: "%Y-%m-%d"
  time_format: "%H-%M-%S"
```

如果时间无法可靠地从文件名取得，设为 `enabled: false`。此时 `is_night` 会是 `unknown`，程序不会仅因夜间规则把文件写入删除候选。

## 夜间保留规则

```yaml
night:
  start: "22:00"
  end: "07:00"
  keep_videos_with_person: false
```

- 支持跨日范围；`22:00`–`07:00` 指当天 22:00 起到次日 07:00 前。
- `keep_videos_with_person: false`：所有时间落在夜间的视频都会成为可删除候选；无人视频无论白天/夜间同样成为候选。
- `keep_videos_with_person: true`：仅无人视频成为候选，夜间有人视频不成为候选。
- 时间点恰好为 `end` 时不属于夜间，例如 `07:00` 不属于 `22:00`–`07:00`。

## 报告编码

`reports.csv_encoding` 默认为 `utf-8-sig`，为了让 Windows Excel 正确识别中文。除非下游系统另有要求，不建议更改。
