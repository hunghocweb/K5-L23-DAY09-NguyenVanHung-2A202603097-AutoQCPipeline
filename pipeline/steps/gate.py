"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework."""
from __future__ import annotations

from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems = set(image_stems)
    reviewed_set = set(reviewed)
    n_images = len(stems)

    n_errors = sum(1 for i in issues if i.severity == ERROR)
    warn_images = {
        i.image
        for i in issues
        if i.severity == WARN and i.image in stems and i.image not in reviewed_set
    }
    n_warn_images = len(warn_images)
    warn_ratio = round(n_warn_images / n_images, 4) if n_images > 0 else 0.0
    hold_thresh = cfg["gate"]["warn_ratio_hold"]

    if n_errors > 0:
        decision = "Rework"
        reasons = [
            f"Còn {n_errors} lỗi bắt buộc (severity ERROR) chưa xử lý trên tổng {n_images} ảnh."
        ]
    elif warn_ratio >= hold_thresh:
        decision = "Hold"
        reasons = [
            f"Không còn lỗi bắt buộc, nhưng có {n_warn_images}/{n_images} ảnh "
            f"({warn_ratio:.2%}) còn cảnh báo chưa duyệt (>= ngưỡng {hold_thresh:.0%})."
        ]
    else:
        decision = "Release"
        reasons = [
            f"Không còn lỗi bắt buộc; chỉ {n_warn_images}/{n_images} ảnh "
            f"({warn_ratio:.2%}) còn cảnh báo chưa duyệt (< ngưỡng {hold_thresh:.0%})."
        ]

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }
