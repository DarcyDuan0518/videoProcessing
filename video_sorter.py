#!/usr/bin/env python3
"""Create review-only reports for a folder of household camera videos.

The program never deletes, moves, or modifies source videos. It writes CSV reports
that can be reviewed before any later manual cleanup.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time as time_module
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Any, Iterator

import cv2

DEFAULT_CONFIG: dict[str, Any] = {
    "model": "yolo11n.pt",
    "recursive": True,
    "extensions": [".mp4", ".avi", ".mov", ".mkv"],
    "sample_interval_seconds": 15,
    "max_samples_per_video": 60,
    "person_confidence": 0.35,
    "baby_max_bbox_area_ratio": 0.12,
    "baby_min_detections": 2,
    "filename_time": {
        "enabled": True,
        "regex": r"(?P<date>\d{8})[_-]?(?P<time>\d{6})",
        "date_format": "%Y%m%d",
        "time_format": "%H%M%S",
    },
    "night": {"start": "22:00", "end": "07:00", "keep_videos_with_person": False},
    "reports": {"csv_encoding": "utf-8-sig"},
}
SUMMARY_FIELDS = [
    "relative_path", "status", "recorded_at", "is_night", "sampled_frames",
    "person_frames", "max_person_count", "baby_like_frames", "result", "notes",
]


@dataclass
class VideoResult:
    relative_path: str
    status: str
    recorded_at: str
    is_night: str
    sampled_frames: int = 0
    person_frames: int = 0
    max_person_count: int = 0
    baby_like_frames: int = 0
    result: str = ""
    notes: str = ""

    def as_row(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in SUMMARY_FIELDS}


def merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge nested user settings into defaults without modifying either input."""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError("配置文件根节点必须是 JSON 对象。")
    config = merge_dict(DEFAULT_CONFIG, loaded)
    if config["sample_interval_seconds"] <= 0 or config["max_samples_per_video"] <= 0:
        raise ValueError("sample_interval_seconds 和 max_samples_per_video 必须大于 0。")
    if not 0 <= config["person_confidence"] <= 1:
        raise ValueError("person_confidence 必须介于 0 和 1。")
    if config["baby_max_bbox_area_ratio"] is not None and not 0 < config["baby_max_bbox_area_ratio"] <= 1:
        raise ValueError("baby_max_bbox_area_ratio 必须为 null 或介于 0 和 1。")
    parse_clock(config["night"]["start"])
    parse_clock(config["night"]["end"])
    if config["filename_time"]["enabled"]:
        pattern = config["filename_time"]["regex"]
        if "?P<date>" not in pattern or "?P<time>" not in pattern:
            raise ValueError("filename_time.regex 必须包含名为 date 和 time 的分组。")
        re.compile(pattern)
    return config


def parse_clock(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def within_night(value: time, start: time, end: time) -> bool:
    """Return whether a clock time lies in a normal or overnight interval."""
    if start == end:
        return True
    if start < end:
        return start <= value < end
    return value >= start or value < end


def recorded_at_from_filename(path: Path, config: dict[str, Any]) -> datetime | None:
    settings = config["filename_time"]
    if not settings["enabled"]:
        return None
    match = re.search(settings["regex"], path.name)
    if not match:
        return None
    try:
        return datetime.strptime(
            match.group("date") + match.group("time"),
            settings["date_format"] + settings["time_format"],
        )
    except ValueError:
        return None


def iter_videos(input_dir: Path, config: dict[str, Any]) -> Iterator[Path]:
    extensions = {extension.lower() for extension in config["extensions"]}
    candidates = input_dir.rglob("*") if config["recursive"] else input_dir.glob("*")
    yield from (path for path in candidates if path.is_file() and path.suffix.lower() in extensions)


def sample_video(path: Path, model: Any, device: str | int, config: dict[str, Any]) -> tuple[int, int, int, int]:
    """Return sampled frames, frames with people, max people, and baby-like frames."""
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError("OpenCV 无法打开此视频")
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if fps <= 0 or frame_count <= 0:
            raise RuntimeError("无法读取有效的视频帧率或帧数")
        duration_seconds = frame_count / fps
        interval = float(config["sample_interval_seconds"])
        sample_times = [index * interval for index in range(int(duration_seconds // interval) + 1)]
        if not sample_times:
            sample_times = [0.0]
        sample_times = sample_times[: int(config["max_samples_per_video"])]

        sampled_frames = person_frames = max_person_count = baby_like_frames = 0
        for seconds in sample_times:
            capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            sampled_frames += 1
            height, width = frame.shape[:2]
            prediction = model.predict(
                frame,
                conf=float(config["person_confidence"]),
                device=device,
                verbose=False,
            )[0]
            boxes = prediction.boxes
            person_areas: list[float] = []
            if boxes is not None:
                for class_id, xyxy in zip(boxes.cls.tolist(), boxes.xyxy.tolist()):
                    # COCO class 0 is person. This avoids relying on translated model labels.
                    if int(class_id) != 0:
                        continue
                    x1, y1, x2, y2 = xyxy
                    person_areas.append(max(0.0, x2 - x1) * max(0.0, y2 - y1) / (width * height))
            if person_areas:
                person_frames += 1
                max_person_count = max(max_person_count, len(person_areas))
                threshold = config["baby_max_bbox_area_ratio"]
                if threshold is not None and any(area <= threshold for area in person_areas):
                    baby_like_frames += 1
        return sampled_frames, person_frames, max_person_count, baby_like_frames
    finally:
        capture.release()


def classify_result(result: VideoResult, config: dict[str, Any]) -> tuple[str, str]:
    """Classify conservatively: unknown timestamp never triggers a night deletion rule."""
    deletion_reasons: list[str] = []
    if result.person_frames == 0:
        deletion_reasons.append("未在采样帧中检测到人")
    if result.is_night == "yes" and not config["night"]["keep_videos_with_person"]:
        deletion_reasons.append("夜间视频且配置为不保留夜间有人视频")
    if deletion_reasons:
        return "可删除候选", "；".join(deletion_reasons)
    if config["baby_max_bbox_area_ratio"] is None:
        return "检测到人", "已禁用婴儿启发式判断"
    if result.baby_like_frames >= int(config["baby_min_detections"]):
        return "疑似有婴儿", "小人框启发式命中，必须人工复核"
    return "疑似无婴儿", "未达到小人框启发式阈值，必须人工复核"


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]], encoding: str) -> None:
    with path.open("w", newline="", encoding=encoding) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_reports(output_dir: Path, results: list[VideoResult], config: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    encoding = config["reports"]["csv_encoding"]
    summary_rows = [result.as_row() for result in results]
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDS, summary_rows, encoding)

    groups = {
        "no_person_files.csv": [r for r in results if r.status == "ok" and r.person_frames == 0],
        "possible_no_baby_files.csv": [r for r in results if r.status == "ok" and r.result == "疑似无婴儿"],
        "possible_baby_files.csv": [r for r in results if r.status == "ok" and r.result == "疑似有婴儿"],
        "deletion_candidates.csv": [r for r in results if r.status == "ok" and r.result == "可删除候选"],
        "errors.csv": [r for r in results if r.status == "error"],
    }
    for name, group in groups.items():
        write_csv(output_dir / name, SUMMARY_FIELDS, [result.as_row() for result in group], encoding)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="离线分析监控视频并生成复核清单；不会删除或移动任何视频。"
    )
    parser.add_argument("--input-dir", required=True, type=Path, help="视频根目录")
    parser.add_argument("--config", required=True, type=Path, help="JSON 配置文件")
    parser.add_argument("--output-dir", required=True, type=Path, help="CSV 报告输出目录")
    return parser.parse_args()


