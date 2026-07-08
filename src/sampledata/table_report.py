"""サンプル結合テーブル(combined)の**対話的**可視化HTMLレポートを生成する。

外部通信ゼロの自己完結HTML(インラインCSS/JS、データはbase64埋め込み)。構成:
  ・左パネル … 選択条件(グループ / 各列の「値あり・なし・不問」)。条件に合う**サンプル数**を即時表示
  ・メイン   … 動的ヒートマップ(canvas)。行=該当サンプル(グループ順), 列=フィールド, 緑=有/赤=欠損
  ・下段     … 列カタログ(型・全体充足率、折りたたみ)

行グループは source/sheet から一意に決まる(血液/骨格筋/Sheet1育種価/NLBC母系/父)。

使い方:
    import table_report
    combined["group"] = table_report.add_group(combined)
    table_report.build_html_report(combined, "sample_table.html")

単独実行: python table_report.py [parquetパス]
"""
from __future__ import annotations

import base64
import html
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 行グループの表示順(ヒートマップの帯・件数の並び)
GROUP_ORDER = ["血液", "骨格筋", "Sheet1育種価", "高知大母", "NLBC母系", "父(種雄牛)"]

# 列のジャンル(ヒートマップに太い縦線を引く境界の判定用)
_META_COLS = {"source", "sheet", "group"}
_OTHER_COLS = {"sample_name", "チューブID", "ラックID", "ポジション", "説明／備考", "サンプルタイプ",
               "枝肉の写真", "SNP解析結果", "遺伝子型解析結果", "SNP解析結果.1", "遺伝子型解析結果.1"}


def _genre(col: str) -> str:
    """列を meta / main / phenotype / bv / other に分類。"""
    if col in _META_COLS:
        return "meta"
    if col in _OTHER_COLS:
        return "other"
    if col.startswith("bv_"):
        return "bv"
    if col.startswith("img_") or col.startswith("fa_") or re.match(r"^\d{2}_", col):
        return "phenotype"
    return "main"


def add_group(df: pd.DataFrame) -> pd.Categorical:
    """source/sheet から各行の由来グループを判定して順序付きCategoricalで返す。

      血液        : 旧血液Excel由来 かつ Sheet1以外(施設シート)
      骨格筋      : 骨格筋Excel由来
      Sheet1育種価: 旧血液ExcelのSheet1(育種価マスタ)
      NLBC母系    : NLBC検索で追加した祖先(source="NLBC")
      父(種雄牛)  : 名前基準で追加した父(source欠損)
    """
    src = df["source"].astype("string")
    sheet = df["sheet"].astype("string")
    g = pd.Series(pd.NA, index=df.index, dtype="object")
    is_muscle = src.str.contains("骨格筋", na=False)
    is_blood_file = src.str.contains("血液", na=False)
    is_sheet1 = sheet == "Sheet1"
    g[is_muscle] = "骨格筋"
    g[is_blood_file & ~is_sheet1] = "血液"
    g[is_blood_file & is_sheet1] = "Sheet1育種価"
    g[src.str.contains("cattle_management", na=False)] = "高知大母"
    g[src == "NLBC"] = "NLBC母系"
    g[src.isna()] = "父(種雄牛)"
    return pd.Categorical(g, categories=GROUP_ORDER, ordered=True)


def _fill_color(r: float) -> str:
    """充足率 r∈[0,1] を 赤(0)→黄(0.5)→緑(1) のRGB文字列に変換。"""
    red, yellow, green = (217, 83, 79), (240, 173, 78), (92, 184, 92)
    if r <= 0.5:
        a, b, t = red, yellow, r / 0.5
    else:
        a, b, t = yellow, green, (r - 0.5) / 0.5
    c = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return f"rgb({c[0]},{c[1]},{c[2]})"


