# -*- coding: utf-8 -*-
"""
把分析结果渲染成一组 SVG 图表，放进 assets/，供 GitHub README 直接内嵌显示。

为什么用 SVG 而不是 PNG：
  - 矢量、体积极小（几十 KB）、在任何缩放下都清晰；
  - 纯 <rect>/<text>/<path>，GitHub 的 SVG 清洗不会破坏；
  - 不依赖外部字体/脚本，离线也能渲染。

配色对深浅色主题都做了处理：图表自带浅色卡片底 + 深色文字，
在 GitHub 的 light / dark 两种主题下都能看清。

用法：python scripts/build_charts.py   -> assets/*.svg
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
os.makedirs(ASSETS, exist_ok=True)

FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',"
        "'Hiragino Sans GB','Microsoft YaHei',sans-serif")
MONO = "ui-monospace,SFMono-Regular,Consolas,monospace"

BG = "#fbfcfe"
INK = "#1a1d21"
INK2 = "#5b636d"
INK3 = "#8b939d"
GRID = "#e6e9ee"
C_ETF = "#2563eb"      # 场内 ETF
C_OFF = "#d97706"      # 场外
C1 = "#2563eb"         # 长期收益兑现
C2 = "#0d9488"         # 真实敞口
C3 = "#d97706"         # 持有成本
C4 = "#6d28d9"         # 规模与稳定
C5 = "#94a3b8"         # 买入摩擦
DIMS = [("长期收益兑现", 40, C1), ("真实敞口", 20, C2), ("持有成本", 20, C3),
        ("规模与稳定", 12, C4), ("买入摩擦", 8, C5)]


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def tw(s, size, bold=False):
    """粗略估算文本宽度：中文按 1em，其余按 0.56em。"""
    w = 0.0
    for ch in str(s):
        w += 1.0 if ord(ch) > 0x2E80 else 0.56
    return w * size * (1.06 if bold else 1.0)


def svg(w, h, body, title=None):
    head = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d" role="img">' % (w, h, w, h))
    if title:
        head += "<title>%s</title>" % esc(title)
    head += '<rect width="%d" height="%d" fill="%s" rx="10"/>' % (w, h, BG)
    return head + body + "</svg>"


def txt(x, y, s, size=12, fill=INK, anchor="start", bold=False, mono=False):
    return ('<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" fill="%s" '
            'text-anchor="%s"%s>%s</text>'
            % (x, y, MONO if mono else FONT, size, fill, anchor,
               ' font-weight="650"' if bold else "", esc(s)))


def rect(x, y, w, h, fill, rx=3, opacity=None):
    return ('<rect x="%.1f" y="%.1f" width="%.2f" height="%.2f" fill="%s" rx="%s"%s/>'
            % (x, y, max(0.0, w), max(0.0, h), fill, rx,
               ' opacity="%s"' % opacity if opacity else ""))


def load():
    sc = json.load(open(os.path.join(ROOT, "data", "score.json"), encoding="utf-8"))
    an = json.load(open(os.path.join(ROOT, "data", "analysis.json"), encoding="utf-8"))
    return sc, an


def color_of(r):
    return C_ETF if r["where"] == "场内" else C_OFF


# --------------------------------------------------------------------------- #
# 图 1：量化总分排名（横向条形 + 五维堆叠）
# --------------------------------------------------------------------------- #
def chart_rank_stack(rows):
    W, ROW, TOP, LEFT, RIGHT = 940, 40, 92, 190, 78
    H = TOP + ROW * len(rows) + 74
    b = []
    b.append(txt(24, 34, "标普 500 标的量化打分排名", 19, INK, bold=True))
    b.append(txt(24, 56, "五维加权，满分 100 ｜ 前四名全部是场内 ETF，与场外存在约 26 分断层",
                 12.5, INK2))
    # 图例
    lx = 24
    for name, full, col in DIMS:
        b.append(rect(lx, 70, 10, 10, col, 2))
        b.append(txt(lx + 15, 79, "%s /%d" % (name, full), 11.5, INK2))
        lx += 15 + tw("%s /%d" % (name, full), 11.5) + 18

    plot_w = W - LEFT - RIGHT
    for i, r in enumerate(rows):
        y = TOP + i * ROW
        if i % 2 == 1:
            b.append(rect(LEFT - 8, y - 3, plot_w + 16, ROW - 4, "#f2f5f9", 6))
        b.append(txt(LEFT - 14, y + 21, r["short"], 12.5, INK, anchor="end", bold=True))
        b.append(txt(LEFT - 14, y + 34, r["code"], 10, INK3, anchor="end", mono=True))
        # 排名徽标
        rk = r["rank"]
        bcol = "#0d9488" if rk <= 4 else ("#64748b" if rk <= 7 else "#c0392b")
        b.append(rect(18, y + 9, 22, 22, bcol, 6))
        b.append(txt(29, y + 24.5, str(rk), 12.5, "#ffffff", anchor="middle", bold=True))
        # 堆叠
        x = LEFT
        for name, full, col in DIMS:
            seg = r["score_breakdown"][name] / 100.0 * plot_w
            b.append(rect(x, y + 9, seg, 22, col, 0))
            if seg > 34:
                b.append(txt(x + seg / 2, y + 24.5, "%.1f" % r["score_breakdown"][name],
                             10.5, "#ffffff", anchor="middle", bold=True))
            x += seg
        b.append(txt(x + 10, y + 24.5, "%.2f" % r["score"], 13, INK, bold=True))
    # 轴
    y0 = TOP + ROW * len(rows)
    for v in range(0, 101, 20):
        gx = LEFT + v / 100.0 * plot_w
        b.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1"/>'
                 % (gx, TOP - 4, gx, y0 - 2, GRID))
        b.append(txt(gx, y0 + 15, str(v), 10.5, INK3, anchor="middle"))
    b.append(txt(LEFT + plot_w / 2, y0 + 34, "总分（五维加权）", 11.5, INK3, anchor="middle"))
    b.append(txt(24, y0 + 62, "注：各维度用组内 min-max 归一化——该维度最好的得满分、最差的得 0 分；"
                              "所以 0 分只代表「在这 10 只里最差」，不代表绝对差。", 11, INK3))
    open(os.path.join(ASSETS, "rank_score.svg"), "w", encoding="utf-8").write(
        svg(W, H, "".join(b), "标普500标的量化打分排名"))
    return W, H


# --------------------------------------------------------------------------- #
# 图 2：费率排名 vs 三年收益排名（bump chart）
# --------------------------------------------------------------------------- #
def chart_bump(rows):
    """左右两列排名对照，中间连线。直观看"低费率"与"高收益"是不是一回事。"""
    fees = sorted(rows, key=lambda r: (r["fee"], -r["r3"]))
    rets = sorted(rows, key=lambda r: -r["r3"])
    fee_rank = {r["code"]: i + 1 for i, r in enumerate(fees)}
    ret_rank = {r["code"]: i + 1 for i, r in enumerate(rets)}
    n = len(rows)
    W, H = 940, 108 + n * 46 + 96
    LX, RX = 352, 596
    TOP, GAP = 132, 46
    Y = lambda rank: TOP + (rank - 1) * GAP

    # Spearman 秩相关
    d2 = sum((fee_rank[r["code"]] - ret_rank[r["code"]]) ** 2 for r in rows)
    rho = 1 - 6 * d2 / (n * (n * n - 1))

    b = [txt(24, 34, "低费率 ≠ 好结果：费率排名与三年收益排名对照", 19, INK, bold=True),
         txt(24, 56, "左边按加权综合费率从低到高排，右边按过去三年收益从高到低排，连线越斜说明错位越大。",
             12.5, INK2),
         txt(24, 80, "Spearman 秩相关 ρ = %.2f —— 两者只有弱相关，费率低并不能保证收益高。" % rho,
             12.5, "#b45309", bold=True)]

    b.append(txt(LX, TOP - 30, "费率排名（1 = 最低）", 12, INK2, anchor="end", bold=True))
    b.append(txt(RX, TOP - 30, "三年收益排名（1 = 最高）", 12, INK2, bold=True))

    for i in range(n):
        yy = Y(i + 1)
        b.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" stroke-width="1"/>'
                 % (LX, yy, RX, yy, GRID))

    # 连线
    for r in rows:
        y1, y2 = Y(fee_rank[r["code"]]), Y(ret_rank[r["code"]])
        b.append('<path d="M %d %.1f C %d %.1f, %d %.1f, %d %.1f" fill="none" '
                 'stroke="%s" stroke-width="2.4" stroke-opacity="0.45"/>'
                 % (LX, y1, LX + 80, y1, RX - 80, y2, RX, y2, color_of(r)))

    # 两端标签与圆点
    for r in rows:
        c = r["code"]
        y1, y2 = Y(fee_rank[c]), Y(ret_rank[c])
        b.append(txt(LX - 16, y1 - 3, r["short"], 12, INK, anchor="end", bold=True))
        b.append(txt(LX - 16, y1 + 11, "%.2f%% · %.0f亿" % (r["fee"], r["nav"] / 1e8),
                     10.5, INK3, anchor="end"))
        b.append('<circle cx="%d" cy="%.1f" r="7" fill="%s"/>' % (LX, y1, color_of(r)))
        b.append('<circle cx="%d" cy="%.1f" r="7" fill="%s"/>' % (RX, y2, color_of(r)))
        b.append(txt(RX + 16, y2 - 3, r["short"], 12, INK, bold=True))
        b.append(txt(RX + 16, y2 + 11, "%.2f%% · 第%d名" % (r["r3"], ret_rank[c]),
                     10.5, INK3))

    b.append(txt(24, H - 52, "怎么读：博时 ETF 费率只排第 6，三年收益却排第 1；"
                             "摩根 A 费率最低（第 1），收益只排第 7。", 11.5, INK3))
    b.append(txt(24, H - 34, "场内 ETF 用蓝线、场外用橙线。四条蓝线全部落在右侧上半区，"
                             "说明场内 ETF 同时占据了「费率低」和「收益高」两端。", 11.5, INK3))
    b.append(txt(24, H - 14, "ρ 的算法：ρ = 1 − 6Σd² / (n(n²−1))，d 为同一只基金两侧的名次差；"
                             "ρ = 1 表示完全一致，0 表示完全无关。", 11, INK3))
    open(os.path.join(ASSETS, "rank_bump.svg"), "w", encoding="utf-8").write(
        svg(W, H, "".join(b), "费率排名与收益排名对照"))
    return W, H


# --------------------------------------------------------------------------- #
# 图 3：参与率对照（穿透后 + 溢价调整后）
# --------------------------------------------------------------------------- #
def chart_exposure(rows):
    W, ROW, TOP, LEFT, RIGHT = 940, 38, 96, 210, 150
    H = TOP + ROW * len(rows) + 62
    b = [txt(24, 34, "穿透后参与率：钱有多少真的进了指数", 19, INK, bold=True),
         txt(24, 56, "深色＝期末穿透后参与率；浅色＝再按场内溢价打折后的「有效参与率」。"
                     "场内 ETF 接近 100%，场外普遍只有 94–95%。", 12.5, INK2)]
    lx = 24
    for name, col in (("期末穿透后参与率", C2), ("溢价调整后（场内）", "#99f6e4")):
        b.append(rect(lx, 74, 10, 10, col, 2))
        b.append(txt(lx + 15, 83, name, 11.5, INK2))
        lx += 15 + tw(name, 11.5) + 22
    pw = W - LEFT - RIGHT
    lo, hi = 90.0, 101.0
    X = lambda v: LEFT + (v - lo) / (hi - lo) * pw
    for v in range(90, 102, 2):
        b.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1"/>'
                 % (X(v), TOP - 4, X(v), TOP + ROW * len(rows) - 2, GRID))
        b.append(txt(X(v), TOP + ROW * len(rows) + 15, "%d%%" % v, 10.5, INK3, anchor="middle"))
    for i, r in enumerate(rows):
        y = TOP + i * ROW
        b.append(txt(LEFT - 14, y + 17, r["short"], 12.5, INK, anchor="end", bold=True))
        b.append(txt(LEFT - 14, y + 30, r["code"], 10, INK3, anchor="end", mono=True))
        v1, v2 = r["penetrated"], r.get("premium_adj")
        b.append(rect(X(lo), y + 5, X(v1) - X(lo), 13, C2, 3))
        b.append(txt(X(v1) + 7, y + 15.5, "%.2f%%" % v1, 11.5, INK, bold=True))
        if v2:
            b.append(rect(X(lo), y + 20, X(v2) - X(lo), 9, "#99f6e4", 3))
            b.append(txt(X(v2) + 7, y + 28.5, "%.2f%%" % v2, 10.5, INK3))
    y0 = TOP + ROW * len(rows)
    b.append(txt(24, y0 + 46, "参与率 = (权益 + 目标基金 × 目标ETF参与率 + 股指期货合约市值) ÷ 期末净资产。"
                              "差出来的部分是现金与应收款，涨的时候就是少赚的钱。", 11, INK3))
    open(os.path.join(ASSETS, "exposure.svg"), "w", encoding="utf-8").write(
        svg(W, H, "".join(b), "穿透后参与率"))
    return W, H


# --------------------------------------------------------------------------- #
# 图 4：多期收益小倍数图
# --------------------------------------------------------------------------- #
def chart_returns(rows):
    W = 940
    PANELS = [("过去三年", "r3", 3), ("过去一年", "r1", 1), ("过去六个月", "r6", 0.5)]
    COLW = (W - 48) / 3.0
    ROW = 26
    TOP = 92
    H = TOP + ROW * len(rows) + 60
    b = [txt(24, 34, "多期净值增长率：场内与场外的差距随持有期拉长而放大", 19, INK, bold=True),
         txt(24, 56, "同一指数、同一区间、同一币种，净值增长率可直接横比。"
                     "半年差 1.35 个百分点，三年差到 10.9 个百分点。", 12.5, INK2)]
    for pi, (name, key, _y) in enumerate(PANELS):
        px = 24 + pi * COLW
        vals = [(r[key] or 0) for r in rows]
        lo, hi = min(vals), max(vals)
        labw = 118
        bw = COLW - labw - 62
        b.append(txt(px, TOP - 14, name, 13.5, INK, bold=True))
        for i, r in enumerate(rows):
            v = r[key] or 0
            y = TOP + i * ROW
            b.append(txt(px + labw - 8, y + 13, r["short"], 11, INK2, anchor="end"))
            w = 0 if hi == lo else (v - lo) / (hi - lo) * bw
            b.append(rect(px + labw, y + 3, max(w, 3), 13, color_of(r), 2))
            b.append(txt(px + labw + w + 6, y + 13, "%.2f%%" % v, 10.5, INK))
        b.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1"/>'
                 % (px + labw - 4, TOP - 6, px + labw - 4, TOP + ROW * len(rows), GRID))
    y0 = TOP + ROW * len(rows)
    b.append(txt(24, y0 + 30, "每列各自按 min-max 缩放，只用于看相对位置，不要跨列比较长度。",
                 11, INK3))
    open(os.path.join(ASSETS, "returns.svg"), "w", encoding="utf-8").write(
        svg(W, H, "".join(b), "多期收益对比"))
    return W, H


# --------------------------------------------------------------------------- #
# 图 5：场内溢价
# --------------------------------------------------------------------------- #
def chart_premium(rows):
    etfs = sorted([r for r in rows if r.get("premium") is not None],
                  key=lambda r: -r["premium"])
    W, H = 940, 400
    L, R, T, B = 92, 40, 88, 96
    pw, ph = W - L - R, H - T - B
    b = [txt(24, 34, "场内 ETF 期末溢价：买场内要多付这笔钱", 19, INK, bold=True),
         txt(24, 56, "溢价 = 收盘价 ÷ 份额净值 − 1。溢价越高，同样的钱买到的指数敞口越少。", 12.5, INK2)]
    hi = max(r["premium"] for r in etfs) + 1
    X = lambda v: L + v / hi * pw
    Y = lambda i: T + i * (ph / len(etfs))
    bh = ph / len(etfs) - 16
    for i, r in enumerate(etfs):
        y = Y(i)
        b.append(txt(L - 12, y + bh / 2 + 4, r["short"], 12.5, INK, anchor="end", bold=True))
        b.append(rect(L, y, X(r["premium"]) - L, bh, C_ETF, 3))
        b.append(txt(X(r["premium"]) + 9, y + bh / 2 + 5,
                     "%.2f%%　→ 有效参与率 %.2f%%" % (r["premium"], r["premium_adj"]),
                     11.5, INK, bold=True))
    for v in range(0, int(hi) + 1, 1):
        b.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1"/>'
                 % (X(v), T, X(v), T + ph, GRID))
        b.append(txt(X(v), T + ph + 17, "%d%%" % v, 10.5, INK3, anchor="middle"))
    b.append(txt(L + pw / 2, T + ph + 40, "2026-06-30 期末溢价率", 12, INK2, anchor="middle"))
    b.append(txt(24, H - 14, "口径提醒：QDII 净值有 T+1 披露时滞，同日「收盘价 ÷ 净值」会把隔夜美股涨跌"
                             "算进溢价。严谨计算应用「价格(T) ÷ 净值(T-1)」，两个口径都要看。", 11, INK3))
    open(os.path.join(ASSETS, "premium.svg"), "w", encoding="utf-8").write(
        svg(W, H, "".join(b), "场内溢价"))
    return W, H


def main():
    sc, an = load()
    rows = sc["ranking"]
    charts = [("rank_score.svg", chart_rank_stack(rows)),
              ("rank_bump.svg", chart_bump(rows)),
              ("exposure.svg", chart_exposure(rows)),
              ("returns.svg", chart_returns(rows)),
              ("premium.svg", chart_premium(rows))]
    for f, (w, h) in charts:
        p = os.path.join(ASSETS, f)
        print("  %-26s %4d x %-4d %6.1f KB" % (f, w, h, os.path.getsize(p) / 1024))
    print("saved -> assets/*.svg  (%d charts)" % len(charts))


if __name__ == "__main__":
    main()
