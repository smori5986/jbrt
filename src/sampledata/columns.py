"""サンプル結合テーブルのカラム解説（単一ソース）。

`COLUMN_DOCS` は列名 → {abbr, desc} の**静的な説明だけ**を持つ。
型・非欠損数・充足率は実データによって変わるので**ここには持たず**、
書き出し時に DataFrame から毎回算出する（README に数を手書きすると乖離するため）。

参照元:
    ・xlsx の「カラム説明」シート (xlsx_report.build_xlsx)
    ・README.md の「カラム定義」節 (docs 生成)

列→ジャンルの判定は table_report._genre() を使う（HTMLレポートと分類を揃える）。
"""
from __future__ import annotations

import re

# ジャンルの表示順と配色（xlsx ヘッダの塗り分け / 説明シートの行色）
GENRE_ORDER = ["main", "phenotype", "bv", "meta", "other"]

# README の <summary> に出す見出し（<b>…</b> はジャンル名）
GENRE_SUMMARY = {
    "main": "<b>main</b>（個体の基本属性・血統・SNP）",
    "phenotype": "<b>phenotype</b>（枝肉格付・画像解析・脂肪酸）",
    "bv": "<b>breeding_value</b>（育種価。<code>bv_</code> 接頭辞）",
    "meta": "<b>meta</b>（由来メタ情報）",
    "other": "<b>other</b>（補助識別子・保管情報・未使用列）",
}

# ジャンル直下に置く注記（無ければ None）
GENRE_NOTE = {
    "bv": "> 育種価(EBV)は接頭辞 `bv_` ＋ 上記 phenotype と同じ Short を流用（略の由来も同じ）。",
}

# phenotype だけ小見出しで割る（判定関数, 見出し）
PHENOTYPE_SUBGROUPS = [
    (lambda c: bool(re.match(r"^\d{2}_", c)), "枝肉格付項目"),
    (lambda c: c.startswith("img_"), "画像解析"),
    (lambda c: c.startswith("fa_"), "脂肪酸組成"),
]

# ヘッダ塗り用（濃いめ・白文字）と説明シート用（淡色・黒文字）
GENRE_COLORS = {
    "main":      {"header": "4E79A7", "light": "DCE6F1"},
    "phenotype": {"header": "59A14F", "light": "DDEEDC"},
    "bv":        {"header": "B07AA1", "light": "EEE1EA"},
    "meta":      {"header": "808080", "light": "E8E8E8"},
    "other":     {"header": "BFBFBF", "light": "F2F2F2"},
}

