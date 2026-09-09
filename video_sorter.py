#!/usr/bin/env python3
"""Create review-only reports for a folder of household camera videos.

The program never deletes, moves, or modifies source videos. It writes CSV reports
that can be reviewed before any later manual cleanup.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
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
    "inference": {
        "batch_size": 8,
        "decoder_workers": 2,
        "full_video_batch": True,
        "stop_after_person_detected": False,
    },
    "filename_time": {
        "enabled": True,
        "regex": r"(?P<date>\d{8})[_-]?(?P<time>\d{6})",
        "date_format": "%Y%m%d",
        "time_format": "%H%M%S",
    },
    "night": {"start": "22:00", "end": "07:00", "keep_videos_with_person": False},
    "reports": {"csv_encoding": "utf-8-sig"},
    "deletion": {"target_folder_name": "可删除"},
    "launch": {
        "input_dir": "data",
        "output_dir": "reports",
    },
}
SUMMARY_FIELDS = [
    "relative_path", "status", "recorded_at", "is_night", "processing_mode", "sampled_frames",
    "person_frames", "max_person_count", "result", "notes",
]


@dataclass
class DecodedVideo:
    index: int
    path: Path
    frames: list[Any]
    sampled_frames: int
    error: str = ""
    stopped_early: bool = False


@dataclass
class VideoResult:
    relative_path: str
    status: str
    recorded_at: str
    is_night: str
    sampled_frames: int = 0
    person_frames: int = 0
    max_person_count: int = 0
    processing_mode: str = "inferred"
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
    if not isinstance(config["inference"]["batch_size"], int) or config["inference"]["batch_size"] <= 0:
        raise ValueError("inference.batch_size 必须是大于 0 的整数。")
    if not isinstance(config["inference"]["decoder_workers"], int) or not 1 <= config["inference"]["decoder_workers"] <= 32:
        raise ValueError("inference.decoder_workers 必须是介于 1 和 32 的整数。")
    if not isinstance(config["inference"]["stop_after_person_detected"], bool):
        raise ValueError("inference.stop_after_person_detected 必须是 true 或 false。")
    if not isinstance(config["inference"]["full_video_batch"], bool):
        raise ValueError("inference.full_video_batch 必须是 true 或 false。")
    if config["inference"]["full_video_batch"] and config["inference"]["stop_after_person_detected"]:
        raise ValueError("full_video_batch=true 时 stop_after_person_detected 必须为 false。")
    parse_clock(config["night"]["start"])
    parse_clock(config["night"]["end"])
    if config["filename_time"]["enabled"]:
        pattern = config["filename_time"]["regex"]
        if "?P<date>" not in pattern or "?P<time>" not in pattern:
            raise ValueError("filename_time.regex 必须包含名为 date 和 time 的分组。")
        re.compile(pattern)
    launch = config["launch"]
    if not isinstance(launch["input_dir"], str) or not launch["input_dir"].strip():
        raise ValueError("launch.input_dir 必须是非空路径字符串。")
    if not isinstance(launch["output_dir"], str) or not launch["output_dir"].strip():
        raise ValueError("launch.output_dir 必须是非空路径字符串。")
    deletion = config["deletion"]
    if not isinstance(deletion["target_folder_name"], str) or not deletion["target_folder_name"].strip():
        raise ValueError("deletion.target_folder_name 必须是非空字符串。")
    if any(character in deletion["target_folder_name"] for character in '<>:"/\\|?*'):
        raise ValueError("deletion.target_folder_name 不能包含 Windows 文件名非法字符。")
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
    """Yield video files while pruning the source-local removable folder."""
    extensions = {extension.lower() for extension in config["extensions"]}
    removable_folder = config["deletion"]["target_folder_name"].casefold()
    if not config["recursive"]:
        yield from (path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() in extensions)
        return
    for root, directories, files in os.walk(input_dir):
        directories[:] = [directory for directory in directories if directory.casefold() != removable_folder]
        root_path = Path(root)
        yield from (root_path / name for name in files if (root_path / name).suffix.lower() in extensions)


def analyze_predictions(predictions: list[Any]) -> tuple[int, int]:
    """Return frames with people and the maximum detected person count for a prediction batch."""
    person_frames = max_person_count = 0
    for prediction in predictions:
        boxes = prediction.boxes
        person_count = 0
        if boxes is not None:
            for class_id in boxes.cls.tolist():
                # COCO class 0 is person. This avoids relying on translated model labels.
                if int(class_id) == 0:
                    person_count += 1
        if person_count:
            person_frames += 1
            max_person_count = max(max_person_count, person_count)
    return person_frames, max_person_count


def decode_video_samples(index: int, path: Path, config: dict[str, Any]) -> DecodedVideo:
    """Read configured sample frames for one video without running model inference."""
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return DecodedVideo(index=index, path=path, frames=[], sampled_frames=0, error="OpenCV 无法打开此视频")
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if fps <= 0 or frame_count <= 0:
            return DecodedVideo(index=index, path=path, frames=[], sampled_frames=0, error="无法读取有效的视频帧率或帧数")
        duration_seconds = frame_count / fps
        interval = float(config["sample_interval_seconds"])
        sample_times = [sample_index * interval for sample_index in range(int(duration_seconds // interval) + 1)]
        if not sample_times:
            sample_times = [0.0]
        frames: list[Any] = []
        for seconds in sample_times[: int(config["max_samples_per_video"])]:
            capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
            ok, frame = capture.read()
            if ok and frame is not None:
                frames.append(frame)
        return DecodedVideo(index=index, path=path, frames=frames, sampled_frames=len(frames))
    except Exception as error:  # OpenCV backend errors must not stop other videos.
        return DecodedVideo(index=index, path=path, frames=[], sampled_frames=0, error=str(error))
    finally:
        capture.release()


def infer_decoded_video(decoded: DecodedVideo, model: Any, device: str | int, config: dict[str, Any]) -> tuple[int, int]:
    """Submit all sampled frames from one video in one YOLO call with an internal GPU batch limit."""
    if not decoded.frames:
        return 0, 0
    predictions = model.predict(
        decoded.frames,
        conf=float(config["person_confidence"]),
        device=device,
        batch=config["inference"]["batch_size"],
        verbose=False,
    )
    return analyze_predictions(predictions)


def iter_decoded_videos(videos: list[tuple[int, Path]], config: dict[str, Any]) -> Iterator[DecodedVideo]:
    """Decode a bounded number of videos concurrently without loading the whole scan into memory."""
    worker_count = config["inference"]["decoder_workers"]
    video_iterator = iter(videos)
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="video-decode") as executor:
        pending: dict[concurrent.futures.Future[DecodedVideo], tuple[int, Path]] = {}

        def submit_next() -> bool:
            try:
                index, path = next(video_iterator)
            except StopIteration:
                return False
            future = executor.submit(decode_video_samples, index, path, config)
            pending[future] = (index, path)
            return True

        for _ in range(min(worker_count, len(videos))):
            submit_next()
        while pending:
            done, _ = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                index, path = pending.pop(future)
                try:
                    decoded = future.result()
                except Exception as error:  # Worker exceptions are isolated to the affected video.
                    decoded = DecodedVideo(index=index, path=path, frames=[], sampled_frames=0, error=str(error))
                submit_next()
                yield decoded


def classify_result(result: VideoResult, config: dict[str, Any]) -> tuple[str, str]:
    """Classify a video as a candidate or as containing at least one person."""
    if result.processing_mode == "night_direct_candidate":
        return "可删除候选", "夜间视频且配置为不保留夜间有人视频；未读取或推理视频"
    if result.person_frames == 0:
        return "可删除候选", "未在采样帧中检测到人"
    return "检测到人", "至少一个采样帧检测到人"


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]], encoding: str) -> None:
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("w", newline="", encoding=encoding) as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def report_path(output_dir: Path, input_dir: Path) -> Path:
    """Return the stable report path for a source video directory."""
    return output_dir / f"report_{input_dir.name}.csv"


def write_reports(output_dir: Path, input_dir: Path, results: list[VideoResult], config: dict[str, Any]) -> Path:
    """Overwrite the source directory's single review report after a completed scan."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = report_path(output_dir, input_dir)
    write_csv(path, SUMMARY_FIELDS, [result.as_row() for result in results], config["reports"]["csv_encoding"])
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="离线分析监控视频并生成复核清单；不会删除或移动任何视频。"
    )
    parser.add_argument("--input-dir", type=Path, help="视频根目录；省略时使用 config.json 的 launch.input_dir")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"), help="JSON 配置文件")
    parser.add_argument("--output-dir", type=Path, help="CSV 报告输出目录；省略时使用 config.json 的 launch.output_dir")
    return parser.parse_args()