def format_duration(seconds: float) -> str:
    """Format a duration for the console progress estimate."""
    total_seconds = max(0, round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}小时{minutes:02d}分"
    if minutes:
        return f"{minutes}分{seconds:02d}秒"
    return f"{seconds}秒"


def main() -> int:
    args = parse_args()
    if not args.input_dir.is_dir():
        print(f"输入目录不存在或不是目录：{args.input_dir}", file=sys.stderr)
        return 2
    if not args.config.is_file():
        print(f"配置文件不存在：{args.config}", file=sys.stderr)
        return 2
    try:
        config = load_config(args.config)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"配置无效：{error}", file=sys.stderr)
        return 2

    videos = list(iter_videos(args.input_dir, config))
    if not videos:
        print("没有找到匹配的视频文件。请检查 input-dir、extensions 和 recursive 设置。")
        return 0

    try:
        from ultralytics import YOLO
        import torch

        device = 0 if torch.cuda.is_available() else "cpu"
        model = YOLO(config["model"])
    except Exception as error:  # noqa: BLE001 - dependency/model startup errors need a readable CLI result.
        print(f"无法加载 YOLO 模型：{error}", file=sys.stderr)
        return 3

    print(f"找到 {len(videos)} 个视频；推理设备：{'NVIDIA GPU' if device == 0 else 'CPU'}", flush=True)
    print("进度会在每个视频完成后更新；可按 Ctrl+C 停止，已中断的运行不生成完整报告。", flush=True)
    results: list[VideoResult] = []
    night_start, night_end = parse_clock(config["night"]["start"]), parse_clock(config["night"]["end"])
    started_at = time_module.monotonic()
    for index, path in enumerate(videos, start=1):
        relative_path = str(path.relative_to(args.input_dir))
        percent = (index - 1) / len(videos) * 100
        elapsed_seconds = time_module.monotonic() - started_at
        average_seconds = elapsed_seconds / (index - 1) if index > 1 else 0
        remaining_seconds = average_seconds * (len(videos) - index + 1) if index > 1 else 0
        eta = "计算中" if index == 1 else format_duration(remaining_seconds)
        print(
            f"[{index}/{len(videos)} | {percent:5.1f}% | 预计剩余 {eta}] 正在处理：{relative_path}",
            flush=True,
        )
        recorded_at = recorded_at_from_filename(path, config)
        is_night = "unknown" if recorded_at is None else ("yes" if within_night(recorded_at.time(), night_start, night_end) else "no")
        result = VideoResult(
            relative_path=relative_path,
            status="ok",
            recorded_at="" if recorded_at is None else recorded_at.isoformat(sep=" "),
            is_night=is_night,
        )
        try:
            result.sampled_frames, result.person_frames, result.max_person_count, result.baby_like_frames = sample_video(
                path, model, device, config
            )
            if result.sampled_frames == 0:
                raise RuntimeError("未能读取任何采样帧")
            result.result, result.notes = classify_result(result, config)
        except Exception as error:  # Continue producing usable reports for other videos.
            result.status = "error"
            result.result = "处理失败"
            result.notes = str(error)
            print(f"  错误：{error}", file=sys.stderr)
        results.append(result)
        completed_percent = index / len(videos) * 100
        print(
            f"  完成 {index}/{len(videos)}（{completed_percent:.1f}%）：{result.result or '处理完成'}",
            flush=True,
        )

    write_reports(args.output_dir, results, config)
    ok_count = sum(result.status == "ok" for result in results)
    deletion_count = sum(result.result == "可删除候选" for result in results)
    print(f"完成：成功 {ok_count}/{len(results)}，可删除候选 {deletion_count}。")
    print(f"报告目录：{args.output_dir.resolve()}")
    print("程序未删除、移动或修改任何源视频。请先人工复核 deletion_candidates.csv。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
