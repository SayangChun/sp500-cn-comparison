# -*- coding: utf-8 -*-
"""
把 data/fund_profiles.json 渲染进 README 的「逐只深度剖析」章节。

用法：python scripts/build_profiles.py
读取：data/fund_profiles.json
写入：README.md（新增/替换 "## 逐只深度剖析" 到 "## 覆盖标的" 之间）
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = json.load(open(os.path.join(ROOT, "data", "fund_profiles.json"), encoding="utf-8"))
FUNDS = P["funds"]
META = P["meta"]


def v(x, default="—"):
    return default if x in (None, "", [], {}) else x


def build():
    out = []
    out.append("## 逐只深度剖析：经理 · 操作 · 纯度 · 态度")
    out.append("")
    out.append("> **2026-11-16 新增。** 前面的章节回答「哪只分数高」，这一节回答「分数是怎么来的、"
               "基金公司具体做了什么、谁在管、谁被善待」。覆盖 8 个维度：经理稳定性 / 操作方式 / "
               "追踪纯度 / 成本与让利 / 规模与流动性 / 溢价 / 对持有人态度 / 综合判断。")
    out.append("> 事实与判断分列：`事实` 来自年报与三季报原文，`判断` 是基于这些事实的推论。"
               "来源：2025 年报（运作与经理履历）、2026 三季报（现任经理与从业年限）、2026 中报（结构指标）。")
    out.append("")

    # ---------- 全景速览 ----------
    out.append("### 全景速览：一只一行")
    out.append("")
    out.append("| 产品 | 经理（任职） | 复制/期货 | 相对基准偏离 2025 | 降费 | 申购 | 一句话 |")
    out.append("|---|---|---|---:|:---:|:---|---|")
    for f in FUNDS:
        mgr = f["manager"]
        op = f["operation"]
        pur = f["purity"]
        att = f["attitude"]
        fut = op.get("futures", "")
        fut_short = "无期货" if ("无期货" in fut or "无股指期货" in fut) else (
            "补敞口" if "期货" in fut else "—")
        rep = "完全复制" if "完全复制" in op.get("replication", "") or "全复制" in op.get("replication", "") else (
            "FOF 组合" if "FOF" in op.get("replication", "") else ("目标ETF" if "目标 ETF" in op.get("replication", "") else "复制"))
        cut = "✓" if "✓" in att.get("fee_cut", "") else "✗"
        # 括号里常有「仅国泰暂停」这类说明，先截掉再判断，避免误判
        sub_raw = (att.get("subscribe", "") or "").split("（")[0]
        sub = ("暂停" if "暂停" in sub_raw else
               "限制大额" if "限制" in sub_raw else
               "正常" if "正常" in sub_raw else "—")
        mm = re.search(r"([+-]?\d+\.\d+)\s*pp", pur.get("bench_2025", "") or "")
        dev = ("%+s pp" % mm.group(1)) if mm else "—"
        out.append("| %s<br>`%s` | %s<br>%s | %s / %s | %s | %s | %s | %s |" % (
            f["short"], f["code"], v(mgr.get("name")), v(mgr.get("since")),
            rep, fut_short, dev, cut, sub, f["verdict"]["one"]))
    out.append("")
    out.append("> 「相对基准偏离」= 2025 年净值增长率 − 该基金自己披露的业绩基准增长率，"
               "衡量的是「跟自己比跟得准不准」，**不是**跨基金收益排名——各家基准口径从 11.00% 到 14.82% 不等。")
    out.append("")

    # ---------- 横向发现 ----------
    out.append("### 横向看：五个被表面数字掩盖的发现")
    out.append("")
    out.append("**1. 参与率最低的摩根 A，跟踪精度其实排第二。** 摩根 A 参与率 94.03% 全场垫底，"
               "但 2025 年相对自己基准只偏离 -0.13pp。它的 6% 现金是合同允许的 95% 仓位结构，"
               "不是操作失误；反过来，博时 ETF 参与率 99.77% 却偏离 -0.93pp——因为它的基准是含息 NTR，口径最严。"
               "**参与率衡量「钱进场没有」，跟踪偏离衡量「跟得准不准」，是两件事。**")
    out.append("")
    out.append("**2. 真正拉开长期差距的不是操作，是结构。** 天弘 FOF 参与率 95.19% 是场外最高，"
               "但持的是别人家 ETF、无法豁免管理费，双重收费让三年收益垫底（56.39%）。"
               "易方达 LOF 跟踪误差实测 0.14% 全场最扎实，但 1.00% 的费率全场最贵。"
               "**操作都做对了，输在层层收费和仓位结构。**")
    out.append("")
    out.append("**3. 经理稳定性与业绩没有必然关系，但和「谁在盯」有关。** 博时万琼 11 年、天弘胡超 7 年零变更；"
               "南方 2025 年原经理离任、增聘两位（含三个月共管期）、易方达 2025 年老将换新人。"
               "被动指数基金不依赖经理择时，所以换人没导致业绩塌方；但国泰艾小军同时管 17+ 只、"
               "国泰联接苗梦羽管 15+ 只，是判断「精细化管理程度」时必须知道的约束条件。")
    out.append("")
    out.append("**4. 降费是真金白银的让利，只有两家做过。** 博时（ETF + 联接）2025-01-27 托管费 "
               "0.25%→0.20%，天弘 FOF 2025-02-13 同步下调。其余八只没有主动降费记录。"
               "在这个维度上，博时和天弘对持有人更厚道——哪怕天弘的 FOF 结构本身仍偏贵。")
    out.append("")
    out.append("**5. 溢价是基金公司控制不了的、但你必须付的成本。** 四只 ETF 在 9-30 溢价 7.72%–10.21%，"
               "博时最高。国泰 ETF 已暂停申购、份额停止创设，溢价短期无法通过套利抹平。"
               "**基金本身再好，按溢价 10% 的场内价买入，也等于先亏近一成。** 这是全项目最该记住的一句话。")
    out.append("")

    # ---------- 逐只 ----------
    out.append("### 逐只拆解")
    out.append("")
    for i, f in enumerate(FUNDS, 1):
        m, op, pu, co, sc, pr, at, ve = (
            f["manager"], f["operation"], f["purity"], f["cost"],
            f["scale"], f["premium"], f["attitude"], f["verdict"])
        out.append("#### %d. %s `%s` · 综合第 %d 名（%.2f 分）" % (
            i, f["short"], f["code"], f["rank"], f["score"]))
        out.append("")
        out.append("**经理** ｜ %s ｜ 任职 %s（%.1f 年）｜ 证券从业 %s 年 ｜ %s" % (
            v(m.get("name")), v(m.get("since")), m.get("tenure_y", 0),
            v(m.get("experience_y")), v(m.get("role"))))
        out.append("")
        out.append("- 变动：%s" % v(m.get("change_note")))
        out.append("- 在管：%s" % v(m.get("concurrent")))
        out.append("- 判断：%s" % v(m.get("assessment")))
        out.append("")
        out.append("**操作** ｜ %s" % v(op.get("replication")))
        out.append("")
        for k, label in (("futures", "期货"), ("securities_lending", "证券出借"),
                         ("fx", "汇率"), ("cash_drag", "现金拖累"), ("rebalance", "调仓")):
            if op.get(k):
                out.append("- %s：%s" % (label, op[k]))
        out.append("")
        out.append("**追踪纯度** ｜ %s ｜ %s" % (v(pu.get("participation")), v(pu.get("bench_kind"))))
        out.append("")
        out.append("- 2025 年相对自己基准：%s" % v(pu.get("bench_2025")))
        out.append("- 三年相对基准：%s" % v(pu.get("gap_3y")))
        out.append("- 判断：%s" % v(pu.get("assessment")))
        out.append("")
        out.append("**成本与让利** ｜ 管理费 %.2f%% + 托管费 %.2f%% = 综合 %.2f%%%s" % (
            co.get("mgmt", 0), co.get("cust", 0), co.get("total", 0),
            ("；" + co["fee_cut"]) if co.get("fee_cut") else ""))
        out.append("")
        out.append("**规模与流动性** ｜ %s 亿（%s）｜ %s" % (
            v(sc.get("nav_yi")), v(sc.get("asof")), v(sc.get("note"))))
        out.append("")
        prem = v(pr.get("note"), "无显著溢价")
        if pr.get("p_0930"):
            prem += "（6/30 %+.2f%% → 9/30 %+.2f%% → 10/22 %+.2f%%）" % (
                pr["p_0630"], pr["p_0930"], pr["p_1022"])
        out.append("**溢价** ｜ %s" % prem)
        out.append("")
        out.append("**对持有人的态度** ｜ %s" % v(at.get("assessment")))
        out.append("")
        out.append("- 分红：%s" % v(at.get("dividend")))
        out.append("- 降费：%s ｜ 申购：%s" % (v(at.get("fee_cut")), v(at.get("subscribe"))))
        out.append("- 披露：%s ｜ 从业人员跟投：%s" % (v(at.get("disclosure")), v(at.get("insider"))))
        out.append("")
        out.append("**综合判断**：%s" % ve["one"])
        out.append("")
        out.append("| 优势 | 短板 |")
        out.append("|---|---|")
        pros = ve.get("pros", [])
        cons = ve.get("cons", [])
        for j in range(max(len(pros), len(cons))):
            out.append("| %s | %s |" % (
                ("✓ " + pros[j]) if j < len(pros) else "",
                ("✗ " + cons[j]) if j < len(cons) else ""))
        out.append("")
        out.append("> 适合：%s ｜ 不适合：%s" % (v(ve.get("fit")), v(ve.get("unfit"))))
        out.append("")
        out.append("---")
        out.append("")

    return "\n".join(out)


def main():
    section = build()
    path = os.path.join(ROOT, "README.md")
    s = open(path, encoding="utf-8").read()
    start = "## 逐只深度剖析"
    end = "## 覆盖标的"
    if start in s:
        i = s.index(start)
        j = s.index(end, i)
        s = s[:i] + section + "\n" + s[j:]
    else:
        j = s.index(end)
        s = s[:j] + section + "\n" + s[j:]
    open(path, "w", encoding="utf-8").write(s)
    print("README rebuilt with profiles: %d chars, section %d chars" % (len(s), len(section)))


if __name__ == "__main__":
    main()
