"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp."""
from __future__ import annotations

from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    lcfg = cfg["label_format"]
    overflow_tol = lcfg["overflow_tol"]
    dup_box_iou = lcfg["dup_box_iou"]
    min_box_px = lcfg["min_box_px"]
    max_box_frac = lcfg["max_box_frac"]
    n_classes = len(ds.classes)

    issues: list[Issue] = []

    for lf in ds.label_files():
        stem = lf.stem
        lines = ds.read_label_lines(stem) or []
        img_size = ds.image_size(stem)
        seen_boxes: list[tuple[int, float, float, float, float]] = []

        for line_no, raw in lines:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(raw)
            except ValueError as exc:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BAD_FORMAT",
                        stem,
                        f"dòng nhãn sai định dạng: {exc}",
                        line=line_no,
                    )
                )
                continue

            if cls_id < 0 or cls_id >= n_classes:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BAD_CLASS_ID",
                        stem,
                        f"id lớp {cls_id} ngoài khoảng 0..{n_classes - 1}",
                        line=line_no,
                        extra={"class_id": cls_id},
                    )
                )
                continue

            if w <= 0 or h <= 0:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BOX_ZERO",
                        stem,
                        f"box có kích thước không dương (w={w}, h={h})",
                        line=line_no,
                    )
                )
                continue

            x1, y1 = cx - w / 2.0, cy - h / 2.0
            x2, y2 = cx + w / 2.0, cy + h / 2.0
            overflow = max(0.0 - x1, 0.0 - y1, x2 - 1.0, y2 - 1.0, 0.0)
            if overflow > overflow_tol:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BOX_OUT_OF_IMAGE",
                        stem,
                        f"mép box tràn khỏi [0, 1] {overflow:.4f} (> {overflow_tol})",
                        line=line_no,
                        extra={"overflow": round(overflow, 6)},
                    )
                )

            box = (cx, cy, w, h)
            is_dup = any(
                prev_cls == cls_id and iou_xywh(box, prev_box) > dup_box_iou
                for prev_cls, prev_box in seen_boxes
            )
            if is_dup:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "DUP_BOX",
                        stem,
                        f"box trùng lặp cùng lớp {cls_id} (IoU > {dup_box_iou})",
                        line=line_no,
                    )
                )
            seen_boxes.append((cls_id, box))

            if img_size is not None:
                img_w, img_h = img_size
                short_px = min(w * img_w, h * img_h)
                if short_px < min_box_px:
                    issues.append(
                        Issue(
                            "label_format",
                            WARN,
                            "BOX_TINY",
                            stem,
                            f"cạnh ngắn {short_px:.1f}px < {min_box_px}px",
                            line=line_no,
                            extra={"short_px": round(short_px, 2)},
                        )
                    )

            area_frac = w * h
            if area_frac > max_box_frac:
                issues.append(
                    Issue(
                        "label_format",
                        WARN,
                        "BOX_HUGE",
                        stem,
                        f"diện tích box {area_frac:.2%} > {max_box_frac:.0%}",
                        line=line_no,
                        extra={"area_frac": round(area_frac, 4)},
                    )
                )

    return issues
