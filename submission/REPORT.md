# Báo cáo Day 09 — Nguyễn Văn Hùng, 2A202603097

## 1. Kết luận trước

Pipeline kết luận **Hold** (mã thoát `10`). Trong **224** ảnh đầu vào từ `data/raw`, cửa vào đã loại **22/224** ảnh lỗi/trùng/rò rỉ và giữ lại **202/224** ảnh (`748` box hợp lệ sau QC). Sau bước tự sửa và ngân sách người duyệt **80/125** ảnh trong hàng đợi, lô dữ liệu còn **0 lỗi bắt buộc** nhưng vẫn còn **38/202** ảnh (**18.81%** ≥ ngưỡng **10%**) mang cảnh báo chưa được người kiểm; vì vậy hệ thống chỉ xuất bản **NHÁP** tại `submission/export/clean_v1/` và chưa cho phát hành chính thức.

## 2. Lỗi và phân việc

Số liệu tổng hợp từ `01_intake.csv` (22 ảnh bị loại ở cửa vào) và `02_error_list_v1.csv` (211 dòng lỗi/cảnh báo trước sửa):

| Mã lỗi | Số dòng / ảnh | Ai sửa (máy / người) | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` | 8 / 224 ảnh | Máy (loại ở cửa vào) | Trùng từng byte MD5, xác suất sai 0%, giữ ảnh đầu tiên. |
| `LEAK_TEST` | 5 / 224 ảnh | Máy (loại ở cửa vào) | Trùng tập `test`/`gold_val`, phải loại để chống rò rỉ đánh giá. |
| `DUP_IMAGE_NEAR` | 4 / 224 ảnh | Máy (loại ở cửa vào) | pHash cách ≤ 10 bit (đã hiệu chỉnh), là ảnh thu nhỏ/đổi sáng của ảnh đã giữ. |
| `BAD_SIZE` / `CORRUPT_IMAGE` | 3 + 2 / 224 ảnh | Máy (loại ở cửa vào) | Ảnh < 250px hoặc cắt cụt (`im.load()` lỗi), không đủ chất lượng train. |
| `BOX_OUT_OF_IMAGE` | 8 dòng / 8 ảnh | Máy (`clip_box` / `drop_line`) | Quy tắc hình học rõ ràng: cắt mép box về `[0, 1]`, xoá nếu mất diện tích. |
| `DUP_BOX` | 7 dòng / 7 ảnh | Máy (`drop_line`) | Box cùng lớp có IoU > 0.9, giữ dòng đầu và xoá dòng lặp phía sau. |
| `BAD_CLASS_ID` / `BOX_ZERO` / `BAD_FORMAT` | 6 + 4 + 3 dòng | Máy (`drop_line`) | Dòng hỏng cú pháp hoặc ID ngoài `0..3`, xoá an toàn không làm lệch dòng khác. |
| `BAD_CLASS_NAME` | 2 lỗi / 1 `data.yaml` | Máy (`rename_classes`) | Viết hoa sai (`Person`, `Bus`), chuẩn hoá về `['car', 'person', 'truck', 'bus']`. |
| `MISSING_LABEL_FILE` | 6 / 202 ảnh | **Người** (`needs_label`) | Máy **không** tự bịa nhãn; chuyển đầu hàng đợi để người gán đủ box. |
| `POSSIBLE_MISSING` | 53 ca / 52 ảnh | **Người** (hàng đợi duyệt) | Model lớn thấy vật nhưng nhãn thiếu; cần mắt người xác nhận tránh FP. |
| `POSSIBLE_FALSE_POS` | 29 ca / 27 ảnh | **Người** (hàng đợi duyệt) | Box nhãn không khớp dự đoán model; có thể do vật bị khuất hoặc nhãn dư. |
| `POSSIBLE_LOOSE_BOX` | 28 ca / 24 ảnh | **Người** (hàng đợi duyệt) | Box cùng lớp nhưng IoU < 0.5; người cần nhìn ranh giới vật thật để chỉnh. |
| `POSSIBLE_WRONG_CLASS` | 18 ca / 18 ảnh | **Người** (hàng đợi duyệt) | Dễ nhầm `car`/`truck`/`bus` (vd. `img_0019`, `img_0020`); người quyết định ngữ nghĩa. |
| `EMPTY_LABEL` / `BOX_TINY` / `BOX_HUGE` | 12 + 6 + 3 ca | **Người** (hàng đợi duyệt) | Cần phân biệt ảnh nền thật vs thiếu nhãn, vật nhỏ hợp lệ vs nhiễu. |

**Giải thích hàng đợi (`05_review_queue.csv`) và hiệu quả ngân sách 80 ảnh:**
Hàng đợi gồm **125 ảnh** sắp theo điểm ưu tiên giảm dần dựa trên trọng số rủi ro trong `configs/pipeline.yaml`: ảnh có lỗi vừa được máy sửa (`FIXED_DROP_LINE` = 2) cộng thêm cảnh báo ngữ nghĩa nặng (`img_0020` = 11.523 điểm) hoặc ảnh thiếu file nhãn (`NEEDS_LABEL` = 10.0 điểm: `img_0031, img_0053, img_0126, img_0135, img_0170, img_0219`) đứng đầu, tiếp theo là `POSSIBLE_WRONG_CLASS` (3 × (1+conf)), `POSSIBLE_MISSING`/`POSSIBLE_FALSE_POS` (2 × (1+conf)), và cuối hàng là các cảnh báo nhẹ (`BOX_TINY` 0.3). Với ngân sách **80/125** ảnh, người duyệt đã xử lý xong toàn bộ **6/6** ảnh thiếu nhãn và phần lớn lỗi ngữ nghĩa nghiêm trọng (`POSSIBLE_WRONG_CLASS` giảm từ **18 → 3**, `POSSIBLE_MISSING` từ **53 → 13**, `POSSIBLE_LOOSE_BOX` từ **28 → 20**, `POSSIBLE_FALSE_POS` từ **24 → 21** ở vòng 3).

## 3. Calibration (2 ngưỡng)

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | `2` | **`10`** | `DUP_IMAGE_NEAR`: `1.00 / 0.50` → `1.00 / 0.67` | Giữ Precision = `1.00`, tăng Recall lên `0.67` để bắt thêm cặp trùng thu nhỏ/đổi sáng trên `raw` (`img_0223`≈`img_0077` dist=6, `img_0186`≈`img_0061` dist=10) mà không xoá nhầm ảnh khác nhau. |
| `second_opinion.conf` | `0.25` | **`0.6`** | `WRONG_CLASS`: `0.56 / 0.83` → `0.62 / 0.83`<br>`MISSING`: `0.50 / 1.00` → `0.57 / 1.00` | Tăng Precision trên `WRONG_CLASS` và `MISSING` (giảm báo động giả tốn ngân sách duyệt từ 136 → 125 ảnh) trong khi vẫn giữ nguyên Recall (`0.83` và `1.00`); nếu tăng lên `0.7` bắt đầu rớt Recall `MISSING` (`1.00 → 0.88`). |

**Một điểm đánh lừa của calibration (có bằng chứng từ dữ liệu):**
Trên tập `data/calib` (chỉ có 39 ảnh), `phash_dist = 16` đạt F1 cao nhất (`DUP_IMAGE_NEAR` đạt `P=1.00, R=0.83, F1=0.91`) với `0` báo động giả. Tuy nhiên khi kiểm chứng thực tế trên `data/raw` (224 ảnh), `phash_dist = 16` tăng số ảnh bị loại từ **22** lên **31** ảnh (tạo ra nhiều cặp trùng giả ở khoảng cách đúng 16 bit), điển hình là cờ nhầm **`img_0011.jpg`** (vận động viên tennis trên sân xanh) là trùng với **`img_0008.jpg`** (hai người trượt tuyết trên núi tuyết), cùng hai cặp sai khác (`img_0084`≈`img_0074`, `img_0177`≈`img_0113`) và 6 cờ `LEAK_TEST` giả. Chọn theo F1 cao nhất trên calib nhỏ sẽ gây xoá nhầm dữ liệu sạch trên lô thật, nên mốc **`10`** là lựa chọn an toàn hơn.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

**(a) Chứng minh cửa chặn hoạt động đúng:**
Chạy lệnh mô phỏng không có người duyệt:
`python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`
Kết quả ghi nhận: còn **6 lỗi bắt buộc** (`MISSING_LABEL_FILE` trên 6 ảnh chưa có file nhãn) và **112/202** ảnh (**55.45%**) có cảnh báo; cửa chặn trả về quyết định **Rework**, mã thoát **`20`**, và thư mục `work/exp_nb/clean_v1` **không được tạo** (`exported: null`). Điều này chứng minh `gate.py` luôn chặn xuất bản khi còn lỗi `ERROR`.

**(b) Các điểm mù mà pipeline KHÔNG bắt được:**
1. **Box lệch/lỏng vừa phải (`0.5 ≤ IoU < 0.75`) hoặc cùng lệch như model:** `iou_loose` cố định ở `0.5` nên các box ôm hơi rộng/lệch một cạnh (nhưng IoU đạt `0.55–0.70`) vẫn qua lọt cửa `second_opinion`; tương tự, nếu cả nhãn gốc lẫn `yolo26l` đều nhầm `truck` thành `car` (hoặc cùng bỏ sót người ở xa/khuất), check ý kiến thứ hai sẽ im lặng.
2. **Ảnh gần trùng biến đổi mạnh (pHash > 10) và box méo tỉ lệ/mất cân bằng lớp trong pipeline lõi:** Trong `data/calib`, 2/6 ca `DUP_IMAGE_NEAR` biến đổi mạnh (cắt/xoay lớn) có khoảng cách pHash > 10 vẫn lọt qua ngưỡng `10`. Ngoài ra, các box quá dẹt/méo tỉ lệ khung hình (như `img_0030` dòng 9 tỉ lệ `8.6:1`, `img_0042` dòng 5 tỉ lệ `9.6:1`, `img_0155` dòng 2 tỉ lệ `9.8:1`) hoặc chênh lệch lớp cực đại (`person` **574** box vs `bus` **32** box — gấp **17.9×**) không có cờ riêng trong pipeline chuẩn mà chỉ phát hiện khi chạy thêm module mở rộng `pipeline/checks/aspect_ratio.py`.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

**Chưa chạy.** Lý do: môi trường thực thi hiện tại không có GPU/Colab runtime để chạy `scripts/train_compare.py` với YOLO26n trong 20 epoch × 2 seed × 2 biến thể; phần lõi được kiểm chứng bằng `make check-core` (theo đúng hướng dẫn `GUIDE.md` và `RUBRIC.md`).

## 6. Quyết định và ghi chú AI

- **(a) Quyết định cuối:** **Hold** (chỉ xuất bản nháp `submission/export/clean_v1/`, chưa phát hành chính thức). Để chuyển sang **Release**, cần tăng ngân sách duyệt thêm ít nhất **19–38 ảnh** còn lại trong danh sách cảnh báo cuối (`07_error_list_v3.csv`) sao cho số ảnh còn cảnh báo chưa duyệt giảm xuống dưới **10%** (`< 20/202` ảnh), và nên bổ sung thêm dữ liệu cho lớp `bus` (`32` box) / `truck` (`41` box).
- **(b) Ghi chú sử dụng AI:**
  1. *Prompt chính*: Cung cấp docstring chuẩn + các ca test trong `tests/test_*.py`, yêu cầu viết lần lượt từng module (`label_format`, `gate`, `autofix`, `second_opinion`, và check mở rộng `aspect_ratio`) đọc toàn bộ ngưỡng từ `cfg`, giữ nguyên số dòng gốc khi có dòng trống, và không sửa bất kỳ file nào thuộc danh sách ghim SHA1.
  2. *Cách kiểm*: Chạy `pytest -q` (83/83 test xanh gồm 79 test đề bài + 4 test mới cho `aspect_ratio`), chạy `pipeline.calibrate` sweep trên `data/calib`, kiểm chứng trực quan cặp ảnh trùng (`img_0008`/`img_0011`, `img_0061`/`img_0186`, `img_0077`/`img_0223`) và đối chiếu `scripts/check_submission.py --no-train`.
  3. *Một lần AI sai & cách sửa*: Ở lần thử nghiệm ngưỡng bằng script một dòng, việc đưa giá trị `phash_dist = 16` theo F1 cao nhất trên `calib` khiến script xoá nhầm ảnh khác hoàn toàn trên `raw`; đã phát hiện bằng cách chạy thử nghiệm trên `data/raw`, mở đối chiếu cặp ảnh thực tế và hạ ngưỡng về `10`.
