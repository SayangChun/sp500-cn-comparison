# -*- coding: utf-8 -*-
"""
从 10 只基金的年度报告全文（data/txt/*_annual.txt）抽取"深度剖析"所需的一手片段：
产品说明（复制方法 / 跟踪误差目标 / 基准口径）、基金经理表、投资策略和运作分析、
业绩表现、持有人结构、转融通出借、股指期货、远期外汇、前十大持仓、境外托管人。

输出：data/profile_raw.json（供 build_profiles / 人工综合判断使用）

依赖：data/txt/*_annual.txt（由 fetch_reports.py 下载、parse_reports.py 抽取，走 .gitignore）
用法：python scripts/extract_profiles.py
"""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TXT = os.path.join(ROOT, "data", "txt")
OUT = os.path.join(ROOT, "data", "profile_raw.json")

CODES = ["513500", "513650", "159612", "159655", "050025",
         "017028", "018064", "007721", "161125", "017641"]


def clean(s):
    """去掉 PDF 分页标记与多余空白，保留段落换行。"""
    s = re.sub(r"<<<PAGE\s*\d+>>>", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def grab(s, start, end=None, maxlen=6000, start_off=0, nth=0):
    """从 start 模式第 nth 次匹配处（可偏移）截取到 end 模式或 maxlen。

    nth=1 用于跳过目录里的同名标题（年报正文标题通常在目录之后第二次出现）。
    """
    ms = list(re.finditer(start, s))
    if len(ms) <= nth:
        return ""
    m = ms[nth]
    i = m.start() + start_off
    j = len(s)
    if end:
        tail = s[m.end():]
        m2 = re.search(end, tail)
        if m2:
            j = m.end() + m2.start()
    return clean(s[i:min(j, i + maxlen)])


def extract(code):
    path = os.path.join(TXT, "%s_annual.txt" % code)
    if not os.path.exists(path):
        return {"code": code, "error": "missing %s" % path}
    s = open(path, encoding="utf-8").read()

    d = {"code": code}

    # 报告年度 / 基金基本要素
    m = re.search(r"(\d{4})\s*年年度报告", s)
    d["report_year"] = m.group(1) if m else ""
    d["contract_date"] = grab(s, r"基金合同生效日\s*(\d{4}\s*年\s*\d+\s*月\s*\d+\s*日)", maxlen=60)
    d["list_date"] = grab(s, r"上市日期\s*(\d{4}\s*年\s*\d+\s*月\s*\d+\s*日)", maxlen=60)
    d["operation_mode"] = grab(s, r"基金运作方式\s*([^\n]{1,40})", maxlen=60)

    # 产品说明：目录里也有同名标题，取第二次出现（正文）。
    # 章节编号不统一：多数是 2.2，摩根是 1.2
    d["product"] = grab(s, r"[12]\.2\s*基金产品说明", r"[12]\.3\s*基金管理人",
                        maxlen=7000, nth=1)
    if "投资目标" not in d["product"]:
        d["product"] = grab(s, r"[12]\.2\s*基金产品说明\s*\n\s*投资目标",
                            r"[12]\.3\s*基金管理人", maxlen=7000)

    # 2.4 境外投资顾问 / 境外托管人
    d["overseas"] = grab(s, r"2\.4\s*境外投资顾问和境外资产托管人", r"2\.5\s*信息披露方式", maxlen=2500)

    # 4.1.1 基金管理人经验（公司规模）
    d["company"] = grab(s, r"4\.1\.1\s*基金管理人及其管理基金的经验",
                        r"4\.1\.2\s*基金经理", maxlen=5000)

    # 基金经理表 + 简介（含任职/离任日期、证券从业年限、简历）
    # 章节编号不统一：博时/华夏/天弘是 4.1.2，摩根是 3.1.2
    d["manager"] = grab(s, r"[34]\.1\.2\s*基金经理（或基金经理小组）",
                        r"\n\s*[34]\.[23]\s|§\s*[45]|注：1", maxlen=14000)

    # 投资策略和运作分析（经理原话，含复制方法、期货、调仓、汇率）
    d["strategy"] = grab(s, r"投资策略和运作分析",
                         r"业绩表现|管理人对宏观经济|§\s*5|§5", maxlen=12000)

    # 报告期内基金的业绩表现（官方净值增长率 vs 基准）
    d["performance"] = grab(s, r"报告期内基金的业绩表现",
                            r"管理人对宏观经济|§\s*5|§5|4\.[78]", maxlen=4000)

    # 持有人结构（机构 / 个人）
    d["holders"] = grab(s, r"持有人户数及持有人结构", r"7\.\d|8\.\d|§\s*9|§9", maxlen=4500)

    # 转融通证券出借：实际出借余额 / 关联方交易
    d["sec_lend"] = grab(s, r"期末参与转融通证券出借业务的证券", r"7\.\d+\.\d+|§", maxlen=1800)
    d["sec_lend_rel"] = grab(s, r"转融通证券出借业务发生重大关联交易事项的说明",
                             r"7\.\d+\.\d+|§", maxlen=2200)

    # 股指期货持仓（年报"期末基金持有的期货合约情况"）
    d["futures"] = grab(s, r"期末基金持有的期货合约情况", r"7\.\d+\.\d+|8\.|§", maxlen=3000)

    # 远期 / 外汇合约（汇率管理）
    d["fx"] = grab(s, r"远期外汇合约|外汇远期|远期合约", r"7\.\d+\.\d+|8\.|§", maxlen=2500)

    # 前十大股票（看集中度 / REITs / 是否完全复制）
    d["top10"] = grab(s, r"前十名股票|前10名股票", r"5\.\d+\.\d+|6\.|§", maxlen=4500)

    # 跟踪偏离度 / 误差的定量描述（若报告披露）
    d["tracking"] = grab(s, r"日均跟踪偏离度|跟踪误差不超过|年跟踪误差", maxlen=1200)

    # 三季报（2026-09-30）经理表 —— 比年报新 9 个月，从业年限与"现任"以此为准
    q3path = os.path.join(TXT, "%s_q3.txt" % code)
    if os.path.exists(q3path):
        s3 = open(q3path, encoding="utf-8").read()
        d["manager_q3"] = grab(s3, r"基金经理（或基金经理小组）简介",
                               r"\n\s*4\.[23]\s|注：1|注:1", maxlen=9000)
        d["concurrent"] = grab(s3, r"同时管理的产品情况", r"\n\s*4\.[23]\s", maxlen=2000)
    else:
        d["manager_q3"] = ""
        d["concurrent"] = ""

    # ---- "对持有人态度"类的一手证据 ----
    # 利润分配（分红是否兑现、频率）—— 目录里也有同名标题，取正文
    d["dividend"] = grab(s, r"利润分配情况", r"7\.4\.12|8\.|§", maxlen=1500, nth=1)
    d["dividend_detail"] = grab(s, r"过去三年基金的利润分配情况\s*\n",
                                r"§|3\.4|3\.5|4\.", maxlen=2500, nth=1)
    # 从业人员自购 / 发起资金锁定份额（公司是否跟投、利益绑定）
    d["insider"] = grab(s, r"基金管理人的从业人员持有本基金的情况",
                        r"9\.[4-9]|§", maxlen=1600, nth=1)
    d["seed"] = grab(s, r"发起式基金发起资金持有份额情况|发起资金持有份额情况",
                     r"§|10\.", maxlen=1200, nth=1)
    # 管理费 / 托管费附注（是否主动降费让利）
    d["fee_note"] = grab(s, r"支付基金管理人[\s\S]{0,20}?管理人报酬按",
                         r"7\.4\.10\.2\.2|7\.4\.10\.3|§", maxlen=1800)
    d["cust_note"] = grab(s, r"支付基金托管人的托管费按",
                          r"7\.4\.10\.2\.3|7\.4\.10\.3|§", maxlen=1800)
    if not d["cust_note"]:
        d["cust_note"] = grab(s, r"支付基金托管人[\s\S]{0,20}?托管费按",
                              r"7\.4\.10\.2\.3|7\.4\.10\.3|§", maxlen=1800)
    # 审计意见（标准无保留 = 加分项）
    d["audit"] = grab(s, r"标准无保留意见|审计意见", maxlen=900)
    # 期末股票投资只数（复制完整度侧证）
    d["stock_count"] = grab(s, r"期末按公允价值占基金资产净值比例大小排序的所有股票投资明细",
                            r"6\.\d|7\.|§", maxlen=600)

    return d


def main():
    out = {"meta": {
        "source": "各基金年度报告全文（data/txt/*_annual.txt，来自基金定期报告公开披露）",
        "note": "自动抽取的一手片段，供逐只深度剖析；人工结论见 data/fund_profiles.json",
        "codes": CODES,
    }, "funds": {}}
    for code in CODES:
        out["funds"][code] = extract(code)
        d = out["funds"][code]
        print("%s  product=%d mgr=%d strategy=%d perf=%d holders=%d futures=%d fx=%d top10=%d"
              % (code, len(d.get("product", "")), len(d.get("manager", "")),
                 len(d.get("strategy", "")), len(d.get("performance", "")),
                 len(d.get("holders", "")), len(d.get("futures", "")),
                 len(d.get("fx", "")), len(d.get("top10", ""))))
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved ->", OUT)


if __name__ == "__main__":
    main()
