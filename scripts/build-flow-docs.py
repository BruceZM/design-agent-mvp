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
*{box-sizing:border-box}[hidden]{display:none!important}
html,body{margin:0;height:100%;overflow:hidden}
body{background:#fff;color:var(--ink);font:14px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
a{color:#126ac3;text-decoration:none}a:hover{text-decoration:underline}
button,.button{font:inherit;line-height:1.4;background:#fff;border:1px solid #cbd6e3;border-radius:7px;color:#3c4b5e;padding:6px 10px;cursor:pointer;white-space:nowrap}
button:hover,.button:hover{background:#edf6ff;border-color:#83b5ee;text-decoration:none}button:disabled{opacity:.4;cursor:default}
button:focus-visible,a:focus-visible,.viewport:focus-visible{outline:3px solid #93c4ff;outline-offset:3px}
.page{height:100vh;height:100dvh;display:grid;grid-template-rows:auto minmax(0,1fr) auto;gap:14px;padding:18px 24px}
.page-header{display:flex;align-items:center;justify-content:space-between;gap:18px;padding-bottom:12px;border-bottom:1px solid var(--line)}
.eyebrow{font-size:10px;letter-spacing:1.5px;color:#376ca7;font-weight:650}h1{font-size:22px;line-height:1.4;margin:2px 0 0;letter-spacing:-.4px}
.top-actions{display:flex;gap:8px;flex-shrink:0}.top-actions .button,.top-actions button{font-size:12px}
.layout{display:grid;grid-template-columns:174px minmax(0,1fr);gap:22px;min-height:0;min-width:0}
nav{min-height:0;overflow:auto;padding-right:4px}nav span{display:block;font-size:11px;color:#8290a0;margin-bottom:9px}
nav a{display:block;padding:10px 10px;margin-bottom:7px;border:1px solid transparent;border-radius:7px;color:#526176;font-size:13px;line-height:1.7}
nav a:hover{background:#f5f7fa;text-decoration:none}nav a[aria-current="page"]{background:#edf6ff;border-color:#c8dff8;color:#126ac3;font-weight:600}
main{min-height:0;min-width:0}.card{height:100%;min-height:0;min-width:0;display:grid;grid-template-rows:auto auto minmax(0,1fr)}
.card-head{margin-bottom:10px}.tag{font-size:10px;letter-spacing:1px;color:#537da6;font-weight:650}h2{font-size:20px;line-height:1.4;margin:2px 0 4px}
.description{color:var(--muted);font-size:12px;margin:0}.controls{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:8px 10px;border:1px solid var(--line);border-bottom:0;border-radius:9px 9px 0 0;background:#fafbfd}
.controls button{font-size:12px}.scale{min-width:40px;text-align:center;color:#778699;font-size:11px}.download-group{display:flex;gap:6px;margin-left:auto}
.viewport{min-height:0;min-width:0;background:var(--panel);border:1px solid var(--line);border-radius:0 0 9px 9px;padding:12px;overflow:auto;overscroll-behavior:contain}
.diagram{display:block;max-width:none;margin:0 auto}.reading{display:none}.notes{display:grid;gap:10px}.note{border:1px solid #e7ecf2;border-radius:8px;padding:12px 14px;color:#59687a;font-size:13px;line-height:1.8}.note b{display:block;font-size:12px;color:#34485e;margin-bottom:3px}
.sources{display:flex;gap:10px;flex-wrap:wrap;font-size:12px;color:#8490a0;margin-top:14px}.sources a{color:#6c8096}
.footer{display:flex;justify-content:space-between;align-items:center;gap:12px;color:#7a8798;font-size:11px}.legend{display:flex;gap:14px;flex-wrap:wrap}.legend span{display:inline-flex;align-items:center;gap:5px}.swatch{width:8px;height:8px;border-radius:2px;display:inline-block}
.pager{display:flex;align-items:center;gap:8px;flex-shrink:0}.pager button{font-size:11px;padding:4px 9px}.counter{min-width:35px;text-align:center}
dialog{padding:22px;border:1px solid var(--line);border-radius:12px;max-width:620px;width:calc(100% - 32px);max-height:calc(100dvh - 40px);color:var(--ink)}dialog::backdrop{background:#172c4855}.dialog-head{display:flex;justify-content:space-between;gap:20px;align-items:start;margin-bottom:12px}.dialog-description{color:var(--muted);font-size:13px;margin:0 0 14px}
#status{position:fixed;right:22px;bottom:55px;background:#fff;border:1px solid #cbd6e3;border-radius:8px;padding:8px 14px;font-size:13px;box-shadow:0 3px 18px #202b3812;display:none}
@media(max-width:850px){.page{padding:12px;gap:10px}.page-header{gap:10px;padding-bottom:8px}.eyebrow{font-size:9px}h1{font-size:18px}.layout{grid-template-columns:1fr;grid-template-rows:auto minmax(0,1fr);gap:10px}nav{display:flex;gap:5px;padding:0}nav span{display:none}nav a{white-space:nowrap;padding:6px 9px;margin:0;font-size:12px;background:#f5f7fa}h2{font-size:18px}.card-head{margin-bottom:8px}.description{font-size:11px}.legend{display:none}.footer{justify-content:flex-end}.controls{gap:4px;padding:7px}.controls button{font-size:11px;padding:5px 7px}.download-group{gap:4px}.viewport{padding:8px}}
@media(max-width:520px){.top-actions .button{display:none}.top-actions button{font-size:11px}.description{display:none}.tag{font-size:9px}.download-group{margin-left:0}.footer{font-size:10px}h1{font-size:17px}}
@media(max-height:540px){.page{padding:8px 12px;gap:7px}.eyebrow,.description{display:none}.page-header{padding-bottom:6px}h1{font-size:17px}.card-head{margin-bottom:5px}h2{font-size:16px}.controls{padding:5px 8px}.footer{font-size:10px}}
@media print{@page{size:A3 portrait;margin:14mm}html,body{height:auto;overflow:visible}.page{height:auto;display:block;padding:0}.page-header,nav,.controls,.footer,dialog,#status{display:none!important}.layout,main{display:block}.card,.card[hidden]{display:block!important;height:auto;break-before:page}.card:first-child{break-before:auto}.viewport{height:auto;overflow:visible;padding:12px}.diagram{width:auto!important;height:auto!important;max-width:100%;max-height:250mm;margin:0 auto!important}.reading{display:block}.notes{grid-template-columns:repeat(3,minmax(0,1fr));margin-top:16px}.description{display:block}.sources{font-size:9pt}h2{font-size:20pt}}
</style>
</head>
<body>
<div class="page">
<header class="page-header">
<div><div class="eyebrow">DESIGN AGENT / MVP DOCUMENTATION</div><h1>从设计稿到任务分支</h1></div>
<div class="top-actions"><a class="button" href="../项目流程图.md" target="_blank" rel="noopener">Markdown 源文档</a><button type="button" id="print">打印 / 保存 PDF</button></div>
</header>
<div class="layout"><nav aria-label="图表导航"><span>点击切换 · 每屏一张完整图</span>__NAV__</nav><main>__CARDS__</main></div>
<footer class="footer"><div class="legend"><span><i class="swatch" style="background:#a9dcff"></i>处理节点</span><span><i class="swatch" style="background:#ffe28e"></i>条件判断</span><span><i class="swatch" style="background:#c2b8fa"></i>编码工具</span><span>虚线：异常 / 人工步骤</span></div><div class="pager"><button type="button" id="previous">上一张</button><span class="counter" aria-live="polite"></span><button type="button" id="next">下一张</button></div></footer>
</div>
<dialog id="details"><div class="dialog-head"><h2 id="details-title"></h2><button type="button" id="close-details">关闭</button></div><div id="details-content"></div></dialog>
<div id="status" role="status" aria-live="polite"></div>
<script>
// 一次显示一张图；说明另放弹窗，不占图表的屏幕高度。
const cards=[...document.querySelectorAll('.card')],links=[...document.querySelectorAll('nav a')];
const fitters=new Map(),statusBox=document.getElementById('status'),details=document.getElementById('details');
let current=0,statusTimer;
function report(message){statusBox.textContent=message;statusBox.style.display='block';clearTimeout(statusTimer);statusTimer=setTimeout(()=>statusBox.style.display='none',2500)}
function save(blob,name){const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
for(const card of cards){
  const img=card.querySelector('.diagram'),viewport=card.querySelector('.viewport'),label=card.querySelector('.scale');
  const width=Number(img.dataset.width),height=Number(img.dataset.height);let scale=1,autoFit=true;
  function space(){const css=getComputedStyle(viewport);return {width:Math.max(1,viewport.clientWidth-parseFloat(css.paddingLeft)-parseFloat(css.paddingRight)-2),height:Math.max(1,viewport.clientHeight-parseFloat(css.paddingTop)-parseFloat(css.paddingBottom)-2)}}
  function apply(value){scale=Math.max(.001,Math.min(3,value));const room=space();img.style.width=width*scale+'px';img.style.height=height*scale+'px';img.style.marginTop=Math.max(0,(room.height-height*scale)/2)+'px';label.textContent=Math.round(scale*100)+'%'}
  function fit(){if(card.hidden)return;autoFit=true;const room=space();apply(Math.min(1,room.width/width,room.height/height));viewport.scrollTop=0;viewport.scrollLeft=0}
  // 宽度、高度同时参与缩放，不设 15% 的下限，窄屏也能先看到整张图。
  fitters.set(card.id,fit);
  new ResizeObserver(()=>{if(autoFit)fit()}).observe(viewport);
  card.querySelector('[data-action="in"]').addEventListener('click',()=>{autoFit=false;apply(scale*1.25)});
  card.querySelector('[data-action="out"]').addEventListener('click',()=>{autoFit=false;apply(scale/1.25)});
  card.querySelector('[data-action="fit"]').addEventListener('click',fit);
  card.querySelector('[data-action="details"]').addEventListener('click',()=>{
    document.getElementById('details-title').textContent=card.querySelector('h2').textContent;
    const content=document.getElementById('details-content');content.replaceChildren();
    const description=card.querySelector('.description').cloneNode(true);description.className='dialog-description';content.append(description);
    for(const child of card.querySelector('.reading').children)content.append(child.cloneNode(true));
    details.showModal();
  });
  // 导出始终使用原始 SVG，与显示缩放比例无关，避免导出模糊的小图。
  const bytes=Uint8Array.from(atob(img.src.split(',')[1]),c=>c.charCodeAt(0));
  card.querySelector('[data-action="svg"]').addEventListener('click',()=>{save(new Blob([bytes],{type:'image/svg+xml'}),card.id+'.svg');report('SVG 已准备下载')});
  card.querySelector('[data-action="png"]').addEventListener('click',()=>{
    try{const ratio=Math.min(2,4608/width,4608/height),canvas=document.createElement('canvas');canvas.width=Math.ceil(width*ratio);canvas.height=Math.ceil(height*ratio);const context=canvas.getContext('2d');context.fillStyle='#f5f7fa';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(img,0,0,canvas.width,canvas.height);canvas.toBlob(blob=>{if(blob){save(blob,card.id+'.png');report('PNG 已准备下载')}else report('PNG 导出失败，请使用 SVG')},'image/png')}catch(error){report('PNG 导出失败，请使用 SVG')}
  });
}
function show(index,updateHash=true){
  current=Math.max(0,Math.min(cards.length-1,index));
  cards.forEach((card,i)=>{card.hidden=i!==current;if(i===current)links[i].setAttribute('aria-current','page');else links[i].removeAttribute('aria-current')});
  document.querySelector('.counter').textContent=(current+1)+' / '+cards.length;
  document.getElementById('previous').disabled=current===0;document.getElementById('next').disabled=current===cards.length-1;
  if(updateHash)history.replaceState(null,'','#'+cards[current].id);
  requestAnimationFrame(()=>fitters.get(cards[current].id)());
}
links.forEach((link,i)=>link.addEventListener('click',event=>{event.preventDefault();show(i)}));
document.getElementById('previous').addEventListener('click',()=>show(current-1));
document.getElementById('next').addEventListener('click',()=>show(current+1));
document.getElementById('close-details').addEventListener('click',()=>details.close());
details.addEventListener('click',event=>{if(event.target===details)details.close()});
function fromHash(){const index=cards.findIndex(card=>'#'+card.id===location.hash);show(index<0?0:index,false)}
window.addEventListener('hashchange',fromHash);
// 真正改变窗口大小时重新适配；手动放大出现滚动条时保留用户缩放。
window.addEventListener('resize',()=>fitters.get(cards[current].id)());fromHash();
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
        "推荐打开 [离线 HTML 展示页](flows/index.html)，默认按屏幕宽高显示一张完整图，点击菜单切换，支持缩放、下载 SVG/PNG 与打印。本文保存说明及 Mermaid 源码；GitHub 可以直接渲染代码块。\n",
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
        cards.append(f'''<section class="card" id="{name}"{' hidden' if number > 1 else ''}><div class="card-head"><div><div class="tag">{number:02d} / {html.escape(item['tag'])}</div><h2>{title}</h2><p class="description">{intro}</p></div></div>
<div class="controls" aria-label="{title}的图表操作"><button type="button" data-action="out" aria-label="缩小{title}">−</button><span class="scale">100%</span><button type="button" data-action="in" aria-label="放大{title}">+</button><button type="button" data-action="fit">适应屏幕</button><div class="download-group"><button type="button" data-action="details">图解 / 源码</button><button type="button" data-action="svg">下载 SVG</button><button type="button" data-action="png">下载 PNG</button></div></div>
<div class="viewport" tabindex="0" aria-label="{title}，放大后可滚动"><img class="diagram" alt="{title}流程图" data-width="{width}" data-height="{height}" width="{width}" height="{height}" src="data:image/svg+xml;base64,{encoded}"></div><div class="reading"><div class="notes">{notes}</div><div class="sources"><span>对照源码</span>{links}</div></div></section>''')
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
