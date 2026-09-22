# -*- coding: utf-8 -*-
"""
对标普 500 标的做多维度量化打分，输出推荐排名（data/score.json）。

设计原则
--------
1. **同一指数、同一区间、同一币种 → 净值增长率本身可直接横比**，不需要"超额收益"这类
   受基准口径污染的指标。这是收益维度只用净值增长率的理由。
2. **只看长期**。半年数据噪声大，用 三年50% + 一年30% + 半年20%（各自年化后加权）。
3. **结构指标与成本指标分开**，避免重复计分：参与率看"钱有没有进指数"，费率看"每年被拿走多少"，
   溢价看"买入那一刻吃亏多少"。
4. **限购额度不进评分**（按需求）。申购状态只做标注。
5. **每个阈值与归一化方式都写清楚**，并用 3 组替代权重做稳健性检验。

输出 data/score.json
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WEIGHTS = {
    "return": 40,      # 长期收益兑现
    "exposure": 20,    # 真实敞口（穿透后参与率）
    "cost": 20,        # 持有成本（加权综合费率）
    "scale": 12,       # 规模与稳定性
    "friction": 8,     # 买入摩擦（场内溢价）
}

# 稳健性检验用的替代权重
ALT_WEIGHTS = {
    "收益优先": {"return": 55, "exposure": 15, "cost": 15, "scale": 10, "friction": 5},
    "成本优先": {"return": 25, "exposure": 15, "cost": 40, "scale": 12, "friction": 8},
    "结构优先": {"return": 30, "exposure": 35, "cost": 20, "scale": 10, "friction": 5},
}

# 规模分档（期末净资产，元）：越小清盘/流动性风险越高
SCALE_BANDS = [(2e9, 7.0), (5e8, 5.5), (1e8, 4.0), (0, 2.0)]


def load():
    a = json.load(open(os.path.join(ROOT, "data", "analysis.json"), encoding="utf-8"))
    r = json.load(open(os.path.join(ROOT, "data", "raw_reports.json"), encoding="utf-8"))
    return a, r


def periods_of(raw, code):
    """取该产品 A 类份额的全部区间收益。"""
    rep = raw.get("%s_semi" % code)
    if not rep:
        return {}
    for lab, v in (rep.get("returns") or {}).items():
        if lab.endswith("A") or lab.endswith("A人民币") or lab == "主份额":
            return v.get("periods", {})
    first = next(iter((rep.get("returns") or {}).values()), None)
    return (first or {}).get("periods", {})


def annualize(pct, years):
    return ((1 + pct / 100.0) ** (1.0 / years) - 1) * 100.0


def minmax(vals, reverse=False):
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [100.0] * len(vals)
    out = [(v - lo) / (hi - lo) * 100.0 for v in vals]
    return [100.0 - x for x in out] if reverse else out


def scale_score(nav):
    """规模分（满分 7）。分档线性，避免超大基金把刻度拉爆。"""
    bands = SCALE_BANDS
    for i, (thr, sc) in enumerate(bands):
        if nav >= thr:
            if i == 0:
                return sc
            hi_thr, hi_sc = bands[i - 1]
            lo_thr = thr
            # 在 [lo_thr, hi_thr] 之间线性插值
            return sc + (hi_sc - sc) * (nav - lo_thr) / (hi_thr - lo_thr)
    return bands[-1][1]


def build():
    a, raw = load()
    P = a["products"]
    rows = []
    for code, rec in P.items():
        p = periods_of(raw, code)
        if not p or "过去六个月" not in p:
            continue
        r6 = p["过去六个月"]["nav"]
        r1 = p.get("过去一年", {}).get("nav")
        r3 = p.get("过去三年", {}).get("nav")
        rows.append(dict(
            code=code, short=rec["short"], name=rec["name"], kind=rec["kind"],
            where=rec["where"], r6=r6, r1=r1, r3=r3,
            bench6=rec["bench_6m"], diff6=rec["diff_6m"],
            penetrated=rec["penetrated_pct"], fee=rec["comprehensive_fee"],
            nav=rec["nav_end"], scale_chg=rec["scale_chg_pct"] or 0.0,
            premium=rec.get("premium_end"),
            premium_adj=rec.get("premium_adj_pct"),
            implied=rec["implied_high"], vs_target=rec.get("vs_target_pp"),
            target=rec.get("target_code"), periods=p,
            std6=p["过去六个月"]["std"],
            std1=(p.get("过去一年") or {}).get("std"),
        ))

    # ---- 维度 1：长期收益兑现（三年50% + 一年30% + 半年20%，各自年化） ----
    for r in rows:
        parts, wts = [], []
        if r["r3"] is not None:
            parts.append(annualize(r["r3"], 3)); wts.append(0.5)
        if r["r1"] is not None:
            parts.append(r["r1"]); wts.append(0.3)
        parts.append(annualize(r["r6"], 0.5)); wts.append(0.2)
        r["ann_return"] = sum(x * w for x, w in zip(parts, wts)) / sum(wts)
        r["ann3"] = annualize(r["r3"], 3) if r["r3"] is not None else None
        r["ann1"] = r["r1"]
        r["ann6"] = annualize(r["r6"], 0.5)

    # ---- 归一化 ----
    s_ret = minmax([r["ann_return"] for r in rows])
    s_exp = minmax([r["penetrated"] for r in rows])
    s_cost = minmax([r["fee"] for r in rows], reverse=True)
    for r, x, y, z in zip(rows, s_ret, s_exp, s_cost):
        r["s_return"], r["s_exposure"], r["s_cost"] = x, y, z

    # ---- 维度 4：规模与稳定（12 = 规模 7 + 稳定 5） ----
    for r in rows:
        r["s_scale_sub"] = scale_score(r["nav"])
        r["s_stab_sub"] = 5.0 * max(0.0, 1.0 - abs(r["scale_chg"]) / 100.0)
        r["s_scale"] = r["s_scale_sub"] + r["s_stab_sub"]

    # ---- 维度 5：买入摩擦（8，绝对刻度：场外无溢价=满分） ----
    for r in rows:
        prem = r["premium"] or 0.0
        r["s_friction"] = 100.0 / (1.0 + prem / 100.0)

    # ---- 加权总分 ----
    def total(r, w):
        return (r["s_return"] * w["return"] + r["s_exposure"] * w["exposure"]
                + r["s_cost"] * w["cost"]
                + r["s_scale"] / 12.0 * 100.0 * w["scale"]
                + r["s_friction"] * w["friction"]) / 100.0

    for r in rows:
        r["score"] = total(r, WEIGHTS)
        r["score_breakdown"] = {
            "长期收益兑现": r["s_return"] * WEIGHTS["return"] / 100.0,
            "真实敞口": r["s_exposure"] * WEIGHTS["exposure"] / 100.0,
            "持有成本": r["s_cost"] * WEIGHTS["cost"] / 100.0,
            "规模与稳定": r["s_scale"] / 12.0 * 100.0 * WEIGHTS["scale"] / 100.0,
            "买入摩擦": r["s_friction"] * WEIGHTS["friction"] / 100.0,
        }
    rows.sort(key=lambda x: -x["score"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    # ---- 稳健性：替代权重下的排名 ----
    for name, w in ALT_WEIGHTS.items():
        alt = sorted(rows, key=lambda x: -total(x, w))
        for i, r in enumerate(alt, 1):
            r.setdefault("alt_ranks", {})[name] = i
    for r in rows:
        rs = list(r.get("alt_ranks", {}).values())
        r["rank_min"], r["rank_max"] = min(rs + [r["rank"]]), max(rs + [r["rank"]])
        r["rank_stable"] = r["rank_max"] - r["rank_min"] <= 1

    out = dict(
        meta=dict(
            weights=WEIGHTS, alt_weights=ALT_WEIGHTS,
            normalization="收益/敞口/成本用组内 min-max；规模用分档绝对分；买入摩擦用绝对刻度",
            scale_bands=[{"nav_min": b[0], "score": b[1]} for b in SCALE_BANDS],
            note="限购额度未计入评分；申购状态仅作标注。等权重与主题指数已剔除。",
        ),
        ranking=rows,
    )
    json.dump(out, open(os.path.join(ROOT, "data", "score.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return out


def main():
    out = build()
    rows = out["ranking"]
    print("%-3s %-11s %7s %7s %7s %7s %7s %6s %6s %6s %6s %6s %6s"
          % ("#", "产品", "总分", "收益年化", "三年", "一年", "半年",
             "收益分", "敞口分", "成本分", "规模分", "摩擦分", "排名区间"))
    for r in rows:
        b = r["score_breakdown"]
        print("%-3d %-11s %7.2f %7.2f%% %6.1f%% %6.2f%% %6.2f%% %6.1f %6.1f %6.1f %6.2f %6.2f %4d-%d%s"
              % (r["rank"], r["short"], r["score"], r["ann_return"],
                 r["r3"] or 0, r["r1"] or 0, r["r6"],
                 b["长期收益兑现"], b["真实敞口"], b["持有成本"], b["规模与稳定"],
                 b["买入摩擦"], r["rank_min"], r["rank_max"],
                 "" if r["rank_stable"] else "  ← 敏感"))
    print("\nsaved -> data/score.json")


if __name__ == "__main__":
    main()
