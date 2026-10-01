#!/usr/bin/env python3
"""把 Mermaid 源码编译成 SVG、离线 HTML 与 GitHub 可读的 Markdown。

渲染器是独立的文档工具，不加入 Agent 的业务依赖。修改 .mmd 后运行此脚本，
保证三种交付格式使用同一份图表内容。示例见生成的 Markdown 末尾。
"""

import argparse
import base64
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FLOWS = ROOT / "docs/flows"
REPO_URL = "https://github.com/BruceZM/design-agent-mvp"

PAGE = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>Design Agent MVP · 项目流程图</title>
<style>
:root{--ink:#202b38;--muted:#627083;--line:#dce3eb;--blue:#0878f9;--panel:#f5f7fa}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:30px}
body{margin:0;background:#fff;color:var(--ink);font:16px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
a{color:#126ac3;text-decoration:none}a:hover{text-decoration:underline}
button,.button{font:inherit;line-height:1.4;background:#fff;border:1px solid #cbd6e3;border-radius:7px;color:#3c4b5e;padding:7px 12px;cursor:pointer;white-space:nowrap}
button:hover,.button:hover{background:#edf6ff;border-color:#83b5ee;text-decoration:none}button:focus-visible,a:focus-visible{outline:3px solid #93c4ff;outline-offset:3px}
.page{max-width:1480px;margin:auto;padding:48px 40px 32px}.eyebrow{font-size:13px;letter-spacing:1.8px;color:#376ca7;font-weight:650}
h1{font-size:40px;line-height:1.3;letter-spacing:-1px;margin:12px 0}h2{font-size:26px;line-height:1.4;margin:0 0 10px}p{margin:0 0 16px}
.lede{max-width:860px;color:var(--muted);font-size:17px}.top-actions{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0 26px}.badge{background:#eef5fc;border:1px solid #d8e7f7;padding:4px 11px;border-radius:6px;color:#3d6388;font-size:13px}
.intro{padding:16px 20px;background:#f6f8fb;border:1px solid var(--line);border-radius:10px;margin-bottom:34px}.intro p{margin:0;color:#536174;font-size:14px}
.layout{display:grid;grid-template-columns:180px minmax(0,1fr);gap:30px;align-items:start}
nav{position:sticky;top:28px;padding-right:12px}nav span{display:block;font-size:12px;color:#8290a0;margin-bottom:10px}nav a{display:block;padding:9px 10px;margin-bottom:5px;border-radius:6px;color:#526176;font-size:14px}nav a:hover{background:#eef5fc;text-decoration:none;color:#126ac3}
.card{margin:0 0 42px;scroll-margin-top:28px;min-width:0}.card-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.tag{color:#537da6;font-size:12px;letter-spacing:1px;font-weight:650;margin-bottom:7px}.description{color:var(--muted);font-size:15px;max-width:850px}
.controls{display:flex;align-items:center;gap:7px;flex-wrap:wrap;padding:12px 14px;border:1px solid var(--line);border-bottom:0;border-radius:10px 10px 0 0;background:#fafbfd}.controls button{font-size:13px;padding:6px 10px}.scale{font-size:12px;color:#778699;min-width:43px;text-align:center}.download-group{display:flex;gap:7px;margin-left:auto}
.viewport{background:var(--panel);border:1px solid var(--line);border-radius:0 0 10px 10px;padding:24px 18px;max-height:920px;overflow:auto;overscroll-behavior:contain}.diagram{display:block;max-width:none;height:auto;margin:0 auto}
.notes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:16px}.note{font-size:13px;line-height:1.8;color:#59687a;background:#fff;border:1px solid #e7ecf2;padding:12px 14px;border-radius:8px}.note b{display:block;color:#34485e;font-size:12px;margin-bottom:3px}
.sources{font-size:12px;color:#8490a0;display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.sources a{color:#6c8096}
.footer{margin-top:38px;padding-top:22px;border-top:1px solid var(--line);font-size:13px;color:#7a8798}.footer p{margin:0 0 8px}#status{position:fixed;right:24px;bottom:20px;border:1px solid #cbd6e3;background:#fff;padding:9px 16px;border-radius:8px;box-shadow:0 3px 18px #202b3812;display:none;font-size:14px}
@media(max-width:850px){.page{padding:28px 18px}.layout{display:block}nav{position:static;display:flex;overflow:auto;gap:4px;margin-bottom:24px;padding:0}nav span{display:none}nav a{white-space:nowrap;background:#f5f7fa;margin:0}h1{font-size:31px}h2{font-size:22px}.notes{grid-template-columns:1fr}.viewport{padding:18px 12px}.card{margin-bottom:32px}.controls{gap:5px}.download-group{margin-left:0}button{font-size:12px}}
@media print{@page{size:A3 portrait;margin:14mm}body{font-size:12pt}.page{max-width:none;padding:0}header{break-after:page}.layout{display:block}nav,.controls,.top-actions,#status{display:none!important}.card{break-before:page;margin:0}.card:first-child{break-before:auto}.viewport{border-color:#cbd3df;max-height:none;overflow:visible;padding:12px}.diagram{width:auto!important;max-width:100%;max-height:265mm;height:auto}.notes{grid-template-columns:repeat(3,minmax(0,1fr))}.sources{font-size:9pt}h1{font-size:24pt}h2{font-size:20pt}.intro{margin-bottom:20px}}
</style>
</head>
<body>
<div class="page">
<header>
<div class="eyebrow">DESIGN AGENT / MVP DOCUMENTATION</div>
<h1>从设计稿到任务分支</h1>
<p class="lede">五张流程图，串起上传、后台执行、模型工具调用和代码交付。图中每一步均按当前实现整理，可对照源码阅读。</p>
<div class="top-actions"><span class="badge">React + FastAPI</span><span class="badge">LangGraph + LangChain</span><span class="badge">GLM-5.3-Flash</span><a class="button" href="../项目流程图.md" target="_blank" rel="noopener">阅读 Markdown 源文档</a><button type="button" id="print">打印 / 保存 PDF</button></div>
<div class="intro"><p><strong>当前版本：</strong>2026-10-01 · 固定本地 CRM · 单线程串行队列 · HTTP 轮询 · 默认一次检查修复。浅蓝表示处理节点，黄色表示判断，紫色表示编码工具，绿色 / 红色表示成功 / 失败结果，虚线表示异常路径或明确标出的人工步骤。</p></div>
</header>
<div class="layout"><nav aria-label="图表导航"><span>阅读顺序</span>__NAV__</nav><main>__CARDS__</main></div>
<footer class="footer"><p>HTML 内嵌五张 SVG，离线打开即可查看；源码位于 sources/，独立矢量图位于 svg/。页面缩放和导出使用浏览器原生功能，不依赖 CDN。</p><p>后台未实现自动浏览器 / 视觉验收、自动 GitHub 推送、RAG 或进程重启后的节点续跑。查看 <a href="https://github.com/BruceZM/design-agent-mvp">项目仓库</a> 或 <a href="https://github.com/mermaid-js/mermaid-cli">Mermaid CLI 渲染工具</a>。</p></footer>
</div><div id="status" role="status" aria-live="polite"></div>
<script>
// SVG 已嵌入页面；这里仅控制显示尺寸，不重新计算图表布局。
const statusBox = document.getElementById('status');
let statusTimer;
function report(message){statusBox.textContent=message;statusBox.style.display='block';clearTimeout(statusTimer);statusTimer=setTimeout(()=>statusBox.style.display='none',3500)}
function save(blob,name){const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
for(const card of document.querySelectorAll('.card')){
  const img=card.querySelector('.diagram'),viewport=card.querySelector('.viewport'),label=card.querySelector('.scale');
  const width=Number(img.dataset.width),height=Number(img.dataset.height);let scale=1;
  function fit(){const padding=parseFloat(getComputedStyle(viewport).paddingLeft)+parseFloat(getComputedStyle(viewport).paddingRight);return Math.min(1,(viewport.clientWidth-padding)/width)}
  function apply(value){scale=Math.max(.15,Math.min(3,value));img.style.width=(width*scale)+'px';label.textContent=Math.round(scale*100)+'%'}
  apply(fit());
  card.querySelector('[data-action="in"]').addEventListener('click',()=>apply(scale*1.25));
  card.querySelector('[data-action="out"]').addEventListener('click',()=>apply(scale/1.25));
  card.querySelector('[data-action="fit"]').addEventListener('click',()=>apply(fit()));
  // 解码嵌入的 SVG 字节，不通过 fetch 读取 file://，避免浏览器本地文件限制。
  const bytes=Uint8Array.from(atob(img.src.split(',')[1]),c=>c.charCodeAt(0));
  card.querySelector('[data-action="svg"]').addEventListener('click',()=>{save(new Blob([bytes],{type:'image/svg+xml'}),card.id+'.svg');report('SVG 已准备下载')});
  card.querySelector('[data-action="png"]').addEventListener('click',()=>{
    try{const ratio=Math.min(2,4608/width,4608/height),canvas=document.createElement('canvas');canvas.width=Math.ceil(width*ratio);canvas.height=Math.ceil(height*ratio);const context=canvas.getContext('2d');context.fillStyle='#f5f7fa';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(img,0,0,canvas.width,canvas.height);canvas.toBlob(blob=>{if(blob){save(blob,card.id+'.png');report('PNG 已准备下载')}else report('PNG 导出失败，请使用 SVG')},'image/png')}catch(error){report('PNG 导出失败，请使用 SVG')}
  });
  window.addEventListener('resize',()=>apply(fit()));
}
document.getElementById('print').addEventListener('click',()=>window.print());
</script>
</body>
</html>
'''


def svg_for_embedding(path):
    """用真实 viewBox 尺寸导出图片，避免百分比宽度导致 PNG 尺寸不确定。"""
    svg = path.read_text()
    # Mermaid CLI 的 SVG 可能含百分比尺寸，用 viewBox 得到稳定的固有宽高。
    # 保留内部矢量元素和样式，仅替换根尺寸，浏览器缩放和 canvas 导出都可复用。
    match = re.search(r'viewBox="([\d. -]+)"', svg)
    if not match:
        raise ValueError(f"SVG 缺少 viewBox: {path}")
    _, _, width, height = map(float, match.group(1).split())
    opening = re.search(r"<svg\b([^>]*)>", svg)
    attributes = re.sub(r'\s(?:width|height|style)="[^"]*"', "", opening.group(1))
    svg = svg[: opening.start()] + f'<svg{attributes} width="{width}" height="{height}">' + svg[opening.end() :]
    return svg, math.ceil(width), math.ceil(height)


def main():
    # 渲染器路径通过参数/环境/系统命令查找，文档工具不加入业务 package.json。
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--renderer", default=os.getenv("MMDC") or shutil.which("mmdc"))
    parser.add_argument("--puppeteer-config")
    args = parser.parse_args()
    if not args.renderer:
        parser.error("请安装 @mermaid-js/mermaid-cli，或用 --renderer 指定 mmdc 路径")
    diagrams = json.loads((FLOWS / "diagrams.json").read_text())
    (FLOWS / "svg").mkdir(exist_ok=True)
    nav, cards = [], []
    markdown = [
        "# Design Agent MVP 项目流程图\n",
        "日期：2026-10-01。按当前代码整理，默认模型为 `glm-5.3-flash`。\n",
        "推荐打开 [离线 HTML 展示页](flows/index.html)，支持缩放、下载 SVG/PNG 与打印。本文保存说明及 Mermaid 源码；GitHub 可以直接渲染代码块。\n",
    ]
    for number, item in enumerate(diagrams, 1):
        # 同一份 .mmd 分别用于独立 SVG、HTML 内嵌图和 Markdown 代码块，避免三份图漂移。
        name = item["id"]
        source, output = FLOWS / "sources" / f"{name}.mmd", FLOWS / "svg" / f"{name}.svg"
        command = [args.renderer, "-i", str(source), "-o", str(output), "-c", str(FLOWS / "mermaid-config.json"), "-b", "transparent"]
        if args.puppeteer_config:
            command += ["-p", args.puppeteer_config]
        subprocess.run(command, check=True)
        # argv 数组避免 shell 插值；任何渲染失败即停止，不能发布缺图的展示页。
        svg, width, height = svg_for_embedding(output)
        output.write_text(svg)
        encoded = base64.b64encode(svg.encode()).decode()
        # data URI 使 HTML 离线可读；HTML 文字转义，避免标题被当作标签解释。
        title, intro = html.escape(item["title"]), html.escape(item["intro"])
        nav.append(f'<a href="#{name}">{number:02d} · {title}</a>')
        notes = "".join(f'<div class="note"><b>阅读要点 {i}</b>{html.escape(note)}</div>' for i, note in enumerate(item["notes"], 1))
        links = "".join(f'<a href="{REPO_URL}/blob/main/{path}">{Path(path).name}</a>' for path in item["sources"])
        cards.append(f'''<section class="card" id="{name}"><div class="card-head"><div><div class="tag">{number:02d} / {html.escape(item['tag'])}</div><h2>{title}</h2><p class="description">{intro}</p></div></div>
<div class="controls" aria-label="{title}的图表操作"><button type="button" data-action="out" aria-label="缩小{title}">−</button><span class="scale">100%</span><button type="button" data-action="in" aria-label="放大{title}">+</button><button type="button" data-action="fit">适应宽度</button><div class="download-group"><button type="button" data-action="svg">下载 SVG</button><button type="button" data-action="png">下载 PNG</button></div></div>
<div class="viewport" tabindex="0" aria-label="{title}，放大后可滚动"><img class="diagram" alt="{title}流程图" data-width="{width}" data-height="{height}" width="{width}" height="{height}" src="data:image/svg+xml;base64,{encoded}"></div><div class="notes">{notes}</div><div class="sources"><span>对照源码</span>{links}</div></section>''')
        markdown.extend([f"## {number}. {item['title']}\n", item["intro"] + "\n", "```mermaid\n" + source.read_text().rstrip() + "\n```\n"])
        markdown.extend("- " + note for note in item["notes"])
        markdown.append("\n源码：" + "、".join(f"[{Path(p).name}](../{p})" for p in item["sources"]) + f"。独立矢量图：[SVG](flows/svg/{name}.svg)。\n")
    (FLOWS / "index.html").write_text(PAGE.replace("__NAV__", "".join(nav)).replace("__CARDS__", "\n".join(cards)))
    markdown.extend([
        "## 格式与维护\n",
        "HTML 用于展示，Markdown 用于阅读和版本维护，SVG 用于放入文档与演示。HTML 已嵌入矢量图，没有运行时 CDN 依赖。\n",
        "修改 `docs/flows/sources/*.mmd` 与 `diagrams.json` 后，使用独立的 [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) 重新生成；工具支持 SVG、PNG 与 PDF 渲染。\n",
        "```sh\nnpm install --prefix .publish/diagram-tools --no-save @mermaid-js/mermaid-cli@12.0.0\npython3 scripts/build-flow-docs.py --renderer .publish/diagram-tools/node_modules/.bin/mmdc\n```\n",
        "若使用系统 Chrome 而不下载 Puppeteer 浏览器，可为 CLI 提供 `--puppeteer-config` JSON，其中设置 `executablePath` 为本机 Chrome 路径。文档工具安装在被 Git 忽略的 `.publish/`，不会改变 Agent 的运行依赖。\n",
    ])
    (ROOT / "docs/项目流程图.md").write_text("\n".join(markdown))
    print("Generated five SVG diagrams, standalone HTML and Mermaid Markdown")


if __name__ == "__main__":
    main()
