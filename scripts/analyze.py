# -*- coding: utf-8 -*-
"""
把中报原始数据换算成可比指标。方法论沿用 B 站 @林怀瑾LHJ 的纳指基金拆解思路
（BV1rdet6MEXA），映射到中国跟踪标普 500 的标的。

指标定义
--------
1. 直接参与率      = (权益投资 + 基金投资 + 股指期货合约市值) / 期末净资产
2. 穿透后参与率    = 联接层持有的目标 ETF 部分，再乘目标 ETF 自己的参与率；
                    期货按合约市值（名义敞口）计 —— 公允价值被暂收款抵销为 0，不能看那个
3. 加权综合费率    = 目标 ETF 费率 + 本层费率 ×(1 − 目标 ETF 权重)
                     联接基金对目标 ETF 部分免收管理费/托管费；
                     QDII-FOF 持的是别人家的 ETF，无法豁免（双重收费）
4. 基准隐含指数收益 = (基准收益率 − 现金权重 × 活期利率) / 指数权重
5. 理论收益 / 缺口 = 穿透后参与率 × 基准隐含指数收益 − 实际净值增长率
6. 联接层相对目标ETF = (1+联接收益)/(1+目标ETF收益) − 1
7. 溢价调整后参与率 = 穿透后参与率 / (1 + 期末溢价率)

数据来源：各基金 2026 年中期报告（PDF 存于 data/pdf/）+ 天天基金公开行情接口。
输出 data/analysis.json
"""
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "quotes_cache.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 半年期人民币活期存款税后利率（%），用于从基准里剥离现金部分
R_CASH_HALF = 0.02

# 两个候选的统一指数口径（人民币计价，2026 上半年，%）：
#   6.60 = 博时标普500ETF 中报明确标注的 NTR（净总收益）基准收益率
#   6.16 = 国泰/南方 ETF 及多家 95/5 联接基金基准反推的口径
R_INDEX_HIGH = 6.60
R_INDEX_LOW = 6.16

PRODUCTS = [
    dict(code="513500", name="博时标普500ETF", short="博时ETF", kind="场内ETF",
         where="场内", index="标普500"),
    dict(code="159612", name="国泰标普500ETF", short="国泰ETF", kind="场内ETF",
         where="场内", index="标普500"),
    dict(code="159655", name="华夏标普500ETF", short="华夏ETF", kind="场内ETF",
         where="场内", index="标普500"),
    dict(code="513650", name="南方标普500ETF", short="南方ETF", kind="场内ETF",
         where="场内", index="标普500"),
    dict(code="050025", name="博时标普500ETF联接A", short="博时联接A", kind="场外ETF联接",
         where="场外", index="标普500", target="513500"),
    dict(code="017028", name="国泰标普500ETF发起联接A", short="国泰联接A", kind="场外ETF联接",
         where="场外", index="标普500", target="159612"),
    dict(code="018064", name="华夏标普500ETF发起式联接A", short="华夏联接A", kind="场外ETF联接",
         where="场外", index="标普500", target="159655"),
    dict(code="007721", name="天弘标普500发起(QDII-FOF)A", short="天弘FOF A", kind="场外QDII-FOF",
         where="场外", index="标普500"),
    dict(code="161125", name="易方达标普500指数(QDII-LOF)A", short="易方达LOF A", kind="场外QDII-LOF",
         where="场外", index="标普500"),
    dict(code="017641", name="摩根标普500指数(QDII)A", short="摩根A", kind="场外QDII直投",
         where="场外", index="标普500"),
]

# 场内 ETF 的行情代码（1.=沪市，0.=深市）
SECID = {"513500": "1.513500", "159612": "0.159612",
         "159655": "0.159655", "513650": "1.513650"}

# 天弘 FOF 实际持有的 6 只海外 ETF：占净值比取自其 2026 中报「前十名基金投资明细」；
# 费率列来自各 ETF 官网/招募说明书（非中报数据，仅用于估算双重收费）
FOF_HOLDINGS = [
    ("SPDR Portfolio S&P 500 ETF", 19.930, 0.02),
    ("SPDR S&P 500 ETF Trust", 19.883, 0.0945),
    ("Vanguard S&P 500 ETF", 19.874, 0.03),
    ("iShares Core S&P 500 ETF", 19.875, 0.03),
    ("iShares Core S&P 500 UCITS ETF", 8.526, 0.07),
    ("Invesco S&P 500 UCITS ETF", 2.967, 0.05),
]

