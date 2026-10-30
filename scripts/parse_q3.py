# -*- coding: utf-8 -*-
"""
解析 2026 年三季报（季度报告结构，与中报不同）。

季报能拿到：
  - 期末基金资产净值（按份额类别分列，需**求和**得到全基金口径）
  - 期末基金份额总额（同样按类别分列）
  - 资产组合：权益投资 / 基金投资 / 银行存款 / 其他各项资产 / 合计
  - 目标基金明细（占基金资产净值比例）
  - 报告期净值增长率与业绩比较基准（3.2.1）
  - 是否持有股指期货（但**只有公允价值，没有合约市值**）

季报拿不到：
  - 期货合约市值（名义敞口）→ 参与率无法按中报口径重算
  - 管理费/托管费年费率及豁免条款 → 沿用中报
  - 净资产变动表（期初/期末）

输出 data/q3_reports.json
"""
import json
import os
import re
import sys

from pypdf import PdfReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDFDIR = os.path.join(ROOT, "data", "pdf")
NUM = r"-?[\d,]+(?:\.\d+)?"

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from parse_reports import (extract_text, heal, flat, f, page_of,  # noqa: E402
                           parse_returns as parse_period_returns)

CODES = ["513500", "159612", "159655", "513650", "050025",
         "161125", "007721", "017028", "017641", "018064"]

PAIR = r"([\d,]+\.\d{2})\s*(\d{1,3}\.\d{2})"


def parse_nav_end(s):
    """期末基金资产净值：按份额类别分列，全部相加才是全基金口径。

    "4.期末基金资产净值6,347,591,513.011,243,166,238.672,442,507,236.275.期末基金份额净值…"
    """
    i = s.find("期末基金资产净值")
    if i < 0:
        return None, []
    j = s.find("期末基金份额净值", i)
    seg = s[i:j] if j > i else s[i:i + 260]
    vals = [f(x) for x in re.findall(r"[\d,]+\.\d{2}", seg)]
    vals = [v for v in vals if v and v > 1e6]
    return (sum(vals) if vals else None), vals


def parse_units(s):
    """期末基金份额总额（同样按类别分列）。"""
    i = s.find("期末基金份额总额")
    if i < 0:
        return None
    seg = s[i:i + 220]
    vals = [f(x) for x in re.findall(r"[\d,]+\.\d{2}", seg)]
    vals = [v for v in vals if v and v > 1e5]
    return sum(vals) if vals else None


def parse_portfolio(s):
    i = s.rfind("期末基金资产组合情况")
    if i < 0:
        return {}
    blk = s[i:i + 1400]
    res = {"_page": page_of(s, i)}
    for key, kw in (("equity", "权益投资"), ("fund_inv", "基金投资"),
                    ("cash", "银行存款和结算备付金合计"),
                    ("other_assets", "其他各项资产")):
        m = re.search(re.escape(kw) + r"\s*" + PAIR, blk)
        if m:
            res[key] = f(m.group(1))
            res[key + "_pct_total"] = f(m.group(2))
    m = re.search(r"(?<!备付金)合计\s*" + PAIR, blk)
    if m:
        res["total_assets"] = f(m.group(1))
    res["_raw"] = flat(blk[:900])
    return res


def parse_target_fund(s):
    i = s.rfind("期末投资目标基金明细")
    if i < 0:
        i = s.rfind("前十名基金投资明细")
    if i < 0:
        return None
    blk = flat(s[i:i + 700])
    m = re.search(r"([\d,]+\.\d{2})\s*(\d{1,3}\.\d{2})", blk[60:])
    if not m:
        return None
    return {"value": f(m.group(1)), "pct_nav": f(m.group(2)), "_raw": blk[:400]}


def parse_futures_presence(s):
    """季报只给期货公允价值（通常为 0），**没有合约市值**，无法算名义敞口。

    只能确认"是否仍持有期货合约"，用于说明参与率口径为何不可比。
    """
    occ = [m.start() for m in re.finditer("股指期货", s)]
    if not occ:
        return {"holds": False, "note": "季报未提及股指期货"}
    for o in occ:
        seg = flat(s[max(0, o - 60):o + 160])
        if "衍生品" in seg or "EMINI" in seg or "S&P" in seg.upper():
            return {"holds": True,
                    "contract": ("EMINI" if "EMINI" in seg.upper() else "?"),
                    "note": "季报仅披露期货公允价值（0），未披露合约市值，名义敞口不可得"}
    return {"holds": True, "contract": "?", "note": "季报提及股指期货但无明细"}


def parse_one(code):
    p = os.path.join(PDFDIR, "%s_q3.pdf" % code)
    if not os.path.exists(p):
        return None
    s = heal(extract_text(p))
    nav, parts = parse_nav_end(s)
    rec = {"code": code, "tag": "q3", "pdf": "data/pdf/%s_q3.pdf" % code,
           "nav_end": nav, "nav_parts": parts, "units_total": parse_units(s),
           "portfolio": parse_portfolio(s),
           "target_fund": parse_target_fund(s),
           "futures": parse_futures_presence(s),
           "returns": parse_period_returns(s)}
    m = re.search(r"报告期[（(]?\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
                  r"[^）)]*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", s)
    rec["period"] = ("%s-%02d-%02d~%s-%02d-%02d" % tuple(int(x) for x in m.groups())
                     if m else None)
    return rec


if __name__ == "__main__":
    out = {}
    for c in CODES:
        r = parse_one(c)
        if r:
            out[c] = r
    json.dump(out, open(os.path.join(ROOT, "data", "q3_reports.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
    print("saved -> data/q3_reports.json (%d)\n" % len(out))
    print("%-8s %16s %8s %8s %8s %8s %8s %6s" % (
        "code", "期末净资产", "权益%", "基金%", "现金%", "Q3净值", "Q3基准", "期货"))
    for c, r in out.items():
        nav = r["nav_end"] or 0
        pf = r["portfolio"]
        ret = next(iter(r["returns"].values()), {})
        q3 = (ret.get("periods") or {}).get("过去三个月", {})
        eq = 100 * (pf.get("equity") or 0) / nav if nav else 0
        fd = 100 * (pf.get("fund_inv") or 0) / nav if nav else 0
        ca = 100 * (pf.get("cash") or 0) / nav if nav else 0
        print("%-8s %16.0f %8.2f %8.2f %8.2f %8s %8s %6s" % (
            c, nav, eq, fd, ca,
            q3.get("nav", "—"), q3.get("bench", "—"),
            "有" if r["futures"]["holds"] else "无"))
