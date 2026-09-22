# -*- coding: utf-8 -*-
"""
把 data/analysis.json 渲染成单文件交互报告 index.html（无外部依赖，可离线打开）。

用法：python scripts/build_site.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "analysis.json")

TPL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>中国标普500标的横向对比 · 2026中报穿透分析</title>
<style>
:root{
  --bg:#f6f7f9; --panel:#ffffff; --ink:#1a1d21; --ink2:#4a5058; --ink3:#7c848e;
  --line:#e3e6ea; --line2:#eef1f4;
  --blue:#2563eb; --blue-bg:#eff4ff;
  --green:#0d9488; --green-bg:#e9f7f5;
  --amber:#b45309; --amber-bg:#fdf5e6;
  --red:#c0392b; --red-bg:#fdf0ee;
  --violet:#6d28d9; --violet-bg:#f4f0ff;
  --radius:10px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  font-size:14px;line-height:1.65;
}
.wrap{max-width:1180px;margin:0 auto;padding:32px 22px 80px}
h1{font-size:27px;line-height:1.35;margin:0 0 10px;letter-spacing:-.2px}
h2{font-size:19px;margin:44px 0 6px;letter-spacing:-.1px}
h2 .num{color:var(--ink3);font-weight:600;margin-right:8px;font-variant-numeric:tabular-nums}
h3{font-size:15px;margin:26px 0 8px}
p{margin:9px 0;color:var(--ink2)}
a{color:var(--blue);text-decoration:none}
a:hover{text-decoration:underline}
code{background:#eef1f4;padding:1px 5px;border-radius:4px;font-size:12.5px;
  font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
.sub{color:var(--ink3);font-size:13.5px;margin:0 0 4px}
.hero{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:26px 28px;margin-bottom:22px}
.tagrow{display:flex;flex-wrap:wrap;gap:7px;margin-top:14px}
.tag{background:var(--blue-bg);color:var(--blue);border-radius:999px;padding:3px 11px;font-size:12.5px;font-weight:500}
.tag.g{background:var(--green-bg);color:var(--green)}
.tag.a{background:var(--amber-bg);color:var(--amber)}
.tag.v{background:var(--violet-bg);color:var(--violet)}
.lede{font-size:15.5px;color:var(--ink);border-left:3px solid var(--blue);padding-left:14px;margin:16px 0 4px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(228px,1fr));gap:12px;margin:18px 0 6px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:15px 17px}
.card .k{font-size:12.5px;color:var(--ink3);margin-bottom:5px}
.card .v{font-size:22px;font-weight:650;font-variant-numeric:tabular-nums;letter-spacing:-.5px}
.card .d{font-size:12.5px;color:var(--ink3);margin-top:5px;line-height:1.5}
.tabs{display:flex;gap:4px;flex-wrap:wrap;margin:26px 0 0;border-bottom:1px solid var(--line)}
.tab{padding:9px 15px;border:none;background:none;cursor:pointer;font-size:13.5px;color:var(--ink3);
  border-bottom:2px solid transparent;font-family:inherit;font-weight:500}
.tab:hover{color:var(--ink)}
.tab.on{color:var(--blue);border-bottom-color:var(--blue)}
.panel{display:none;padding-top:18px}
.panel.on{display:block}
.tablebox{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius)}
table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
th,td{padding:9px 11px;text-align:right;border-bottom:1px solid var(--line2);white-space:nowrap}
th{background:#fafbfc;color:var(--ink2);font-weight:600;font-size:12.5px;position:sticky;top:0;
  cursor:pointer;user-select:none}
th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:var(--panel);z-index:1}
th:first-child{background:#fafbfc;z-index:2}
tbody tr:hover td{background:#fafbfc}
tbody tr:hover td:first-child{background:#fafbfc}
td.name{font-weight:600}
td .code{color:var(--ink3);font-weight:400;font-size:11.5px;margin-left:5px;font-family:ui-monospace,monospace}
.hi{color:var(--green);font-weight:650}
.lo{color:var(--red);font-weight:650}
.dim{color:var(--ink3)}
.bar{position:relative;height:8px;background:#eef1f4;border-radius:4px;min-width:64px;overflow:hidden}
.bar>i{position:absolute;left:0;top:0;bottom:0;border-radius:4px;background:var(--blue)}
.bar.g>i{background:var(--green)}
.bar.a>i{background:#d99a2b}
.chip{display:inline-block;padding:1px 7px;border-radius:5px;font-size:11.5px;font-weight:500}
.chip.etf{background:var(--blue-bg);color:var(--blue)}
.chip.link{background:var(--green-bg);color:var(--green)}
.chip.fof{background:var(--amber-bg);color:var(--amber)}
.chip.direct{background:var(--violet-bg);color:var(--violet)}
.chip.ew{background:#eef1f4;color:var(--ink2)}
.note{background:var(--amber-bg);border:1px solid #f0dcb4;border-radius:var(--radius);
  padding:13px 16px;margin:14px 0;font-size:13px;color:#6b4a10}
.note b{color:#7a4d05}
.note.blue{background:var(--blue-bg);border-color:#d3e0fb;color:#1e3a8a}
.note.blue b{color:#1e40af}
.note.gray{background:#f2f4f6;border-color:var(--line);color:var(--ink2)}
.note.gray b{color:var(--ink)}
ul,ol{color:var(--ink2);padding-left:22px;margin:9px 0}
li{margin:5px 0}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:var(--ink3);margin:9px 0 0}
.legend span{display:flex;align-items:center;gap:6px}
.dot{width:9px;height:9px;border-radius:3px;display:inline-block}
details{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:11px 15px;margin:8px 0}
details summary{cursor:pointer;font-weight:600;font-size:13.5px;color:var(--ink)}
details p,details li{font-size:13px}
.rawtext{background:#fafbfc;border:1px solid var(--line2);border-radius:7px;padding:10px 12px;
  font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:11.5px;color:var(--ink2);
  max-height:210px;overflow:auto;white-space:pre-wrap;word-break:break-all;line-height:1.7}
footer{margin-top:56px;padding-top:20px;border-top:1px solid var(--line);color:var(--ink3);font-size:12.5px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.mini{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:14px 16px}
.mini .t{font-weight:650;font-size:13.5px;margin-bottom:3px}
.mini .s{font-size:12.5px;color:var(--ink3)}
</style>
</head>
<body>
<div class="wrap">

<div class="hero">
  <p class="sub">2026 年中期报告穿透分析 · 数据截至 2026-06-30</p>
  <h1>中国境内跟踪标普 500 的标的：谁真的拿到了指数那部分钱？</h1>
  <p class="lede">同样跟踪标普 500，2026 上半年场外收益从 <b>5.55%</b> 到 <b>6.90%</b>，相差 1.35 个百分点。
  差异不来自"选股能力"，而来自三件事：<b>实际参与率</b>、<b>加权综合费率</b>、<b>场内溢价</b>。</p>
  <div class="tagrow">
    <span class="tag">__N__ 只产品</span>
    <span class="tag g">4 只场内 ETF</span>
    <span class="tag g">6 只场外</span>
    <span class="tag v">数据源：2026 中报 PDF</span>
  </div>
  <p class="sub" style="margin-top:12px">收录口径：仅<b>市值加权的纯标普 500 指数</b>产品。
  标普 500 等权重、标普 100 等权重、标普行业/主题指数（红利低波、油气、消费、生物科技等）均不收录。</p>
</div>

<h2><span class="num">01</span>关键发现</h2>
<div class="cards">
  <div class="card">
    <div class="k">期末参与率（穿透后）区间</div>
    <div class="v">__PEN_MIN__% – __PEN_MAX__%</div>
    <div class="d">场外产品没有一只真正做到 100%。最高的 <b>__PEN_TOP__</b> 为 __PEN_TOPV__%，
    最低的 <b>__PEN_BOT__</b> 只有 __PEN_BOTV__%。</div>
  </div>
  <div class="card">
    <div class="k">半年基准收益率最大口径差</div>
    <div class="v">__BENCH_SPREAD__ pp</div>
    <div class="d">同样是标普 500，博时 ETF 写 <b>6.60%</b>（NTR），国泰/南方 ETF 写 <b>6.16%</b>，
    纯指数口径本身就差 0.44pp；含 95/5 现金的场外产品最低只有 5.86%。跨基金的"超额收益"不能直接横比。</div>
  </div>
  <div class="card">
    <div class="k">费率误区实例</div>
    <div class="v">0.60% → __FEE_GAP__%</div>
    <div class="d">博时联接 A 页面上写管理费 0.60%，但按目标 ETF 权重加权后，
    综合管托为 <b>__FEE_COMP__%</b>。</div>
  </div>
  <div class="card">
    <div class="k">场内溢价调整后的参与率</div>
    <div class="v">96.4% – 98.4%</div>
    <div class="d">四只 ETF 期末均处溢价状态。按场内价买入，真正买到指数敞口的钱
    只有 96%–98%。</div>
  </div>
</div>

<h2><span class="num">02</span>方法论：从纳指 100 映射到标普 500</h2>
<p>本项目的分析框架来自 B 站 <a href="https://www.bilibili.com/video/BV1rdet6MEXA" target="_blank">@林怀瑾LHJ《同样跟踪纳斯达克 100，为什么国泰场外在前列？》</a>
（BV1rdet6MEXA，2026-09-19）。他把"为什么国泰纳指 100 长期稳居场外前列"拆成了三件事，本项目把同一套方法套到标普 500 上：</p>
<div class="tablebox"><table>
<thead><tr><th style="text-align:left">纳指 100 版（视频）</th><th style="text-align:left">标普 500 版（本项目）</th></tr></thead>
<tbody>
<tr><td style="text-align:left"><b>参与率</b>＝股票占比＋股指期货名义敞口。国泰：股票 80.96% ＋ 期货 19.10% ≈ 100%</td>
    <td style="text-align:left">同口径。国泰标普500ETF：权益 90.31% ＋ 期货 9.45% ＝ <b>99.76%</b>；场外最好的华夏联接穿透后 <b>95.07%</b></td></tr>
<tr><td style="text-align:left">期货公允价值被暂收款抵销为 0，<b>名义敞口要看「合约市值」</b></td>
    <td style="text-align:left">同。四只 ETF 合计持有 ES/HWAU 等标普 500 期货合约市值 __FUT_TOTAL__ 亿元</td></tr>
<tr><td style="text-align:left">南方：期末参与率 97.84%，但按收益反推半年平均只有约 93.5%——规模半年从 86.6 亿冲到 141.8 亿，建仓节奏拉低了平均仓位</td>
    <td style="text-align:left">加了「反推平均参与率＝半年净值增长率 ÷ 基准隐含指数收益」一列，用来识别同样的建仓摊薄</td></tr>
<tr><td style="text-align:left">费率误区：联接基金页面写 0.65% 不代表只收 0.65%，华泰柏瑞按 ETF 权重加权后实际约 0.97%</td>
    <td style="text-align:left">同。博时联接 A 页面 0.60%，加权综合 <b>__FEE_COMP__%</b>；天弘 QDII-FOF 持的是别人家 ETF，<b>无法豁免</b>，双重收费</td></tr>
<tr><td style="text-align:left">结论：长期业绩不来自花哨操作，而来自"有没有真的拿到指数那部分钱"</td>
    <td style="text-align:left">同，且标普 500 还多一层：<b>QDII 额度紧张导致场内 ETF 常年溢价</b>，买场内/买联接都要额外付这笔钱</td></tr>
</tbody></table></div>

<div class="tabs">
  <button class="tab on" data-t="p1">参与率与费率</button>
  <button class="tab" data-t="p2">收益与跟踪缺口</button>
  <button class="tab" data-t="p3">基准口径对照</button>
  <button class="tab" data-t="p4">规模变化</button>
  <button class="tab" data-t="p5">场内溢价</button>
  <button class="tab" data-t="p6">原始数据与出处</button>
</div>

<div class="panel on" id="p1">
  <p><b>参与率</b>衡量的是"基金净资产里有多少真的暴露在指数上"。名义参与率只算本层持仓；
  <b>穿透后参与率</b>再乘一层目标 ETF 自己的参与率——因为 ETF 自己也不是满仓。</p>
  <div class="tablebox"><table id="t1">
  <thead><tr>
    <th>产品</th><th>类型</th><th>权益</th><th>目标基金</th><th>期货(名义)</th>
    <th>直接参与率</th><th>穿透后参与率</th><th>vs 基准权重</th>
    <th>本层管托</th><th>加权综合费率</th>
  </tr></thead><tbody>__ROWS_P1__</tbody></table></div>
  <div class="legend">
    <span><i class="dot" style="background:var(--blue)"></i>场内 ETF</span>
    <span><i class="dot" style="background:var(--green)"></i>场外 ETF 联接</span>
    <span><i class="dot" style="background:#d99a2b"></i>场外 QDII-FOF / LOF</span>
    <span><i class="dot" style="background:var(--violet)"></i>场外直投</span>
  </div>
  <div class="note blue">
    <b>怎么读这张表：</b>「穿透后参与率」低于 100% 的部分，就是没有拿到指数收益的钱。
    场外产品普遍在 94%–95%，意味着在上涨行情里天然少赚 5 个点左右的指数涨幅；
    而这 5 个点里，一部分是合同允许的 5% 现金仓位（基准权重 95%），
    另一部分（如国泰联接 94.57% vs 基准 95%）则是实实在在的跑输。
  </div>
</div>

<div class="panel" id="p2">
  <p>把「穿透后参与率 × 基准隐含指数收益」当作<b>理论收益</b>，与实际净值增长率相减，得到<b>跟踪缺口</b>。
  缺口理论上应该接近该产品的年化综合费率的一半。</p>
  <div class="note">
    <b>重要口径警示：</b>各基金业绩比较基准的口径并不统一（含息/价格、估值汇率/人民币汇率、95% 或 100% 指数），
    半年基准收益从 __BENCH_MIN__% 到 __BENCH_MAX__% 不等，跨度 __BENCH_SPREAD__ 个百分点。
    因此下表的「理论收益」「缺口」用了两个统一口径分别计算（__R_HIGH__% 与 __R_LOW__%），
    请当作区间看，不要当点估计。
  </div>
  <div class="tablebox"><table id="t2">
  <thead><tr>
    <th>产品</th><th>净值增长率(A)</th><th>自己基准</th><th>①−③</th>
    <th>基准隐含指数</th><th>理论收益<br><span class="dim" style="font-weight:400">@__R_HIGH__%</span></th>
    <th>缺口 pp</th><th>理论收益<br><span class="dim" style="font-weight:400">@__R_LOW__%</span></th>
    <th>缺口 pp</th><th>反推平均参与率</th><th>期末−反推</th>
  </tr></thead><tbody>__ROWS_P2__</tbody></table></div>
  <div class="note gray">
    <b>「反推平均参与率」＝ 半年净值增长率 ÷ 基准隐含指数收益</b>，它包含全部成本，
    所以正常情况应该低于期末参与率，差值就是期内平均仓位偏低 + 各种隐性成本。
    这个指标在视频里被用来抓"规模快速膨胀摊薄仓位"的问题。
  </div>
</div>

<div class="panel" id="p3">
  <p>所有产品都声称跟踪标普 500，但业绩比较基准的写法差别很大。中报原文摘录如下（这是本项目所有收益口径的来源）：</p>
  <div class="tablebox"><table id="t3">
  <thead><tr><th>产品</th><th style="text-align:left">中报原文基准定义</th><th>指数权重</th><th>半年基准收益</th><th>反推指数收益</th></tr></thead>
  <tbody>__ROWS_P3__</tbody></table></div>
  <div class="note">
    <b>三点差异：</b>
    <ol>
      <li><b>含息与否：</b>博时 ETF 明确写 <code>NTR（Net Total Return，净总收益）</code>，
      其余多数只写"标普 500 指数收益率"。含息与价格指数半年能差 0.3–0.5 个百分点。</li>
      <li><b>汇率口径：</b>"经估值汇率调整"与"经人民币汇率调整"并存，估值时点不同会产生差异。</li>
      <li><b>指数权重：</b>场内 ETF 用 100% 指数，场外联接 / QDII-FOF 普遍用 95% 指数 + 5% 活期存款。</li>
    </ol>
  </div>
</div>

<div class="panel" id="p4">
  <p>规模变化是理解"参与率为什么不是 100%"的关键：半年内规模快速膨胀的产品，
  期内平均仓位会被建仓节奏拉低。</p>
  <div class="tablebox"><table id="t4">
  <thead><tr><th>产品</th><th>期初净资产</th><th>期末净资产</th><th>半年变化</th><th style="text-align:left">变化幅度</th></tr></thead>
  <tbody>__ROWS_P4__</tbody></table></div>
</div>

<div class="panel" id="p5">
  <p>场内 ETF 的<b>收盘价</b>与<b>份额净值</b>不是一回事。QDII 额度紧张时，场内价格会长期高于净值。
  联接基金持有目标 ETF，若按收盘价估值，这笔溢价也会进出联接的净值。</p>
  <div class="tablebox"><table id="t5">
  <thead><tr><th>ETF</th><th>期初收盘价</th><th>期初净值</th><th>期初溢价</th>
  <th>期末收盘价</th><th>期末净值</th><th>期末溢价</th><th>半年价格涨幅</th><th>半年净值涨幅</th>
  <th>溢价调整后参与率</th></tr></thead>
  <tbody>__ROWS_P5__</tbody></table></div>
  <div class="note">
    <b>口径提醒：</b>QDII 基金净值存在 T+1 披露时滞，同日「收盘价 ÷ 净值」会把隔夜美股涨跌算进溢价，
    从而系统性放大或缩小溢价率。本表给的是同日口径；严谨计算应使用 <code>价格(T) ÷ 净值(T-1)</code>，
    两端口径的差异已在下文「未能解释的部分」中说明。
  </div>
</div>

<div class="panel" id="p6">
  <p>每一项指标的原始出处。PDF 全文可通过 <code>python scripts/fetch_reports.py</code> 重新下载。</p>
  __RAW_BLOCKS__
</div>

<h2><span class="num">03</span>未能解释的部分</h2>
<p>按视频作者的提醒，指数基金的残余差异往往来自中报看不到的东西。以下四项本项目无法从公开中报中确证，如实列出：</p>
<div class="grid2">
  <div class="mini">
    <div class="t">① 联接基金跑赢自家目标 ETF</div>
    <div class="s">国泰联接 A 半年 <b>6.90%</b>，而其持有的国泰标普500ETF 只有 <b>6.27%</b>（+0.59pp）；
    华夏联接 A <b>6.81%</b> vs 华夏 ETF <b>6.51%</b>（+0.28pp）；博时联接则是 −0.09pp。
    联接持有 ETF 在数学上不可能超越 ETF 本身，除非估值口径不同。
    候选解释：联接按目标 ETF 的<b>收盘价</b>而非净值估值，QDII ETF 长期溢价，
    溢价路径变化会进出联接净值。但中报不披露估值方法与持仓明细，无法确证。</div>
  </div>
  <div class="mini">
    <div class="t">② 基准口径差 0.44pp</div>
    <div class="s">博时 ETF 基准半年 6.60%，国泰/南方 ETF 只有 6.16%。
    可能与 NTR / 价格指数、估值汇率 / 人民币汇率、以及指数收益的起止时点有关，
    但中报只给结论不给计算明细，无法拆分。</div>
  </div>
  <div class="mini">
    <div class="t">③ 缺口与综合费率对不上</div>
    <div class="s">博时联接 A 半年缺口约 0.15pp（年化 0.30%），但其加权综合费率为 0.86%／年。
    差额可能来自期内日均仓位高于期末、现金利息收入、期货展期收益，以及口径问题。</div>
  </div>
  <div class="mini">
    <div class="t">④ 参与率只有期末一个时点</div>
    <div class="s">中报只披露 6 月 30 日的持仓。规模半年翻倍的产品，期内平均参与率可能显著低于期末值，
    用期末值做理论收益会低估缺口。「反推平均参与率」是间接替代，但同样混入了费率与口径误差。</div>
  </div>
</div>

<h2><span class="num">04</span>复现</h2>
<div class="tablebox"><table>
<thead><tr><th style="text-align:left">步骤</th><th style="text-align:left">命令</th><th style="text-align:left">产出</th></tr></thead>
<tbody>
<tr><td style="text-align:left">1. 下载定期报告</td><td style="text-align:left"><code>python scripts/fetch_reports.py</code></td><td style="text-align:left"><code>data/reports_index.json</code>、<code>data/pdf/*.pdf</code></td></tr>
<tr><td style="text-align:left">2. 解析中报</td><td style="text-align:left"><code>python scripts/parse_reports.py</code></td><td style="text-align:left"><code>data/raw_reports.json</code></td></tr>
<tr><td style="text-align:left">3. 抓行情与净值</td><td style="text-align:left"><code>python scripts/fetch_quotes.py</code></td><td style="text-align:left"><code>data/quotes_cache.json</code>、<code>data/nav_per_share.json</code></td></tr>
<tr><td style="text-align:left">4. 穿透计算</td><td style="text-align:left"><code>python scripts/analyze.py</code></td><td style="text-align:left"><code>data/analysis.json</code></td></tr>
<tr><td style="text-align:left">5. 生成报告</td><td style="text-align:left"><code>python scripts/build_site.py</code></td><td style="text-align:left"><code>index.html</code></td></tr>
</tbody></table></div>
<div class="note gray">
  依赖：<code>pypdf</code>。数据源全部为公开接口：天天基金
  <code>api.fund.eastmoney.com</code> / <code>pdf.dfcfw.com</code>、腾讯行情 <code>web.ifzq.gtimg.cn</code>。
  净值增长率与场内价格已用独立接口交叉验证一致。
</div>

<footer>
  <p>数据来源：各基金 2026 年中期报告（截至 2026-06-30），场内行情与份额净值取自公开接口。
  方法论参考：B 站 @林怀瑾LHJ《同样跟踪纳斯达克 100，为什么国泰场外在前列？》（BV1rdet6MEXA）。</p>
  <p>本文仅作数据整理与结构化对比，不构成任何投资建议。所有"理论收益""缺口"均为基于公开中报的推算，
  受口径差异影响，请当作区间参考。</p>
  <p>报告生成时间：__GEN__</p>
</footer>

</div>
<script>
document.querySelectorAll('.tab').forEach(function(b){
  b.addEventListener('click',function(){
    document.querySelectorAll('.tab').forEach(function(x){x.classList.remove('on')});
    document.querySelectorAll('.panel').forEach(function(x){x.classList.remove('on')});
    b.classList.add('on');
    document.getElementById(b.dataset.t).classList.add('on');
  });
});
// 表头点击排序
document.querySelectorAll('table').forEach(function(tb){
  var ths=tb.querySelectorAll('thead th');
  ths.forEach(function(th,idx){
    th.addEventListener('click',function(){
      var body=tb.tBodies[0];
      var rows=Array.prototype.slice.call(body.rows);
      var dir=th.dataset.dir==='asc'?-1:1;
      th.dataset.dir=dir===1?'asc':'desc';
      var num=function(tr){
        var c=tr.cells[idx]; if(!c) return 0;
        var v=c.getAttribute('data-v');
        if(v!==null&&v!==undefined&&v!=='') return parseFloat(v);
        var m=c.textContent.replace(/[,%＋+]/g,'').match(/-?\d+(\.\d+)?/);
        return m?parseFloat(m[0]):0;
      };
      rows.sort(function(a,b){return (num(a)-num(b))*dir});
      rows.forEach(function(r){body.appendChild(r)});
    });
  });
});
</script>
</body>
</html>
"""