TARGET_ETF = {"050025": "513500", "017028": "159612", "018064": "159655"}


# --------------------------------------------------------------------------- #
def fetch_prices():
    """取场内 ETF 的日收盘价（带本地缓存）。"""
    if os.path.exists(CACHE):
        return json.load(open(CACHE, encoding="utf-8"))
    out = {}
    for code, secid in SECID.items():
        u = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=%s"
             "&fields1=f1,f2,f3&fields2=f51,f53&klt=101&fqt=0&beg=20251215&end=20260710" % secid)
        req = urllib.request.Request(u, headers={"User-Agent": UA,
                                                "Referer": "https://quote.eastmoney.com/"})
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
            ks = (d.get("data") or {}).get("klines") or []
            out[code] = {x.split(",")[0]: float(x.split(",")[1]) for x in ks}
        except Exception as e:      # noqa: BLE001
            print("  ! %s 行情获取失败: %s" % (code, e))
    json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return out


def load():
    return json.load(open(os.path.join(ROOT, "data", "raw_reports.json"), encoding="utf-8"))


def index_weight(bench_def):
    """从业绩比较基准定义里抠出指数权重（95% / 100%）。"""
    if not bench_def:
        return 1.0
    m = re.search(r"×\s*(\d{2,3})\s*%", bench_def) or re.search(r"(\d{2,3})\s*%\s*[*×]", bench_def)
    return float(m.group(1)) / 100.0 if m else 1.0


def main_class(returns):
    """取 A 类（或唯一份额）作为该产品的代表份额。"""
    if not returns:
        return None, None
    for k, v in returns.items():
        if re.search(r"(?<![A-Za-z])A(?![A-Za-z])|主份额", k):
            return k, v
    return next(iter(returns.items()))


def last_on(prices, date):
    ks = sorted(k for k in prices if k <= date)
    return (ks[-1], prices[ks[-1]]) if ks else (None, None)


