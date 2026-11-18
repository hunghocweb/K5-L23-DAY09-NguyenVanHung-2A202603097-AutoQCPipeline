"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l)."""
from __future__ import annotations

from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    scfg = cfg["second_opinion"]
    conf_thresh = scfg["conf"]
    min_area_px = scfg["min_area_px"]
    fp_conf = scfg["fp_conf"]
    iou_missing = scfg["iou_missing"]
    iou_match = scfg["iou_match"]
    iou_loose = scfg["iou_loose"]
    n_classes = len(ds.classes)

    issues: list[Issue] = []

    for img_path in ds.image_files():
        stem = img_path.stem
        if stem not in preds:
            continue
        raw_lines = ds.read_label_lines(stem)
        if raw_lines is None:
            continue
        size = ds.image_size(stem)
        if size is None:
            continue
        img_w, img_h = size

        labels = ds.valid_boxes(stem)
        all_preds = preds[stem]

        filtered_preds = [
            p
            for p in all_preds
            if p[1] >= conf_thresh and (p[4] * img_w) * (p[5] * img_h) >= min_area_px
        ]

        for p in filtered_preds:
            p_cls = int(p[0])
            p_conf = float(p[1])
            p_box = (float(p[2]), float(p[3]), float(p[4]), float(p[5]))

            cands = []
            for l_cls, lcx, lcy, lw, lh in labels:
                iou = iou_xywh(p_box, (lcx, lcy, lw, lh))
                if iou >= iou_missing:
                    cands.append((l_cls, iou))

            if not cands:
                cls_name = ds.classes[p_cls] if 0 <= p_cls < n_classes else str(p_cls)
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_MISSING",
                        stem,
                        f"model dự đoán {cls_name} (conf={p_conf:.2f}) nhưng không có nhãn khớp",
                        extra={"conf": round(p_conf, 3), "pred_class": p_cls},
                    )
                )
                continue

            same_cls = [iou for l_cls, iou in cands if l_cls == p_cls]
            if same_cls:
                best_same = max(same_cls)
                if best_same < iou_loose:
                    issues.append(
                        Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_LOOSE_BOX",
                            stem,
                            f"box nhãn cùng lớp khớp lỏng với model (IoU={best_same:.2f} < {iou_loose})",
                            extra={"conf": round(p_conf, 3), "iou": round(best_same, 3)},
                        )
                    )
            else:
                best_other_cls, best_other_iou = max(cands, key=lambda item: item[1])
                if best_other_iou >= iou_match:
                    issues.append(
                        Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_WRONG_CLASS",
                            stem,
                            f"nhãn lớp {best_other_cls} nhưng model dự đoán lớp {p_cls} (IoU={best_other_iou:.2f})",
                            extra={
                                "conf": round(p_conf, 3),
                                "iou": round(best_other_iou, 3),
                                "label_class": best_other_cls,
                                "pred_class": p_cls,
                            },
                        )
                    )

        fp_preds = [p for p in all_preds if p[1] >= fp_conf]
        for line_no, raw in raw_lines:
            try:
                parsed = parse_yolo_line(raw)
            except ValueError:
                continue
            if not (0 <= parsed[0] < n_classes):
                continue
            l_box = (parsed[1], parsed[2], parsed[3], parsed[4])
            matched = any(
                iou_xywh(l_box, (float(p[2]), float(p[3]), float(p[4]), float(p[5]))) >= iou_missing
                for p in fp_preds
            )
            if not matched:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_FALSE_POS",
                        stem,
                        f"box nhãn dòng {line_no} không khớp dự đoán nào của model",
                        line=line_no,
                        extra={"conf": 0.0},
                    )
                )

    return issues