def resolve_config_path(path: str, config_path: Path) -> Path:
    """Resolve a configured path relative to the configuration file."""
    candidate = Path(path).expanduser()
    return candidate if candidate.is_absolute() else config_path.parent / candidate


def default_output_dir(config: dict[str, Any], config_path: Path) -> Path:
    """Return the configured directory for stable, replaceable reports."""
    return resolve_config_path(config["launch"]["output_dir"], config_path)


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
    config_path = args.config.expanduser().resolve()
    if not config_path.is_file():
        print(f"配置文件不存在：{config_path}", file=sys.stderr)
        return 2
    try:
        config = load_config(config_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"配置无效：{error}", file=sys.stderr)
        return 2

    input_dir = args.input_dir.expanduser() if args.input_dir else resolve_config_path(config["launch"]["input_dir"], config_path)
    output_dir = args.output_dir.expanduser() if args.output_dir else default_output_dir(config, config_path)
    if not input_dir.is_dir():
        print(f"输入目录不存在或不是目录：{input_dir}", file=sys.stderr)
        return 2

    videos = list(iter_videos(input_dir, config))
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

    print(
        f"找到 {len(videos)} 个视频；推理设备：{'NVIDIA GPU' if device == 0 else 'CPU'}；GPU 内部批量大小：{config['inference']['batch_size']}；解码工作线程：{config['inference']['decoder_workers']}",
        flush=True,
    )
    night_start, night_end = parse_clock(config["night"]["start"]), parse_clock(config["night"]["end"])
    results_by_index: dict[int, VideoResult] = {}
    videos_to_infer: list[tuple[int, Path]] = []
    skip_night_inference = not config["night"]["keep_videos_with_person"]
    for index, path in enumerate(videos, start=1):
        recorded_at = recorded_at_from_filename(path, config)
        is_night = "not_checked" if not skip_night_inference else (
            "unknown" if recorded_at is None else ("yes" if within_night(recorded_at.time(), night_start, night_end) else "no")
        )
        result = VideoResult(
            relative_path=str(path.relative_to(input_dir)),
            status="ok",
            recorded_at="" if recorded_at is None else recorded_at.isoformat(sep=" "),
            is_night=is_night,
        )
        if is_night == "yes":
            result.processing_mode = "night_direct_candidate"
            result.result, result.notes = classify_result(result, config)
            results_by_index[index] = result
            continue
        videos_to_infer.append((index, path))

    direct_count = len(videos) - len(videos_to_infer)
    if skip_night_inference:
        print(f"夜间直入候选：{direct_count} 个；其余 {len(videos_to_infer)} 个视频进入解码与 GPU 推理流水线。", flush=True)
    else:
        print(f"已禁用夜间时间判断；全部 {len(videos_to_infer)} 个视频进入解码与 GPU 推理流水线。", flush=True)

    run_started_at = datetime.now()
    started_at = time_module.monotonic()
    print(f"运行开始时间：{run_started_at.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    inferred_count = 0
    for decoded in iter_decoded_videos(videos_to_infer, config):
        inferred_count += 1
        completed_count = direct_count + inferred_count
        percent = (completed_count - 1) / len(videos) * 100
        elapsed_seconds = time_module.monotonic() - started_at
        average_seconds = elapsed_seconds / inferred_count if inferred_count else 0
        remaining_seconds = average_seconds * (len(videos_to_infer) - inferred_count) if inferred_count else 0
        eta = "计算中" if inferred_count == 1 else format_duration(remaining_seconds)
        elapsed = format_duration(elapsed_seconds)
        relative_path = str(decoded.path.relative_to(input_dir))
        print(
            f"[{datetime.now().strftime('%H:%M:%S')} | {completed_count}/{len(videos)} | {percent:5.1f}% | 已运行 {elapsed} | 预计剩余 {eta}] 正在处理：{relative_path}",
            flush=True,
        )
        recorded_at = recorded_at_from_filename(decoded.path, config)
        result = VideoResult(
            relative_path=relative_path,
            status="ok",
            recorded_at="" if recorded_at is None else recorded_at.isoformat(sep=" "),
            is_night="not_checked" if not skip_night_inference else "no",
        )
        try:
            if decoded.error:
                raise RuntimeError(decoded.error)
            if decoded.sampled_frames == 0:
                raise RuntimeError("未能读取任何采样帧")
            result.sampled_frames = decoded.sampled_frames
            result.person_frames, result.max_person_count = infer_decoded_video(decoded, model, device, config)
            result.result, result.notes = classify_result(result, config)
        except Exception as error:  # Continue producing usable reports for other videos.
            result.status = "error"
            result.processing_mode = "error"
            result.result = "处理失败"
            result.notes = str(error)
            print(f"  错误：{error}", file=sys.stderr)
        results_by_index[decoded.index] = result
        completed_percent = completed_count / len(videos) * 100
        print(
            f"  完成 {completed_count}/{len(videos)}（{completed_percent:.1f}%）：{result.result or '处理完成'}",
            flush=True,
        )

    results = [results_by_index[index] for index in range(1, len(videos) + 1)]

    report = write_reports(output_dir, input_dir, results, config)
    elapsed_seconds = time_module.monotonic() - started_at
    run_finished_at = datetime.now()
    ok_count = sum(result.status == "ok" for result in results)
    deletion_count = sum(result.result == "可删除候选" for result in results)
    print(f"运行结束时间：{run_finished_at.strftime('%Y-%m-%d %H:%M:%S')}；总运行时间：{format_duration(elapsed_seconds)}")
    print(f"完成：成功 {ok_count}/{len(results)}，可删除候选 {deletion_count}。")
    print(f"报告文件（已覆盖同源目录的上一份报告）：{report.resolve()}")
    print("程序未删除、移动或修改任何源视频。请先人工复核报告中的可删除候选。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