# --------------------------------------------------------------------------- #
def build():
    raw = load()
    prices = fetch_prices()
    recs = {}

    for p in PRODUCTS:
        r = raw.get("%s_semi" % p["code"])
        if not r:
            continue
        nav = r.get("nav_end") or 0
        pf = r.get("portfolio", {})
        fu = (r.get("futures") or {}).get("market_value") or 0.0
        fees = r.get("fees", {})
        bench_def = r.get("benchmark_def")
        w_idx = index_weight(bench_def)
        cls, ret = main_class(r.get("returns"))
        if not ret or not nav:
            continue

        equity_pct = 100.0 * (pf.get("equity") or 0) / nav
        fund_pct = 100.0 * (pf.get("fund_inv") or 0) / nav
        cash_pct = 100.0 * (pf.get("cash") or 0) / nav
        fut_pct = 100.0 * fu / nav
        direct = equity_pct + fund_pct + fut_pct

        bench_6m = ret["bench_6m"]
        r_index_own = (bench_6m - (1 - w_idx) * R_CASH_HALF) / w_idx

        rec = dict(
            code=p["code"], name=p["name"], short=p["short"], kind=p["kind"],
            where=p["where"], index=p["index"], period=r.get("period"), pdf=r.get("pdf"),
            nav_end=nav, nav_begin=r.get("nav_begin"),
            scale_chg_pct=(100.0 * (nav - r["nav_begin"]) / r["nav_begin"]
                           if r.get("nav_begin") else None),
            equity_pct=equity_pct, fund_pct=fund_pct, cash_pct=cash_pct,
            futures_pct=fut_pct, futures_mv=fu, direct_pct=direct,
            bench_def=bench_def, bench_weight=w_idx, bench_6m=bench_6m,
            r_index_own=r_index_own,
            class_label=cls, nav_6m=ret["nav_6m"], diff_6m=ret["diff_6m"],
            all_classes=r.get("returns"),
            mgmt=fees.get("mgmt_rate"), cust=fees.get("cust_rate"),
            mgmt_waiver=fees.get("mgmt_waiver"), cust_waiver=fees.get("cust_waiver"),
            mgmt_note=fees.get("mgmt_note"), cust_note=fees.get("cust_note"),
            raw_portfolio=(pf or {}).get("_raw"),
            raw_futures=(r.get("futures") or {}).get("_raw"),
        )

        # ---- 穿透后参与率 ----
        tgt = TARGET_ETF.get(p["code"])
        if tgt and ("%s_semi" % tgt) in raw:
            t = raw["%s_semi" % tgt]
            tnav = t["nav_end"]
            t_pf = t["portfolio"]
            t_fu = (t.get("futures") or {}).get("market_value") or 0.0
            t_ratio = 100.0 * ((t_pf.get("equity") or 0) + t_fu) / tnav
            penetrated = fund_pct * t_ratio / 100.0 + fut_pct + equity_pct
            rec["target_code"] = tgt
            rec["target_ratio"] = t_ratio
            rec["penetration_note"] = (
                "目标 ETF %s 自身参与率 %.2f%%（权益 %.2f%% + 期货 %.2f%%）"
                % (tgt, t_ratio, 100 * t_pf["equity"] / tnav, 100 * t_fu / tnav))
        elif p["code"] == "007721":
            uw = sum(w for _, w, _ in FOF_HOLDINGS)
            fee_w = sum(w * fe for _, w, fe in FOF_HOLDINGS) / uw
            penetrated = direct
            rec["target_code"] = "海外ETF组合"
            rec["target_ratio"] = 100.0
            rec["underlying"] = [dict(name=n, weight=w, fee=fe) for n, w, fe in FOF_HOLDINGS]
            rec["underlying_fee_weighted"] = fee_w
            rec["penetration_note"] = (
                "持有 6 只海外标普500 ETF（合计占净值 %.2f%%），底层 ETF 接近满仓，"
                "穿透后不再打折；底层费率加权约 %.3f%%" % (uw, fee_w))
        else:
            penetrated = direct
            rec["target_code"] = None
            rec["target_ratio"] = None
            rec["penetration_note"] = "直接持有股票，无目标基金层"

        rec["penetrated_pct"] = penetrated

        # ---- 理论收益 / 缺口 / 反推平均参与率 ----
        rec["theory_own"] = penetrated / 100.0 * r_index_own
        rec["gap_own"] = rec["theory_own"] - ret["nav_6m"]
        rec["implied_own"] = ret["nav_6m"] / r_index_own * 100.0
        rec["theory_high"] = penetrated / 100.0 * R_INDEX_HIGH
        rec["gap_high"] = rec["theory_high"] - ret["nav_6m"]
        rec["implied_high"] = ret["nav_6m"] / R_INDEX_HIGH * 100.0
        rec["theory_low"] = penetrated / 100.0 * R_INDEX_LOW
        rec["gap_low"] = rec["theory_low"] - ret["nav_6m"]
        rec["implied_low"] = ret["nav_6m"] / R_INDEX_LOW * 100.0
        rec["end_minus_avg_pp"] = penetrated - rec["implied_high"]
        rec["vs_bench_weight_pp"] = penetrated - w_idx * 100.0

        # ---- 加权综合费率 ----
        own = (fees.get("mgmt_rate") or 0) + (fees.get("cust_rate") or 0)
        rec["own_fee"] = own
        if tgt:
            tf = raw["%s_semi" % tgt]["fees"]
            etf_own = (tf.get("mgmt_rate") or 0) + (tf.get("cust_rate") or 0)
            rec["etf_fee"] = etf_own
            rec["comprehensive_fee"] = etf_own + own * (1 - fund_pct / 100.0)
            rec["fee_note"] = ("目标 ETF 费率 %.2f%% + 本层 %.2f%% ×(1−目标ETF权重 %.2f%%)，"
                               "本基金对目标 ETF 部分免收管理费/托管费"
                               % (etf_own, own, fund_pct))
        elif p["code"] == "007721":
            rec["etf_fee"] = rec.get("underlying_fee_weighted")
            rec["comprehensive_fee"] = own + (rec.get("underlying_fee_weighted") or 0) * fund_pct / 100.0
            rec["fee_note"] = ("本层 %.2f%% 全额计提（持别人家 ETF，无法豁免）"
                               "+ 底层 ETF 费率按权重摊到净值约 %.3f%%"
                               % (own, rec["comprehensive_fee"] - own))
        else:
            rec["etf_fee"] = None
            rec["comprehensive_fee"] = own
            rec["fee_note"] = "单层收费，直接持有股票/债券"

        # ---- 联接层相对目标 ETF ----
        if tgt and ("%s_semi" % tgt) in raw:
            _, t_ret = main_class(raw["%s_semi" % tgt]["returns"])
            if t_ret:
                rec["target_nav_6m"] = t_ret["nav_6m"]
                rec["vs_target_pp"] = ((1 + ret["nav_6m"] / 100.0)
                                       / (1 + t_ret["nav_6m"] / 100.0) - 1) * 100.0

        # ---- 场内溢价（仅场内 ETF）----
        if p["code"] in prices and prices[p["code"]]:
            px = prices[p["code"]]
            d0, p0 = last_on(px, "2025-12-31")
            d1, p1 = last_on(px, "2026-06-30")
            rec["quote"] = dict(date_begin=d0, price_begin=p0, date_end=d1, price_end=p1,
                                price_chg_pct=(p1 / p0 - 1) * 100.0)

        recs[p["code"]] = rec

    return recs