def pct(x, nd=2, sign=False):
    if x is None:
        return "—"
    s = ("{:." + str(nd) + "f}").format(x)
    return ("+" + s if sign and x > 0 else s) + "%"


def yi(x):
    return "—" if x is None else "{:.2f}".format(x / 1e8)


def chip(kind):
    m = {"场内ETF": ("etf", "场内ETF"), "场外ETF联接": ("link", "联接"),
         "场外QDII-FOF": ("fof", "QDII-FOF"), "场外QDII-LOF": ("fof", "QDII-LOF"),
         "场外QDII直投": ("direct", "QDII直投")}
    c, t = m.get(kind, ("ew", kind))
    return '<span class="chip %s">%s</span>' % (c, t)


def bar(v, lo, hi, cls=""):
    p = 0 if hi == lo else max(0, min(100, (v - lo) / (hi - lo) * 100))
    return ('<div class="bar %s"><i style="width:%.1f%%"></i></div>' % (cls, p))


def main():
    d = json.load(open(DATA, encoding="utf-8"))
    meta, P = d["meta"], d["products"]
    rows = list(P.values())

    main_rows = [r for r in rows if r["index"] == "标普500"]
    etf = [r for r in main_rows if r["kind"] == "场内ETF"]
    off = [r for r in main_rows if r["where"] == "场外"]

    # ---- 01 卡片 ----
    off_sorted = sorted(off, key=lambda r: -r["penetrated_pct"])
    pen_min, pen_max = off_sorted[-1], off_sorted[0]
    bj = [r for r in rows if r["code"] == "050025"][0]

    # ---- p1 参与率与费率 ----
    order = (sorted(etf, key=lambda r: -r["penetrated_pct"])
             + sorted(off, key=lambda r: -r["penetrated_pct"]))
    r1 = []
    for r in order:
        d1 = r["direct_pct"]
        d2 = r["penetrated_pct"]
        vs = r["vs_bench_weight_pp"]
        r1.append(
            "<tr>"
            '<td class="name">%s<span class="code">%s</span></td>'
            "<td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
            '<td data-v="%.4f">%s</td><td data-v="%.4f"><b>%.2f%%</b></td>'
            '<td data-v="%.4f" class="%s">%s</td>'
            '<td data-v="%.4f">%.2f%%</td><td data-v="%.4f">%.2f%%</td></tr>' % (
                r["short"], r["code"], chip(r["kind"]),
                pct(r["equity_pct"]) if r["equity_pct"] else "—",
                pct(r["fund_pct"]) if r["fund_pct"] else "—",
                pct(r["futures_pct"]) if r["futures_pct"] else "—",
                d1, pct(d1), d2, d2, vs,
                "hi" if vs > 0.05 else ("lo" if vs < -0.05 else "dim"),
                ("+" if vs > 0 else "") + "%.2f" % vs,
                r["own_fee"], r["own_fee"], r["comprehensive_fee"], r["comprehensive_fee"]))

    # ---- p2 收益与缺口 ----
    order2 = (sorted(etf, key=lambda r: -r["nav_6m"])
              + sorted(off, key=lambda r: -r["nav_6m"]))
    r2 = []
    for r in order2:
        em = r["end_minus_avg_pp"]
        r2.append(
            "<tr>"
            '<td class="name">%s<span class="code">%s</span></td>'
            '<td data-v="%.4f"><b>%.2f%%</b></td><td data-v="%.4f">%.2f%%</td>'
            '<td data-v="%.4f" class="%s">%s</td><td data-v="%.4f">%.2f%%</td>'
            '<td data-v="%.4f">%.2f%%</td><td data-v="%.4f" class="%s">%s</td>'
            '<td data-v="%.4f">%.2f%%</td><td data-v="%.4f" class="%s">%s</td>'
            '<td data-v="%.4f">%.2f%%</td><td data-v="%.4f" class="%s">%s</td></tr>' % (
                r["short"], r["code"], r["nav_6m"], r["nav_6m"], r["bench_6m"], r["bench_6m"],
                r["diff_6m"], "hi" if r["diff_6m"] > 0 else "lo",
                ("+" if r["diff_6m"] > 0 else "") + "%.2f" % r["diff_6m"],
                r["r_index_own"], r["r_index_own"],
                r["theory_high"], r["theory_high"],
                r["gap_high"], "hi" if r["gap_high"] < 0 else "dim",
                ("+" if r["gap_high"] > 0 else "") + "%.2f" % r["gap_high"],
                r["theory_low"], r["theory_low"],
                r["gap_low"], "hi" if r["gap_low"] < 0 else "dim",
                ("+" if r["gap_low"] > 0 else "") + "%.2f" % r["gap_low"],
                r["implied_high"], r["implied_high"], em,
                "lo" if em < 0 else "dim", ("+" if em > 0 else "") + "%.2f" % em))

    # ---- p3 基准口径 ----
    r3 = []
    for r in sorted(rows, key=lambda x: -x["bench_6m"]):
        bd = (r["bench_def"] or "—").replace("业绩比较基准为", "").replace("业绩比较基准", "")
        r3.append('<tr><td class="name">%s<span class="code">%s</span></td>'
                  '<td style="text-align:left;white-space:normal;min-width:340px">%s</td>'
                  '<td data-v="%.2f">%.0f%%</td><td data-v="%.4f"><b>%.2f%%</b></td>'
                  '<td data-v="%.4f">%.2f%%</td></tr>'
                  % (r["short"], r["code"], bd, r["bench_weight"] * 100, r["bench_weight"] * 100,
                     r["bench_6m"], r["bench_6m"], r["r_index_own"], r["r_index_own"]))

    # ---- p4 规模 ----
    r4 = []
    for r in sorted(rows, key=lambda x: -(x["scale_chg_pct"] or -999)):
        c = r["scale_chg_pct"] or 0
        r4.append('<tr><td class="name">%s<span class="code">%s</span></td>'
                  '<td data-v="%.0f">%s</td><td data-v="%.0f">%s</td>'
                  '<td data-v="%.4f" class="%s">%s</td>'
                  '<td style="text-align:left">%s</td></tr>'
                  % (r["short"], r["code"], r["nav_begin"] or 0, yi(r["nav_begin"]),
                     r["nav_end"] or 0, yi(r["nav_end"]), c,
                     "hi" if c > 0 else "lo", ("+" if c > 0 else "") + "%.1f%%" % c,
                     bar(c, -40, 70, "g" if c > 0 else "a")))

    # ---- p5 溢价 ----
    r5 = []
    for r in sorted(etf, key=lambda x: -(x.get("premium_end") or -99)):
        q = r.get("quote") or {}
        if not q.get("price_begin"):
            continue
        r5.append('<tr><td class="name">%s<span class="code">%s</span></td>'
                  '<td>%.3f</td><td>%.4f</td><td data-v="%.4f"><b>%s</b></td>'
                  '<td>%.3f</td><td>%.4f</td><td data-v="%.4f"><b>%s</b></td>'
                  '<td data-v="%.4f">%s</td><td data-v="%.4f">%s</td>'
                  '<td data-v="%.4f"><b>%s</b></td></tr>'
                  % (r["short"], r["code"],
                     q["price_begin"], q["nav_begin"], q.get("premium_begin", 0),
                     pct(q.get("premium_begin"), 2, True),
                     q["price_end"], q["nav_end"], q.get("premium_end", 0),
                     pct(q.get("premium_end"), 2, True),
                     q["price_chg_pct"], pct(q["price_chg_pct"], 2, True),
                     r["nav_6m"], pct(r["nav_6m"], 2, True),
                     r.get("premium_adj_pct", 0), pct(r.get("premium_adj_pct"))))

    # ---- p6 原始数据 ----
    blocks = []
    for r in sorted(rows, key=lambda x: x["code"]):
        cls = r["all_classes"] or {}
        cls_txt = "；".join("%s：净值 %s%% / 基准 %s%%" % (k, v["nav_6m"], v["bench_6m"])
                           for k, v in cls.items())
        inner = [
            "<p><b>资产组合</b>（占净值）：权益 %s、基金投资 %s、现金 %s、期货名义敞口 %s</p>"
            % (pct(r["equity_pct"]), pct(r["fund_pct"]), pct(r["cash_pct"]), pct(r["futures_pct"])),
            "<p><b>穿透说明</b>：%s</p>" % (r["penetration_note"] or "—"),
            "<p><b>费率</b>：本层管理费 %s%% + 托管费 %s%%；%s。豁免标记：管理费 %s／托管费 %s</p>"
            % (r["mgmt"], r["cust"], r["fee_note"],
               "有" if r["mgmt_waiver"] else "无", "有" if r["cust_waiver"] else "无"),
            "<p><b>各份额半年收益</b>：%s</p>" % (cls_txt or "—"),
        ]
        if r["mgmt_note"]:
            inner.append("<p><b>管理费附注原文</b></p><div class='rawtext'>%s</div>" % r["mgmt_note"])
        if r["cust_note"]:
            inner.append("<p><b>托管费附注原文</b></p><div class='rawtext'>%s</div>" % r["cust_note"])
        if r["raw_futures"]:
            inner.append("<p><b>期货合约原文</b></p><div class='rawtext'>%s</div>" % r["raw_futures"])
        if r["raw_portfolio"]:
            inner.append("<p><b>资产组合原文</b></p><div class='rawtext'>%s</div>" % r["raw_portfolio"])
        if r.get("underlying"):
            ul = "；".join("%s（占净值 %.2f%%，费率 %.4f%%）" % (u["name"], u["weight"], u["fee"])
                          for u in r["underlying"])
            inner.append("<p><b>底层持仓</b>：%s</p>" % ul)
        blocks.append("<details><summary>%s · %s <span class='dim'>（%s）</span></summary>%s</details>"
                      % (r["short"], r["code"], r["pdf"], "".join(inner)))

    fut_total = sum(r["futures_mv"] or 0 for r in rows) / 1e8
    html = (TPL
            .replace("__N__", str(len(rows)))
            .replace("__PEN_MIN__", "%.2f" % pen_min["penetrated_pct"])
            .replace("__PEN_MAX__", "%.2f" % pen_max["penetrated_pct"])
            .replace("__PEN_TOP__", pen_max["short"]).replace("__PEN_TOPV__", "%.2f" % pen_max["penetrated_pct"])
            .replace("__PEN_BOT__", pen_min["short"]).replace("__PEN_BOTV__", "%.2f" % pen_min["penetrated_pct"])
            .replace("__FEE_GAP__", "%.2f" % bj["comprehensive_fee"])
            .replace("__FEE_COMP__", "%.2f" % bj["comprehensive_fee"])
            .replace("__FUT_TOTAL__", "%.2f" % fut_total)
            .replace("__BENCH_MIN__", "%.2f" % min(r["bench_6m"] for r in rows))
            .replace("__BENCH_MAX__", "%.2f" % max(r["bench_6m"] for r in rows))
            .replace("__BENCH_SPREAD__", "%.2f" % (max(r["bench_6m"] for r in rows)
                                                   - min(r["bench_6m"] for r in rows)))
            .replace("__R_HIGH__", "%.2f" % meta["r_index_high"])
            .replace("__R_LOW__", "%.2f" % meta["r_index_low"])
            .replace("__ROWS_P1__", "".join(r1))
            .replace("__ROWS_P2__", "".join(r2))
            .replace("__ROWS_P3__", "".join(r3))
            .replace("__ROWS_P4__", "".join(r4))
            .replace("__ROWS_P5__", "".join(r5))
            .replace("__RAW_BLOCKS__", "".join(blocks))
            .replace("__GEN__", "2026-09-22"))
    out = os.path.join(ROOT, "index.html")
    open(out, "w", encoding="utf-8").write(html)
    print("saved -> index.html  (%.1f KB)" % (len(html.encode("utf-8")) / 1024))


if __name__ == "__main__":
    main()
