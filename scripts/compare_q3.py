# -*- coding: utf-8 -*-
"""生成「三季报 vs 中报」的对比数据，并重算窗口稳健性。输出 data/q3_compare.json"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda n: json.load(open(os.path.join(ROOT, "data", n), encoding="utf-8"))

sc = D("score.json")
q3 = D("q3_reports.json")
an = D("analysis.json")
lt = D("latest.json")
prev = D("score_20261022.json")
prevlt = D("latest_20261022.json")
rows = sc["ranking"]
P = {r["code"]: r for r in rows}
O = {r["code"]: r for r in prev["ranking"]}


def ann(p, y):
    return ((1 + p / 100) ** (1 / y) - 1) * 100


def minmax(v):
    lo, hi = min(v), max(v)
    return [100.0] * len(v) if hi == lo else [(x - lo) / (hi - lo) * 100 for x in v]


# ---------- 1. 排名变化 ----------
rank_chg = []
for r in rows:
    o = O[r["code"]]
    rank_chg.append({
        "code": r["code"], "short": r["short"],
        "old_rank": o["rank"], "new_rank": r["rank"],
        "old_score": o["score"], "new_score": r["score"],
        "delta": r["score"] - o["score"],
        "move": o["rank"] - r["rank"],
    })

# ---------- 2. 规模变化（中报 6/30 → 三季报 9/30）----------
scale = []
for r in rows:
    c = r["code"]
    a = an["products"][c]["nav_end"]
    b = q3[c]["nav_end"]
    scale.append({"code": c, "short": r["short"], "nav_0630": a, "nav_0930": b,
                  "chg_pct": (b - a) / a * 100 if a else None})

# ---------- 3. 持仓占比变化 ----------
hold = []
for r in rows:
    c = r["code"]
    a = an["products"][c]
    e = lt["products"][c]
    hold.append({
        "code": c, "short": r["short"],
        "eq_0630": a["equity_pct"], "eq_0930": e["equity_pct_q3"],
        "fund_0630": a["fund_pct"], "fund_0930": e["fund_pct_q3"],
        "fut_0630": a["futures_pct"], "holds_futures": e["holds_futures"],
        "penetrated_0630": a["penetrated_pct"],
    })

# ---------- 4. 溢价四时点 ----------
prem = []
for r in rows:
    c = r["code"]
    e = lt["products"][c]
    if "premium" not in e:
        continue
    prem.append({
        "code": c, "short": r["short"],
        "p_1y": e.get("premium_1y"),
        "p_0630": an["products"][c].get("premium_end"),
        "p_0930": e["premium"],
        "p_latest": (prevlt["products"].get(c) or {}).get("premium"),
        "adj_0930": e["premium_adj_pct"],
    })

# ---------- 5. 单季收益 ----------
quarter = []
for r in rows:
    c = r["code"]
    p = lt["products"][c]["periods"]
    q = p.get("过去三个月", {})
    quarter.append({"code": c, "short": r["short"],
                    "q3": q.get("nav"), "q3_bench": q.get("bench"),
                    "q3_diff": q.get("diff")})

# ---------- 6. 窗口稳健性（用三季报数据重算）----------
W = sc["meta"]["weights"]
variants = {
    "基准 3y50+1y30+6m20": lambda r: 0.5 * ann(r["r3"], 3) + 0.3 * r["r1"] + 0.2 * ann(r["r6"], 0.5),
    "只看近三年": lambda r: r["r3"],
    "只看近一年": lambda r: r["r1"],
    "只看近半年": lambda r: r["r6"],
}
ranks = {}
for name, fn in variants.items():
    vals = [fn(r) for r in rows]
    s = minmax(vals)
    tot = {r["code"]: (x * W["return"] + r["s_exposure"] * W["exposure"]
                       + r["s_cost"] * W["cost"] + r["s_scale"] / 12 * 100 * W["scale"]
                       + r["s_friction"] * W["friction"]) / 100
           for r, x in zip(rows, s)}
    for i, c in enumerate(sorted(tot, key=lambda k: -tot[k]), 1):
        ranks.setdefault(c, {})[name] = i
json.dump({"variants": list(variants), "ranks": ranks},
          open(os.path.join(ROOT, "data", "window_robust.json"), "w",
               encoding="utf-8"), ensure_ascii=False, indent=2)

out = {"asof": lt["asof"], "rank_chg": rank_chg, "scale": scale,
       "hold": hold, "premium": prem, "quarter": quarter}
json.dump(out, open(os.path.join(ROOT, "data", "q3_compare.json"), "w",
                    encoding="utf-8"), ensure_ascii=False, indent=2)

print("基准日 %s\n" % lt["asof"])
print("%-12s %5s %5s %8s %8s   %10s %10s   %6s %6s" % (
    "产品", "上次", "本次", "上次分", "本次分", "规模6/30", "规模9/30", "权益6/30", "权益9/30"))
for i, r in enumerate(rows):
    rc = next(x for x in rank_chg if x["code"] == r["code"])
    s = next(x for x in scale if x["code"] == r["code"])
    h = next(x for x in hold if x["code"] == r["code"])
    mv = rc["move"]
    m = "↑%d" % mv if mv > 0 else ("↓%d" % -mv if mv < 0 else "—")
    print("%-12s %5d %5d %8.2f %8.2f   %9.1f亿 %9.1f亿   %6.2f %6.2f" % (
        r["short"], rc["old_rank"], rc["new_rank"], rc["old_score"], rc["new_score"],
        s["nav_0630"] / 1e8, s["nav_0930"] / 1e8, h["eq_0630"], h["eq_0930"] or 0))
print("\n=== 溢价四时点 ===")
for p in prem:
    f = lambda v: ("%+7.2f%%" % v) if v is not None else "      —"
    print("  %-10s 25/10 %s | 26/6 %s | 26/9 %s | 26/10 %s" % (
        p["short"], f(p["p_1y"]), f(p["p_0630"]), f(p["p_0930"]), f(p["p_latest"])))
print("\n=== 窗口稳健性 ===")
for r in rows:
    d = ranks.get(r["code"], {})
    vals = [d.get(n, 0) for n in variants]
    print("  %-12s %s  跨度 %d" % (r["short"], " ".join("%2d" % v for v in vals),
                                   max(vals) - min(vals)))
print("\nsaved -> data/q3_compare.json, data/window_robust.json")
