from pipeline.checks import aspect_ratio


def test_normal_aspect_ratio_is_clean(make_ds, cfg):
    ds = make_ds(
        images={"a": 1, "b": 2},
        labels={"a": ["0 0.5 0.5 0.2 0.2"], "b": ["1 0.5 0.5 0.15 0.25"]},
        size=(640, 480),
    )
    assert aspect_ratio.run(ds, cfg) == []


def test_extreme_wide_and_tall_aspect_ratio_flagged(make_ds, cfg):
    ds = make_ds(
        images={"a": 1},
        labels={
            "a": [
                "0 0.5 0.5 0.6 0.02",  # 384px x 9.6px -> AR 40:1
                "1 0.2 0.5 0.02 0.8",  # 12.8px x 384px -> AR 30:1
                "2 0.8 0.5 0.2 0.2",   # bình thường
            ]
        },
        size=(640, 480),
    )
    iss = [i for i in aspect_ratio.run(ds, cfg) if i.code == "BOX_EXTREME_AR"]
    assert [(i.image, i.line, i.severity) for i in iss] == [
        ("a", 1, "warn"),
        ("a", 2, "warn"),
    ]


def test_class_imbalance_detected_across_dataset(make_ds, cfg):
    many = ["0 0.5 0.5 0.2 0.2"] * 12
    ds = make_ds(
        images={"a": 1, "b": 2},
        labels={"a": many, "b": ["3 0.5 0.5 0.2 0.2"]},
        size=(640, 480),
    )
    imb = [i for i in aspect_ratio.run(ds, cfg) if i.code == "CLASS_IMBALANCE"]
    assert len(imb) == 1 and imb[0].image == "<dataset>"


def test_broken_lines_do_not_crash_aspect_ratio(make_ds, cfg):
    ds = make_ds(
        images={"a": 1},
        labels={"a": ["garbage", "", "99 0.5 0.5 0.2 0.2", "0 0.5 0.5 0 0.2"]},
        size=(640, 480),
    )
    assert aspect_ratio.run(ds, cfg) == []