def enrich_premium(recs):
    """用「中报期末份额净值」与场内收盘价算溢价率。

    期末份额净值取自天天基金净值接口（与中报一致，已交叉验证）。
    注意：QDII 基金净值存在 T+1 披露时滞，同日「价格/净值」会放大溢价，
    因此同时给出「价格(T)/净值(T-1)」的时滞调整口径，两个口径都要看。
    """
    navps = json.load(open(os.path.join(ROOT, "data", "nav_per_share.json"), encoding="utf-8"))
    for code, q in ((c, recs[c].get("quote")) for c in recs):
        if not q or code not in navps:
            continue
        v = navps[code]
        q["nav_begin"] = v.get("nav_20251231")
        q["nav_end"] = v.get("nav_20260630")
        q["nav_prev_end"] = v.get("nav_20260629")
        if q["nav_begin"]:
            q["premium_begin"] = (q["price_begin"] / q["nav_begin"] - 1) * 100.0
        if q["nav_end"]:
            q["premium_end"] = (q["price_end"] / q["nav_end"] - 1) * 100.0
        if q.get("nav_prev_end"):
            q["premium_end_lagadj"] = (q["price_end"] / q["nav_prev_end"] - 1) * 100.0
        if q.get("premium_end"):
            recs[code]["premium_end"] = q["premium_end"]
            recs[code]["premium_adj_pct"] = recs[code]["penetrated_pct"] / (1 + q["premium_end"] / 100.0)


def main():
    recs = build()
    enrich_premium(recs)
    out = dict(
        meta=dict(
            source="各基金 2026 年中期报告（截至 2026-06-30），PDF 取自天天基金公开接口；"
                   "净值与场内价格取自天天基金/东方财富公开行情",
            methodology="B 站 @林怀瑾LHJ《同样跟踪纳斯达克 100，为什么国泰场外在前列？》"
                        "（BV1rdet6MEXA）的「参与率 / 穿透 / 加权费率」思路，映射到中国跟踪标普 500 的标的",
            r_index_high=R_INDEX_HIGH, r_index_low=R_INDEX_LOW, r_cash_half=R_CASH_HALF,
            caveat="各基金业绩比较基准口径不统一（含息/价格、估值汇率/人民币汇率、95% 或 100% 指数），"
                   "跨基金的「超额收益」不可直接横比。本报告把基准口径差异单独列出。",
        ),
        products=recs,
    )
    json.dump(out, open(os.path.join(ROOT, "data", "analysis.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("saved -> data/analysis.json\n")

    hdr = ("%-9s %-11s %7s %7s %7s %7s %7s %7s %7s %7s %7s %7s"
           % ("code", "short", "期末参率", "穿透后", "溢价调", "基准权", "净值6m", "基准6m",
              "理论6m", "缺口pp", "反推平", "综合费"))
    print(hdr)
    for c, r in sorted(recs.items(), key=lambda x: -x[1]["penetrated_pct"]):
        print("%-9s %-11s %7.2f %7.2f %7s %7.0f %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f" % (
            c, r["short"], r["direct_pct"], r["penetrated_pct"],
            ("%.2f" % r["premium_adj_pct"]) if r.get("premium_adj_pct") else "-",
            r["bench_weight"] * 100, r["nav_6m"], r["bench_6m"], r["theory_high"],
            r["gap_high"], r["implied_high"], r["comprehensive_fee"]))


if __name__ == "__main__":
    main()