def _catalog_html(df: pd.DataFrame, cols: list[str], n: int) -> str:
    """列カタログ(dtype / 非欠損 / 充足率バー)。折りたたみで下段に置く。"""
    rows = []
    for c in cols:
        is_bool = pd.api.types.is_bool_dtype(df[c])
        nn = int(df[c].fillna(False).sum()) if is_bool else int(df[c].notna().sum())  # bool=True数
        r = nn / n if n else 0.0
        lbl = "True数" if is_bool else "非欠損"
        bar = (f'<div class="bar"><div class="barfill" style="width:{r*100:.1f}%;'
               f'background:{_fill_color(r)}"></div></div>')
        rows.append(
            f"<tr><td class='mono'>{html.escape(c)}</td>"
            f"<td class='mono dt'>{html.escape(str(df[c].dtype))}</td>"
            f"<td class='num'>{nn:,}<span class='dt'> {lbl}</span></td>"
            f"<td class='num'>{r*100:.0f}%</td><td>{bar}</td></tr>")
    return ("<table class='catalog'><thead><tr>"
            "<th>列名</th><th>型</th><th>非欠損 / True数</th><th>率</th><th></th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


# ---- クライアント側 CSS / JS(ヒートマップ描画・条件フィルタ・件数集計) ----

_CSS = """
*{box-sizing:border-box}
body{font-family:-apple-system,'Segoe UI',sans-serif;margin:0;color:#222;background:#fafafa}
h1{font-size:18px;margin:0 0 2px} h2{font-size:15px;margin:26px 0 8px}
.meta{color:#666;font-size:12px}
header{padding:14px 18px;border-bottom:1px solid #e2e2e2;background:#fff}
.layout{display:flex;align-items:flex-start;gap:0;height:calc(100vh - 62px)}
#panel{width:310px;min-width:310px;height:100%;overflow-y:auto;border-right:1px solid #e2e2e2;
       background:#fff;padding:14px}
#main{flex:1;height:100%;overflow:auto;padding:10px}
.count{font-size:26px;font-weight:700;color:#2a7} .count small{font-size:13px;color:#888;font-weight:400}
.pergroup{font-size:12px;color:#555;margin:6px 0 4px;line-height:1.7}
.pergroup .sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 10px;vertical-align:middle}
.sec{font-size:12px;font-weight:700;color:#444;margin:14px 0 6px;border-bottom:1px solid #eee;padding-bottom:3px}
label.gk{display:block;font-size:13px;padding:2px 0;cursor:pointer}
.collist{max-height:40vh;overflow-y:auto;border:1px solid #eee;border-radius:4px}
.crow{display:flex;align-items:center;justify-content:space-between;padding:2px 6px;font-size:12px;
      border-bottom:1px solid #f4f4f4}
.crow .cn{font-family:monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.crow .cn.hidden{color:#bbb;text-decoration:line-through}
.crow .cright{display:flex;align-items:center;gap:6px;flex:none}
.visck{cursor:pointer;margin:0}
.tri{border:1px solid #ccc;border-radius:4px;font-size:11px;padding:1px 7px;cursor:pointer;background:#f7f7f7;
     min-width:52px;text-align:center;white-space:nowrap}
.tri.have{background:#d6efd6;border-color:#8ac48a;color:#1c6b1c}
.tri.none{background:#f6d6d6;border-color:#d59a9a;color:#8a1c1c}
button.reset{margin-top:10px;width:100%;padding:6px;border:1px solid #ccc;border-radius:5px;background:#f0f0f0;
             cursor:pointer;font-size:12px}
.legend{font-size:12px;color:#555;margin:2px 0 8px}
.chip{display:inline-block;width:12px;height:12px;border-radius:2px;vertical-align:middle;margin:0 4px}
canvas{background:#fff;display:block}
#hdr{position:sticky;top:0;z-index:3;background:#fff;border-bottom:1px solid #ccc}
#cv{border:1px solid #ddd;border-top:none}
details{margin:10px 18px 30px} summary{cursor:pointer;font-weight:700;font-size:15px;margin:8px 0}
table.catalog{border-collapse:collapse;font-size:12px}
.catalog td,.catalog th{border:1px solid #e2e2e2;padding:3px 8px}
.catalog th{background:#f0f0f0;text-align:left}
.mono{font-family:monospace}.dt{color:#777}.num{text-align:right;font-variant-numeric:tabular-nums}
.bar{width:120px;height:11px;background:#eee;border-radius:3px;overflow:hidden}.barfill{height:100%}
"""

_JS = """
const D = __DATA__;
const COLS = D.cols, GROUPS = D.groups, N = D.n, BPR = D.bpr;
const GROUP_COLORS = ['#4e79a7','#59a14f','#b07aa1','#f28e2b','#e15759','#9c755f'];
function b64bytes(s){const bin=atob(s);const a=new Uint8Array(bin.length);
  for(let i=0;i<bin.length;i++)a[i]=bin.charCodeAt(i);return a;}
const BITS = b64bytes(D.bits);   // N*BPR, big-endian bit order per row
const RG   = b64bytes(D.rg);     // N 主グループ(帯レイアウト用)
const MEMB = b64bytes(D.memb);   // N メンバーシップbitmask(1個体が複数グループに帰属しうる)
const present=(i,j)=>(BITS[i*BPR+(j>>3)]>>(7-(j&7)))&1;

let groupOn = GROUPS.map(()=>true);
let colCond = COLS.map(()=>0);   // 0=不問 1=値あり 2=欠損
let colVis  = COLS.map(()=>true);// 列の表示/非表示(フィルタ条件とは独立)
let rowHpx = Math.min(6, Math.max(0.3, 6000/N));   // 1行の高さ(px, スライダーで調整。<1=つぶす)

function checkedMask(){ let m=0; for(let k=0;k<GROUPS.length;k++) if(groupOn[k]) m|=(1<<k); return m; }
function matchIndices(){
  const cm=checkedMask(), idx=[], per=GROUPS.map(()=>0);
  for(let i=0;i<N;i++){
    if(!(MEMB[i] & cm)) continue;              // 選択グループのいずれかに帰属していれば対象
    let ok=true;
    for(let j=0;j<COLS.length;j++){
      const c=colCond[j]; if(!c) continue;
      const p=present(i,j);
      if((c===1&&!p)||(c===2&&p)){ok=false;break;}
    }
    if(ok){ idx.push(i); for(let k=0;k<GROUPS.length;k++) if(MEMB[i]&(1<<k)) per[k]++; }  // 複数グループにカウント
  }
  idx.sort((a,b)=> (RG[a]-RG[b]) || (a-b));   // 主グループ順→元順(帯レイアウト)
  return {idx, per};
}

const cv=document.getElementById('cv');      // 本体(ヒートマップ、縦スクロール)
const cvh=document.getElementById('cvh');    // 列名ヘッダ(sticky、常時表示)
const ML=96, MT=150, MR=12, MB=8;            // 余白(左=群ラベル, 上=列名)

function ctxOf(c,w,h){                        // HiDPI対応: DPR分だけ実解像度を上げて文字をシャープに
  const dpr=window.devicePixelRatio||1;
  c.width=Math.round(w*dpr); c.height=Math.round(h*dpr);
  c.style.width=w+'px'; c.style.height=h+'px';
  const x=c.getContext('2d'); x.setTransform(dpr,0,0,dpr,0,0); x.clearRect(0,0,w,h);
  return x;
}

function draw(idx){
  const nrow=idx.length;
  const vis=[]; for(let j=0;j<COLS.length;j++) if(colVis[j]) vis.push(j);   // 表示する列
  const nv=vis.length;
  const wrap=document.getElementById('main');
  const W=Math.max(760, wrap.clientWidth-24);
  const plotW=W-ML-MR, colW = nv ? plotW/nv : plotW;
  let rowH=rowHpx;
  if(nrow*rowH>30000) rowH=30000/nrow;         // canvas高さ上限(32767px)保護
  const cellH=Math.max(1,rowH);                // 描画セル高(<1でも最低1px, 位置は詰めて重ねる)
  const plotH=nrow*rowH;
  // 表示列だけでジャンル境界を再計算(隣り合う表示列でジャンルが変わる位置)
  const gb=[]; for(let p=1;p<nv;p++) if(D.genre[vis[p]]!==D.genre[vis[p-1]]) gb.push(p);

  // ---- 列名ヘッダ(sticky canvas) ----
  const hx=ctxOf(cvh, W, MT);
  hx.font='11px monospace'; hx.fillStyle='#222'; hx.textBaseline='middle';
  for(let p=0;p<nv;p++){
    const x=ML+p*colW+colW/2;
    hx.save(); hx.translate(x,MT-6); hx.rotate(-Math.PI/2);
    hx.textAlign='left'; hx.fillText(COLS[vis[p]],0,0); hx.restore();
  }
  hx.font='11px sans-serif'; hx.fillStyle='#666'; hx.textAlign='right'; hx.textBaseline='alphabetic';
  hx.fillText('群＼列', ML-6, MT-6);
  hx.strokeStyle='rgba(0,0,0,0.65)'; hx.lineWidth=2;      // ジャンル境界(太線)をヘッダにも
  for(const p of gb){ const x=ML+p*colW; hx.beginPath(); hx.moveTo(x,0); hx.lineTo(x,MT); hx.stroke(); }

  // ---- 本体(ヒートマップ + 左群ラベル) ----
  const bx=ctxOf(cv, W, plotH+MB);
  if(nv===0){ bx.fillStyle='#999'; bx.font='13px sans-serif'; bx.fillText('表示する列がありません', ML, 24); return; }
  const runs=[];
  for(let k=0;k<nrow;){ const g=RG[idx[k]]; let k2=k; while(k2<nrow&&RG[idx[k2]]===g)k2++; runs.push([g,k,k2]); k=k2; }
  for(const [g,k0,k1] of runs){
    for(let k=k0;k<k1;k++){
      const i=idx[k], ry=k*rowH;
      for(let p=0;p<nv;p++){
        bx.fillStyle=present(i,vis[p])?'#5cb85c':'#d9534f';
        bx.fillRect(ML+p*colW, ry, Math.ceil(colW), cellH);
      }
    }
    const y0=k0*rowH, y1=k1*rowH;
    bx.strokeStyle='#fff'; bx.lineWidth=1.5;
    bx.beginPath(); bx.moveTo(ML,y1); bx.lineTo(ML+plotW,y1); bx.stroke();
    bx.fillStyle=GROUP_COLORS[g]; bx.fillRect(ML-10,y0,6,Math.max(1,y1-y0));
    bx.textAlign='right'; bx.textBaseline='middle';
    bx.fillStyle='#333'; bx.font='11px sans-serif';
    bx.fillText(GROUPS[g], ML-14, (y0+y1)/2);
    bx.fillStyle='#999'; bx.font='9px sans-serif';
    bx.fillText('('+(k1-k0).toLocaleString()+')', ML-14, (y0+y1)/2+11);
  }

  // ---- 縦グリッド線(列区切り、細) ----
  bx.strokeStyle='rgba(0,0,0,0.28)'; bx.lineWidth=0.6;
  for(let p=0;p<=nv;p++){ const x=ML+p*colW; bx.beginPath(); bx.moveTo(x,0); bx.lineTo(x,plotH); bx.stroke(); }
  // ---- ジャンル境界(太線: meta/main/表現型/育種価/other の区切り) ----
  bx.strokeStyle='rgba(0,0,0,0.7)'; bx.lineWidth=2;
  for(const p of gb){ const x=ML+p*colW; bx.beginPath(); bx.moveTo(x,0); bx.lineTo(x,plotH); bx.stroke(); }
}

function refresh(){
  const {idx,per}=matchIndices();
  document.getElementById('count').innerHTML =
    idx.length.toLocaleString()+' <small>/ '+N.toLocaleString()+' サンプル該当</small>';
  document.getElementById('pergroup').innerHTML = GROUPS.map((g,k)=>
    "<span class='sw' style='background:"+GROUP_COLORS[k]+"'></span>"+g+": <b>"+per[k].toLocaleString()+"</b>"
  ).join('　');
  draw(idx);
}

// --- 左パネル生成 ---
function buildPanel(){
  const gc=document.getElementById('groups');
  GROUPS.forEach((g,k)=>{
    const l=document.createElement('label'); l.className='gk';
    l.innerHTML="<input type='checkbox' checked> <span class='sw' style='display:inline-block;width:10px;height:10px;border-radius:2px;background:"+GROUP_COLORS[k]+"'></span> "+g;
    l.querySelector('input').addEventListener('change',e=>{groupOn[k]=e.target.checked;refresh();});
    gc.appendChild(l);
  });
  const cl=document.getElementById('collist');
  const CLS=['','have','none'];
  COLS.forEach((c,j)=>{
    const LB = D.boolcols[j] ? ['不問','True','False'] : ['不問','値あり','欠損'];
    const row=document.createElement('div'); row.className='crow';
    const mark = D.boolcols[j] ? " ⚑" : "";     // bool列は値(True/False)で色分け/絞込
    const nm=document.createElement('span'); nm.className='cn';
    nm.title=c+(D.boolcols[j]?" (bool: 緑=True/赤=False)":""); nm.textContent=c+mark;
    const rt=document.createElement('span'); rt.className='cright';
    const vis=document.createElement('input'); vis.type='checkbox'; vis.checked=true;
    vis.className='visck'; vis.title='表示/非表示';
    vis.addEventListener('change',e=>{colVis[j]=e.target.checked; nm.classList.toggle('hidden',!e.target.checked); refresh();});
    const btn=document.createElement('span'); btn.className='tri'; btn.textContent='不問';
    btn.addEventListener('click',()=>{colCond[j]=(colCond[j]+1)%3;
      btn.textContent=LB[colCond[j]]; btn.className='tri '+CLS[colCond[j]]; refresh();});
    rt.appendChild(vis); rt.appendChild(btn);
    row.appendChild(nm); row.appendChild(rt); cl.appendChild(row);
  });
  const rh=document.getElementById('rowh');
  rh.min=0.3; rh.max=8; rh.step=0.1; rh.value=rowHpx;
  rh.addEventListener('input',e=>{rowHpx=parseFloat(e.target.value);refresh();});
  document.getElementById('reset').addEventListener('click',()=>{
    groupOn=GROUPS.map(()=>true); colCond=COLS.map(()=>0); colVis=COLS.map(()=>true);
    document.querySelectorAll('#groups input').forEach(i=>i.checked=true);
    document.querySelectorAll('#collist .tri').forEach(b=>{b.textContent='不問';b.className='tri';});
    document.querySelectorAll('#collist .visck').forEach(i=>i.checked=true);
    document.querySelectorAll('#collist .cn').forEach(n=>n.classList.remove('hidden'));
    refresh();
  });
}
buildPanel(); refresh();
let _t; window.addEventListener('resize',()=>{clearTimeout(_t);_t=setTimeout(refresh,150);});
"""


def build_html_report(df: pd.DataFrame, out_html, title: str = "サンプル結合テーブル レポート") -> Path:
    """combined を対話的に可視化した自己完結HTMLを out_html に書き出す。"""
    out_html = Path(out_html)
    n = len(df)
    cols = [c for c in df.columns if c != "group"]        # group列自体は可視化対象外

    # --- グループ(複数メンバーシップ対応) ---
    # group列は ";"区切りの複数ラベル(例 "Sheet1育種価;高知大母")。無ければ add_group(単一)にフォールバック
    _gi = {g: i for i, g in enumerate(GROUP_ORDER)}
    if "group" in df.columns:
        memb_lists = df["group"].fillna("").astype(str).apply(
            lambda s: [g for g in s.split(";") if g in _gi])
    else:
        _g = pd.Series(add_group(df), index=df.index)
        memb_lists = _g.apply(lambda g: [g] if (pd.notna(g) and g in _gi) else [])
    memb_lists = list(memb_lists)

    def _primary(ms):                                     # 帯レイアウト用の主グループ(GROUP_ORDER順で先頭)
        for g in GROUP_ORDER:
            if g in ms:
                return g
        return None
    prim = [_primary(ms) for ms in memb_lists]

    # 各列の bit を計算: 通常列=値の有無(notna) / bool列=値そのもの(True/False)
    boolcols = [bool(pd.api.types.is_bool_dtype(df[c])) for c in cols]
    present = np.empty((n, len(cols)), dtype=bool)
    for j, c in enumerate(cols):
        present[:, j] = (df[c].fillna(False).to_numpy(dtype=bool) if boolcols[j]
                         else df[c].notna().to_numpy())
    packed = np.packbits(present, axis=1)                  # (n, ceil(c/8)) uint8, 行ごとbig-endian
    bpr = packed.shape[1]
    rg = np.array([_gi.get(p, 255) for p in prim], dtype=np.uint8)          # 主グループ(帯)
    memb = np.array([sum(1 << _gi[m] for m in ms) for ms in memb_lists], dtype=np.uint8)  # メンバーシップbitmask
    _gcode = {"meta": 0, "main": 1, "phenotype": 2, "bv": 3, "other": 4}
    genre = [_gcode[_genre(c)] for c in cols]              # 列ごとのジャンル(表示列だけで境界を再計算)
    data = {
        "cols": cols, "groups": GROUP_ORDER, "n": int(n), "bpr": int(bpr),
        "boolcols": boolcols,                              # True=値(True/False)で色分け/絞込する列
        "genre": genre,                                    # 列ごとのジャンルコード(太い縦線用)
        "bits": base64.b64encode(packed.tobytes()).decode("ascii"),
        "rg": base64.b64encode(rg.tobytes()).decode("ascii"),
        "memb": base64.b64encode(memb.tobytes()).decode("ascii"),          # 複数グループ帰属
    }
    js = _JS.replace("__DATA__", json.dumps(data, ensure_ascii=False))

    _mcount = {g: sum(1 for ms in memb_lists if g in ms) for g in GROUP_ORDER}
    grpsum = "　".join(f"{html.escape(g)} {c:,}" for g in GROUP_ORDER if (c := _mcount[g]) > 0)

    body = f"""
<header>
  <h1>{html.escape(title)}</h1>
  <div class='meta'>{n:,} 行 × {len(cols)} 列　|　{grpsum}</div>
</header>
<div class='layout'>
  <aside id='panel'>
    <div id='count' class='count'></div>
    <div id='pergroup' class='pergroup'></div>
    <div class='sec'>表示</div>
    <label style='font-size:12px'>行の高さ（左=圧縮） <input id='rowh' type='range' style='width:100%;vertical-align:middle'></label>
    <div class='sec'>グループ</div>
    <div id='groups'></div>
    <div class='sec'>列（☑=表示 ／ ボタン=行フィルタ条件）</div>
    <div class='legend'>
      <span class='chip' style='background:#5cb85c'></span>値あり
      <span class='chip' style='background:#d9534f'></span>欠損
      ／ <b>⚑</b>=bool列(緑=True/赤=False)　／　左の☑で列の表示/非表示（条件とは独立）
    </div>
    <div id='collist' class='collist'></div>
    <button id='reset' class='reset'>条件をリセット</button>
  </aside>
  <div id='main'>
    <div class='legend'>ヒートマップ: 行＝該当サンプル(グループ順)／列＝フィールド
      <span class='chip' style='background:#5cb85c'></span>値あり
      <span class='chip' style='background:#d9534f'></span>欠損　（列名は縦スクロールしても上部に固定）</div>
    <div id='hdr'><canvas id='cvh'></canvas></div>
    <canvas id='cv'></canvas>
  </div>
</div>
<details>
  <summary>列カタログ（型・全体充足率）</summary>
  {_catalog_html(df, cols, n)}
</details>
<script>{js}</script>
"""
    doc = (f"<!doctype html><html lang='ja'><head><meta charset='utf-8'>"
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>{html.escape(title)}</title><style>{_CSS}</style></head>"
           f"<body>{body}</body></html>")
    out_html.write_text(doc, encoding="utf-8")
    return out_html


if __name__ == "__main__":
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
    else:                                       # 既定: processed/sample_* の最新
        sys.path.insert(0, "/home/s_mori/JBRT/JBRT_share/src")
        from jbrt import config
        cands = sorted(Path(config.PROCESSED_DIR).glob("sample_*/sample_table.parquet"))
        if not cands:
            sys.exit("sample_table.parquet が見つかりません（引数でパス指定も可）")
        src = cands[-1]
    df = pd.read_parquet(src)
    out = build_html_report(df, src.with_suffix(".html"))
    print(f"HTML出力: {out}  ({len(df):,}行 × {df.shape[1]}列)")
