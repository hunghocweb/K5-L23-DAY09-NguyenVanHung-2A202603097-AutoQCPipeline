"""CHECK BỔ SUNG (thưởng +3đ) — Kiểm tra lệch tỉ lệ khung hình (aspect ratio) và mất cân bằng lớp."""
from __future__ import annotations

from collections import Counter

from ..common import WARN, Issue, parse_yolo_line

DEFAULT_MAX_ASPECT_RATIO = 8.0
DEFAULT_IMBALANCE_RATIO = 10.0


def run(ds, cfg):
    acfg = cfg.get("aspect_ratio", {})
    max_ar = float(acfg.get("max_aspect_ratio", DEFAULT_MAX_ASPECT_RATIO))
    imbalance_ratio = float(acfg.get("imbalance_ratio", DEFAULT_IMBALANCE_RATIO))
    n_classes = len(ds.classes)

    issues: list[Issue] = []
    class_counts: Counter[int] = Counter()

    for lf in ds.label_files():
        stem = lf.stem
        lines = ds.read_label_lines(stem) or []
        size = ds.image_size(stem)

        for line_no, raw in lines:
            try:
                cls_id, _cx, _cy, w, h = parse_yolo_line(raw)
            except ValueError:
                continue
            if cls_id < 0 or cls_id >= n_classes or w <= 0 or h <= 0:
                continue

            class_counts[cls_id] += 1

            if size is not None:
                pw, ph = w * size[0], h * size[1]
            else:
                pw, ph = w, h

            if pw > 0 and ph > 0:
                ar = max(pw / ph, ph / pw)
                if ar > max_ar:
                    issues.append(
                        Issue(
                            "aspect_ratio",
                            WARN,
                            "BOX_EXTREME_AR",
                            stem,
                            f"tỉ lệ khung hình box bất thường ({ar:.1f}:1 > {max_ar:.1f}:1)",
                            line=line_no,
                            extra={"aspect_ratio": round(ar, 2)},
                        )
                    )

    if len(class_counts) >= 2:
        max_cnt = max(class_counts.values())
        min_cnt = min(class_counts.values())
        ratio = max_cnt / max(min_cnt, 1)
        if ratio > imbalance_ratio:
            issues.append(
                Issue(
                    "aspect_ratio",
                    WARN,
                    "CLASS_IMBALANCE",
                    "<dataset>",
                    f"mất cân bằng lớp mạnh (tỉ lệ max/min = {ratio:.1f}x > {imbalance_ratio:.1f}x)",
                    extra={"counts": dict(sorted(class_counts.items())), "ratio": round(ratio, 2)},
                )
            )

    return issues