# 列名 → {"abbr": 略の由来 (無ければ None), "desc": 内容}
COLUMN_DOCS: dict[str, dict[str, str | None]] = {
    # --- main -------------------------------------------------------------
    "cat_id":      {"abbr": None, "desc": "個体識別番号"},
    "breed_id":    {"abbr": None, "desc": "登録番号（血統登録番号）"},
    "name":        {"abbr": None, "desc": "名号（牛の名前）。同名重複は末尾 `_N` で一意化"},
    "snp_id":      {"abbr": None, "desc": "SNP解析コード＝CELファイル名（genotypingの識別子。SNPデータとの結合キー）"},
    "has_snp":     {"abbr": None, "desc": "snp_id が実SNPデータ(feather)に存在するか（True=genotypeあり）"},
    "dupli_snp":   {"abbr": None, "desc": "同一個体(cat_id)が複数のgenotypeを持つ（複数回測定された）"},
    "DNA_conc":    {"abbr": None, "desc": "DNA濃度 (ng/μL)"},
    "birth":       {"abbr": None, "desc": "出生年月日"},
    "death":       {"abbr": None, "desc": "と畜日／死亡日（NLBC異動履歴の と畜 or 死亡日）"},
    "age":         {"abbr": None, "desc": "出荷月齢（birth→death の月差）"},
    "sex":         {"abbr": None, "desc": "雌雄。`F`=メス / `M`=オス / `C`=去勢"},
    "raising":     {"abbr": None, "desc": "肥育繁殖区分。`fat`=肥育 / `breed`=繁殖"},
    "species":     {"abbr": None, "desc": "品種（褐毛和種 / ホルスタイン種 等。NLBC由来）"},
    "p1_cat_id":   {"abbr": None, "desc": "父の個体識別番号"},
    "p1_name":     {"abbr": None, "desc": "父の名号（種雄牛。漢字のみ）"},
    "p1_breed_id": {"abbr": None, "desc": "父の登録番号"},
    "m1_cat_id":   {"abbr": None, "desc": "母の個体識別番号"},
    "m1_name":     {"abbr": None, "desc": "母の名号。`_?` = 同名複数で特定不可"},
    "specimen":    {"abbr": None, "desc": "サンプル種別。`blood` / `muscle` / `hair`"},
    "farm":        {"abbr": None, "desc": "出生及び飼養農家名"},
    "owner":       {"abbr": None, "desc": "所有者名"},

    # --- phenotype: 枝肉格付項目 -------------------------------------------
    "01_Grade":  {"abbr": "Grade = Carcass Grade", "desc": "枝肉格付等級（A5等の総合等級。文字含む）"},
    "21_CW":     {"abbr": "CW = Carcass Weight", "desc": "枝肉重量 (kg)"},
    "03_REA":    {"abbr": "REA = Rib Eye Area", "desc": "ロース芯面積 (cm²)＝胸最長筋面積"},
    "04_RT":     {"abbr": "RT = Rib Thickness", "desc": "バラの厚さ (cm)"},
    "05_SFT":    {"abbr": "SFT = Subcutaneous Fat Thickness", "desc": "皮下脂肪の厚さ (cm)"},
    "06_YE":     {"abbr": "YE = Yield Estimate（歩留基準値）", "desc": "歩留基準値"},
    "07_BMS":    {"abbr": "BMS = Beef Marbling Standard", "desc": "脂肪交雑 BMS No."},
    "08_MG":     {"abbr": "MG = Marbling Grade", "desc": "脂肪交雑等級"},
    "09_BCS":    {"abbr": "BCS = Beef Color Standard", "desc": "肉色 BCS No."},
    "10_MLus":   {"abbr": "MLus = Meat Lustre", "desc": "肉の光沢"},
    "11_MQ1":    {"abbr": "MQ1 = Meat Quality grade 1", "desc": "肉質等級①"},
    "12_Firm":   {"abbr": "Firm = Firmness", "desc": "肉の締まり"},
    "13_Tex":    {"abbr": "Tex = Texture", "desc": "肉のきめ"},
    "14_MQ2":    {"abbr": "MQ2 = Meat Quality grade 2", "desc": "肉質等級②"},
    "15_BFS":    {"abbr": "BFS = Beef Fat Standard", "desc": "脂肪色 BFS No."},
    "16_FLQ":    {"abbr": "FLQ = Fat Lustre and Quality", "desc": "脂肪の光沢と質"},
    "17_MQ3":    {"abbr": "MQ3 = Meat Quality grade 3", "desc": "肉質等級③"},
    "18_Defect": {"abbr": "Defect = Defect / Blemish", "desc": "瑕疵"},
    "22_UP":     {"abbr": "UP = Unit Price", "desc": "取引単価 (円/kg)"},

    # --- phenotype: 画像解析 -----------------------------------------------
    "img_REAi": {"abbr": "REAi = Rib Eye Area (image-derived)", "desc": "画像解析ロース芯面積"},
    "img_Fat":  {"abbr": "Fat = Fat ratio", "desc": "画像解析 脂肪割合"},
    "img_Lean": {"abbr": "Lean = Lean meat ratio", "desc": "画像解析 赤身割合"},
    "img_FMI":  {"abbr": "FMI = Fine Marbling Index（コザシ）", "desc": "画像解析 コザシ指数"},
    "img_CMI":  {"abbr": "CMI = Coarse Marbling Index（アラザシ）", "desc": "画像解析 アラザシ指数"},

    # --- phenotype: 脂肪酸組成 ---------------------------------------------
    "fa_C18_1": {"abbr": "C18:1 = Oleic acid（オレイン酸）", "desc": "オレイン酸割合"},
    "fa_SFA":   {"abbr": "SFA = Saturated Fatty Acids", "desc": "飽和脂肪酸割合"},
    "fa_MUFA":  {"abbr": "MUFA = Monounsaturated Fatty Acids", "desc": "一価不飽和脂肪酸割合"},

    # --- breeding_value（bv_ 接頭辞。略は phenotype と同じ Short を流用）----
    "bv_CW":     {"abbr": "CW = Carcass Weight (EBV)", "desc": "枝肉重量 育種価"},
    "bv_REA":    {"abbr": "REA = Rib Eye Area (EBV)", "desc": "ロース芯面積 育種価"},
    "bv_RT":     {"abbr": "RT = Rib Thickness (EBV)", "desc": "バラ厚 育種価"},
    "bv_SFT":    {"abbr": "SFT = Subcutaneous Fat Thickness (EBV)", "desc": "皮下脂肪厚 育種価"},
    "bv_YE":     {"abbr": "YE = Yield Estimate (EBV)", "desc": "推定歩留 育種価"},
    "bv_BMS":    {"abbr": "BMS = Beef Marbling Standard (EBV)", "desc": "脂肪交雑 BMS 育種価"},
    "bv_C18_1":  {"abbr": "C18:1 = Oleic acid (EBV)", "desc": "オレイン酸 育種価"},
    "bv_SFA":    {"abbr": "SFA = Saturated Fatty Acids (EBV)", "desc": "飽和脂肪酸 育種価"},
    "bv_MUFA":   {"abbr": "MUFA = Monounsaturated Fatty Acids (EBV)", "desc": "一価不飽和脂肪酸 育種価"},
    "bv_AFC":    {"abbr": "AFC = Age at First Calving (EBV)", "desc": "初産月齢 育種価"},
    "bv_CI":     {"abbr": "CI = Calving Interval (EBV)", "desc": "分娩間隔 育種価"},

    # --- meta ---------------------------------------------------------------
    "source": {"abbr": None,
               "desc": "由来ファイル名（旧血液Excel / 骨格筋Excel / `NLBC` / 高知大母リスト）。空=種雄牛の名号だけ追加した行"},
    "sheet":  {"abbr": None, "desc": "由来シート名（施設シート / `Sheet1`(育種価マスタ) / `骨格筋N-M` 等）"},
    "group":  {"abbr": None,
               "desc": "由来グループ。`;`区切りの複数ラベル（1個体が複数帰属可）。"
                       "排他=血液/骨格筋/Sheet1育種価/NLBC母系、横断=高知大母/父(種雄牛)"},

    # --- other --------------------------------------------------------------
    "sample_name":     {"abbr": None, "desc": "通し番号（入庫サンプルの連番。サンプルリスト↔CEL の橋渡しに使う補助キー）"},
    "チューブID":        {"abbr": None, "desc": "保管チューブID"},
    "ラックID":          {"abbr": None, "desc": "保管ラックID"},
    "ポジション":         {"abbr": None, "desc": "ラック内ポジション"},
    "説明／備考":         {"abbr": None, "desc": "備考"},
    "サンプルタイプ":      {"abbr": None, "desc": "全空（未使用）"},
    "枝肉の写真":         {"abbr": None, "desc": "全空（未使用）"},
    "SNP解析結果":       {"abbr": None, "desc": "全空（未使用）"},
    "遺伝子型解析結果":    {"abbr": None, "desc": "全空（未使用）"},
    "SNP解析結果.1":     {"abbr": None, "desc": "全空（未使用・重複ヘッダ由来）"},
    "遺伝子型解析結果.1":  {"abbr": None, "desc": "全空（未使用・重複ヘッダ由来）"},
}

