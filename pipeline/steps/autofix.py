"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN."""
from __future__ import annotations

from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

REMOVE_IMAGE_CODES = {
    "DUP_IMAGE_EXACT",
    "DUP_IMAGE_NEAR",
    "LEAK_TEST",
    "CORRUPT_IMAGE",
    "BAD_SIZE",
}
DROP_LINE_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}


def fix(ds, issues, cfg):
    fixes: list[dict] = []
    errors = [i for i in issues if i.severity == ERROR]

    # 1. Xoá ảnh lỗi ở cửa vào (cùng file nhãn tương ứng nếu có)
    removed_stems: set[str] = set()
    to_remove: list[str] = []
    for iss in errors:
        if iss.code in REMOVE_IMAGE_CODES and iss.image not in removed_stems:
            removed_stems.add(iss.image)
            to_remove.append(iss.image)

    for stem in to_remove:
        img_p = ds.image_path(stem)
        lbl_p = ds.label_path(stem)
        lbl_exists = lbl_p.exists()
        if img_p is None and not lbl_exists:
            continue
        before = img_p.name if img_p is not None else lbl_p.name
        if img_p is not None and img_p.exists():
            img_p.unlink()
        if lbl_exists:
            lbl_p.unlink()
        ds._size_cache.pop(stem, None)
        fixes.append(
            {
                "image": stem,
                "line": "",
                "action": "remove_image",
                "before": before,
                "after": "(đã xoá)",
            }
        )

    # 2. Chuẩn hoá tên lớp trong data.yaml
    if any(iss.code == "BAD_CLASS_NAME" for iss in errors) and ds.yaml_path.exists():
        expected = list(cfg["classes"])
        cur_names = ds.yaml_names()
        expected_map = {idx: name for idx, name in enumerate(expected)}
        if cur_names != expected_map:
            data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
            before_names = data.get("names")
            data["names"] = expected
            ds.yaml_path.write_text(
                yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            fixes.append(
                {
                    "image": "data.yaml",
                    "line": "",
                    "action": "rename_classes",
                    "before": str(before_names),
                    "after": str(expected),
                }
            )

    # 3. Ảnh thiếu file nhãn -> không tự bịa nhãn, chuyển hàng đợi người
    seen_missing: set[str] = set()
    for iss in errors:
        if iss.code == "MISSING_LABEL_FILE":
            stem = iss.image
            if stem in removed_stems or stem in seen_missing:
                continue
            seen_missing.add(stem)
            if not ds.label_path(stem).exists():
                fixes.append(
                    {
                        "image": stem,
                        "line": "",
                        "action": "needs_label",
                        "before": "(không có file)",
                        "after": "chuyển người gán",
                    }
                )

    # 4. Sửa lỗi mức dòng trong từng file nhãn (gom theo file để giữ nguyên số dòng gốc)
    line_actions: dict[str, dict[int, str]] = defaultdict(dict)
    for iss in errors:
        stem = iss.image
        if stem in removed_stems or iss.line is None:
            continue
        if iss.code in DROP_LINE_CODES:
            line_actions[stem][iss.line] = "drop_line"
        elif iss.code == "BOX_OUT_OF_IMAGE":
            if line_actions[stem].get(iss.line) != "drop_line":
                line_actions[stem][iss.line] = "clip_box"

    for stem, actions_by_line in line_actions.items():
        lbl_p = ds.label_path(stem)
        if not lbl_p.exists():
            continue
        raw_lines = lbl_p.read_text(encoding="utf-8", errors="replace").splitlines()
        new_lines: list[str] = []
        changed = False

        for line_no, raw in enumerate(raw_lines, 1):
            action = actions_by_line.get(line_no)
            if action == "drop_line":
                changed = True
                fixes.append(
                    {
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": raw.strip(),
                        "after": "(đã xoá)",
                    }
                )
                continue

            if action == "clip_box":
                try:
                    cls_id, cx, cy, w, h = parse_yolo_line(raw)
                except ValueError:
                    changed = True
                    fixes.append(
                        {
                            "image": stem,
                            "line": line_no,
                            "action": "drop_line",
                            "before": raw.strip(),
                            "after": "(đã xoá: sai định dạng)",
                        }
                    )
                    continue

                x1 = max(0.0, min(1.0, cx - w / 2.0))
                y1 = max(0.0, min(1.0, cy - h / 2.0))
                x2 = max(0.0, min(1.0, cx + w / 2.0))
                y2 = max(0.0, min(1.0, cy + h / 2.0))
                nw, nh = x2 - x1, y2 - y1

                if nw <= 0.0 or nh <= 0.0:
                    changed = True
                    fixes.append(
                        {
                            "image": stem,
                            "line": line_no,
                            "action": "drop_line",
                            "before": raw.strip(),
                            "after": "(đã xoá: ngoài ảnh)",
                        }
                    )
                    continue

                ncx, ncy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                clipped = f"{cls_id} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"
                changed = True
                fixes.append(
                    {
                        "image": stem,
                        "line": line_no,
                        "action": "clip_box",
                        "before": raw.strip(),
                        "after": clipped,
                    }
                )
                new_lines.append(clipped)
                continue

            new_lines.append(raw)

        if changed:
            content = "\n".join(new_lines) + ("\n" if new_lines else "")
            lbl_p.write_text(content, encoding="utf-8")

    return fixes
