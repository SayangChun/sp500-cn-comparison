# -*- coding: utf-8 -*-
"""
把三季报 + 市场数据合成「2026-09-30 快照」，覆盖 data/latest.json。

与中报的分工：
  - 参与率：季报**不披露期货合约市值**，无法按中报口径重算 → 评分仍用中报参与率，
    季报的「权益占比」只作为可比性说明
  - 费率：季报无费率附注 → 沿用中报
  - 规模：用季报期末净资产（按份额类别求和）
  - 多期收益：用季报 3.2.1 的官方区间（过去三个月/六个月/一年/三年），口径与报告一致
  - 溢价：2026-09-30 收盘价 ÷ 单位净值
  - 申购状态：最新

输出 data/latest.json（保持原 schema，score.py 无需改动）
"""
import json
import os
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
ASOF = "2026-09-30"
TX = {"513500": "sh513500", "159612": "sz159612",
      "159655": "sz159655", "513650": "sh513650"}
SUB_CODES = ["513500", "159612", "159655", "513650", "050025",
             "161125", "007721", "017028", "017641", "018064"]


def curl_json(url, referer="", retry=4):
    last = None
    for i in range(retry):
        try:
            cmd = ["curl", "-s", "--max-time", "45", "-A", UA]
            if referer:
                cmd += ["-H", "Referer: " + referer]
            out = subprocess.run(cmd + [url], capture_output=True, check=True).stdout
            return json.loads(out.decode("utf-8", "ignore"))
        except Exception as e:              # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def prices():
    out = {}
    for code, sym in TX.items():
        d = curl_json("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,"
                      "day,2026-09-01,2026-10-05,60," % sym)
        node = (d.get("data") or {}).get(sym) or {}
        ks = node.get("day") or node.get("qfqday") or []
        out[code] = {r[0]: float(r[2]) for r in ks}
        time.sleep(0.35)
    return out


def subscribe_status():
    out = {}
    for c in SUB_CODES:
        try:
            d = curl_json("https://api.fund.eastmoney.com/f10/lsjz?fundCode=%s&pageIndex=1"
                          "&pageSize=1" % c, "https://fundf10.eastmoney.com/jjjz_%s.html" % c)
            L = (d.get("Data") or {}).get("LSJZList") or []
            if L:
                out[c] = {"date": L[0]["FSRQ"], "sgzt": L[0].get("SGZT")}
        except Exception:                   # noqa: BLE001
            pass
        time.sleep(0.25)
    return out


def main():
    q3 = json.load(open(os.path.join(ROOT, "data", "q3_reports.json"), encoding="utf-8"))
    an = json.load(open(os.path.join(ROOT, "data", "analysis.json"), encoding="utf-8"))
    hist = json.load(open(os.path.join(ROOT, "data", "nav_history.json"), encoding="utf-8"))
    px = prices()
    subs = subscribe_status()

    prods = {}
    for code, rec in an["products"].items():
        r = q3.get(code)
        if not r:
            continue
        # 季报的 A 类区间收益
        first = next(iter(r["returns"].values()), {})
        periods = first.get("periods") or {}
        # 单位净值（算溢价用，不能用累计净值）
        ks = sorted(k for k in hist.get(code, {}) if k <= ASOF)
        nav_unit = hist[code][ks[-1]]["nav"] if ks else None
        pf = r["portfolio"]
        nav = r["nav_end"]
        entry = {
            "asof": ASOF,
            "periods": {k: v for k, v in periods.items()},
            "nav": nav_unit,
            "nav_scale": nav,
            "sgzt": (subs.get(code) or {}).get("sgzt"),
            # 季报可观测的持仓占比（不含期货，期货名义敞口季报不披露）
            "equity_pct_q3": 100 * (pf.get("equity") or 0) / nav if nav else None,
            "fund_pct_q3": 100 * (pf.get("fund_inv") or 0) / nav if nav else None,
            "cash_pct_q3": 100 * (pf.get("cash") or 0) / nav if nav else None,
            "holds_futures": r["futures"]["holds"],
            "futures_note": r["futures"]["note"],
            # 费率沿用中报
            "penetrated": rec["penetrated_pct"],
            "fee": rec["comprehensive_fee"],
            "penetrated_source": "2026 中报",
        }
        if code in px and px[code] and nav_unit:
            kk = sorted(k for k in px[code] if k <= ASOF)
            if kk:
                k = kk[-1]
                entry.update(price=px[code][k], price_date=k,
                             premium=(px[code][k] / nav_unit - 1) * 100.0)
                entry["premium_adj_pct"] = (rec["penetrated_pct"]
                                           / (1 + entry["premium"] / 100.0))
        prods[code] = entry

    out = {"asof": ASOF, "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
           "source": "2026 年第 3 季度报告", "products": prods, "subscribe": subs}
    json.dump(out, open(os.path.join(ROOT, "data", "latest.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)

    print("基准日 %s（三季报）\n" % ASOF)
    print("%-8s %14s %8s %8s %9s %9s %9s %9s %8s" % (
        "code", "期末净资产", "权益%", "基金%", "近三月", "近半年", "近一年", "近三年", "溢价"))
    for code, e in sorted(prods.items(), key=lambda x: -(x[1]["penetrated"])):
        p = e["periods"]
        g = lambda k: ("%8.2f%%" % p[k]["nav"]) if k in p else "       —"
        eq = e["equity_pct_q3"] if e["equity_pct_q3"] else e["fund_pct_q3"]
        prem = ("%+7.2f%%" % e["premium"]) if "premium" in e else "      —"
        print("%-8s %14.0f %8.2f %8.2f %s %s %s %s %s" % (
            code, e["nav_scale"], eq or 0, e["fund_pct_q3"] or 0,
            g("过去三个月"), g("过去六个月"), g("过去一年"), g("过去三年"), prem))
    print("\nsaved -> data/latest.json")


if __name__ == "__main__":
    main()