# 表示用の型名（pandas dtype → 短い表記）
_DTYPE_LABEL = {
    "object": "string", "string": "string", "boolean": "bool", "bool": "bool",
    "Int64": "Int64", "int64": "Int64", "float64": "float", "Float64": "float",
    "datetime64[ns]": "datetime", "category": "category",
}


def dtype_label(s) -> str:
    """pandas Series の dtype を README/xlsx 表記に寄せた短い型名にする。"""
    return _DTYPE_LABEL.get(str(s.dtype), str(s.dtype))


def plain(s: str) -> str:
    """markdown 用のバックティックを剥がす（xlsx セルにそのまま出すと邪魔なので）。"""
    return s.replace("`", "")


def describe_columns(df, plain_text: bool = False) -> list[dict]:
    """列ごとの {no, col, genre, dtype, n_notna, fill_rate, abbr, desc} を DataFrame の列順で返す。

    型・非欠損・充足率は df から実測する。COLUMN_DOCS に無い列は desc="（未記載）"。
    plain_text=True で desc/abbr のバックティックを剥がす（xlsx 用）。
    """
    from table_report import _genre                     # 分類は HTML レポートと共通

    conv = plain if plain_text else (lambda x: x)
    n = len(df)
    rows = []
    for i, c in enumerate(df.columns, 1):
        doc = COLUMN_DOCS.get(c)
        notna = int(df[c].notna().sum())
        rows.append({
            "no": i,
            "col": c,
            "genre": _genre(c),
            "dtype": dtype_label(df[c]),
            "n_notna": notna,
            "fill_rate": (notna / n) if n else 0.0,
            "abbr": conv((doc or {}).get("abbr") or ""),
            "desc": conv((doc or {}).get("desc") or "（未記載）"),
        })
    return rows


def undocumented(df) -> list[str]:
    """COLUMN_DOCS に説明が無い列名を返す（列が増えたのに解説が無いことの検知用）。"""
    return [c for c in df.columns if c not in COLUMN_DOCS]


# ==========================================================================
# README.md の「カラム定義」節を生成する
# ==========================================================================
_MD_BEGIN = "## カラム定義（ジャンル別）"
_MD_END = "---"                                  # 残タスク節の直前の水平線


def _render_entry(r: dict) -> list[str]:
    out = [f'{r["no"]}. **{r["col"]}**',
           f'    - 型: {r["dtype"]}',
           f'    - 非欠損: {r["n_notna"]}']
    if r["abbr"]:
        out.append(f'    - 略: {r["abbr"]}')
    out.append(f'    - 内容: {r["desc"]}')
    return out


def render_column_docs_md(df) -> str:
    """README の「カラム定義（ジャンル別）」節を、COLUMN_DOCS + df の実測から生成する。"""
    rows = describe_columns(df)
    L = [_MD_BEGIN, ""]

    for g in GENRE_ORDER:
        grp = [r for r in rows if r["genre"] == g]
        if not grp:
            continue
        L += ["<details>", f"<summary>{GENRE_SUMMARY[g]}</summary>", ""]
        if GENRE_NOTE.get(g):
            L += [GENRE_NOTE[g], ""]

        if g == "phenotype":                     # 小見出しで割る
            for pred, title in PHENOTYPE_SUBGROUPS:
                sub = [r for r in grp if pred(r["col"])]
                if not sub:
                    continue
                L += [f"### {title}"]
                for r in sub:
                    L += _render_entry(r)
                L += [""]
        else:
            for r in grp:
                L += _render_entry(r)
            L += [""]
        L += ["</details>", ""]

    return "\n".join(L).rstrip() + "\n\n"


def update_readme(df, path) -> None:
    """README.md の「カラム定義」節だけを差し替える（手書きの他節は温存）。

    先頭サマリの「N 行 × M 列」も実データに合わせて更新する。
    """
    from pathlib import Path

    p = Path(path)
    text = p.read_text(encoding="utf-8")

    i = text.index(_MD_BEGIN)
    j = text.index(f"\n{_MD_END}\n", i)           # 残タスク節の手前まで
    new = text[:i] + render_column_docs_md(df) + text[j + 1:]

    # 冒頭の行数×列数サマリを実測に同期
    new = re.sub(r"- \*\*[\d,]+ 行 × \d+ 列\*\*",
                 f"- **{len(df):,} 行 × {df.shape[1]} 列**", new, count=1)
    p.write_text(new, encoding="utf-8")


if __name__ == "__main__":                        # python columns.py [parquet]
    import sys

    import pandas as pd

    from jbrt import config

    src = (sys.argv[1] if len(sys.argv) > 1
           else sorted(config.PROCESSED_DIR.glob("sample_*/sample_table.parquet"))[-1])
    _df = pd.read_parquet(src)
    _readme = __file__.rsplit("/", 1)[0] + "/README.md"
    update_readme(_df, _readme)
    print(f"更新: {_readme}  ({src})")
    _u = undocumented(_df)
    print("解説が無い列:", _u if _u else "なし")
