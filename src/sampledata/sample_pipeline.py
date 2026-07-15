# ==============================================================================
# sample_pipeline.py  —  サンプル前処理パイプライン（本番用・関数化）
#
#   ・各処理を「1処理=1関数」に切り出し。ノートは公開関数を順に呼ぶだけ
#     （呼び出し順は notebooks/preprocess_sampledata.ipynb を参照）
#   ・公開関数は combined を受け取り combined を返す（truth/blood は明示引数）
#   ・定数は先頭の「定数」セクションに集約（COLUMN_ORDER 等はここで編集）
#   ・"_" 始まりは内部ヘルパー（非公開）
# ==============================================================================

# ==============================================================================
# import
# ==============================================================================
import json
import re
import sys
import unicodedata
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))                                  # nlbc_scraper / table_report
sys.path.insert(0, "/home/s_mori/JBRT/JBRT_share/src")          # jbrt.config

from jbrt import config                                          # noqa: E402
import table_report                                              # noqa: E402
import xlsx_report                                               # noqa: E402
from nlbc_scraper import search_pedigree                         # noqa: E402

# openpyxl の無害な警告を抑制（Excel独自プロパティ / データ検証拡張は読み込みに影響なし）
warnings.filterwarnings("ignore", message="Unknown type for", module="openpyxl")
warnings.filterwarnings("ignore", message="Data Validation extension", module="openpyxl")


# ==============================================================================
# 定数
# ==============================================================================
# ---- パス ----
SNP_DIR = config.RAW_DIR / "SNP"
BLOOD_PATH = config.RAW_DIR / "sample_data" / "20251029" / "☆旧血液サンフ_ル(2023まて_).xlsx"
MUSCLE_PATH = config.RAW_DIR / "sample_data" / "20260701" / "☆骨格筋サンフ_ル(2024_2026)1-1000.xlsx"
DAM_DIR = config.RAW_DIR / "sample_data" / "20260514_kochi_u_dams"
DAM_SNP_XLSX = DAM_DIR / "cattle_management_list (SNPデータ有り).xlsx"      # snp_id / 名号 / 血統名号
DAM_FND_XLSX = DAM_DIR / "cattle_management_list (始祖割合あり).xlsx"       # 父 / 母
NLBC_DIR = config.RAW_DIR / "nlbc_data"

KEY = "通し番号入庫サンプル"                                    # サンプル表の通し番号カラム名(生)

# ---- 接頭辞（通し番号の施設区別） ----
# ラックID → 接頭辞（5施設シートは通し番号が各1から振り直しなので接頭辞で区別）
RACK_PREFIX = {
    "A1_中央家畜保健衛生所": "A1-",
    "A2_中央・田野支所": "A2-",
    "A4_中央・嶺北支所": "A4-",
    "B1_西部家畜保健衛生所": "B1-",
    "B3_西部・梼原支所": "B3-",
}
# シート名 → 接頭辞（ラックIDでは区別できないシート用）。高知大学(仔牛)は通し番号(9057…)だけ → KC-
SHEET_PREFIX = {
    "高知大学（仔牛）": "KC-",
}

# 高知大学（仔牛）の22サンプル(AX020-05の一部)。通し番号だけで施設接頭辞が無いので KC- を付与。
KOCHI_CALF_IDS = {
    "AX020-05_E13.CEL", "AX020-05_E15.CEL", "AX020-05_E17.CEL", "AX020-05_E19.CEL",
    "AX020-05_E21.CEL", "AX020-05_E23.CEL", "AX020-05_G01.CEL", "AX020-05_G03.CEL",
    "AX020-05_G05.CEL", "AX020-05_G07.CEL", "AX020-05_G09.CEL", "AX020-05_G11.CEL",
    "AX020-05_G13.CEL", "AX020-05_G15.CEL", "AX020-05_G17.CEL", "AX020-05_G19.CEL",
    "AX020-05_G21.CEL", "AX020-05_G23.CEL", "AX020-05_I01.CEL", "AX020-05_I03.CEL",
    "AX020-05_I05.CEL", "AX020-05_I07.CEL",
}

# ---- 生カラム名 → 統一列名（血液/骨格筋/Sheet1 共通。父牛系など表記ゆれもここで吸収） ----
RENAME = {
    # main
    '個体識別番号': 'cat_id',
    '通し番号入庫サンプル': 'sample_name',
    'サンプル種別': 'specimen',
    'と畜日': 'death',
    '雌雄区別': 'sex',
    '肥育繁殖区別': 'raising',
    '出生年月日': 'birth',
    '出荷月齢': 'age',
    '出生及び飼養農家名': 'farm',
    'DNA濃度 (ng/μL)': 'DNA_conc',
    'SNP解析コード': 'snp_id',
    # phenotype
    '枝肉格付項目01等級': '01_Grade',
    '枝肉格付項目21総重量': '21_CW',
    '枝肉格付項目03歩留胸最長筋面積': '03_REA',
    '枝肉格付項目04歩留ばら厚さ': '04_RT',
    '枝肉格付項目05歩留皮下脂肪厚さ': '05_SFT',
    '枝肉格付項目06歩留基準値': '06_YE',
    '枝肉格付項目07肉質BMSNo': '07_BMS',
    '枝肉格付項目08肉質脂肪交雑等級': '08_MG',
    '枝肉格付項目09肉質BCSNo': '09_BCS',
    '枝肉格付項目10肉質光沢': '10_MLus',
    '枝肉格付項目11肉質等級1': '11_MQ1',
    '枝肉格付項目12肉質締まり': '12_Firm',
    '枝肉格付項目13肉質きめ': '13_Tex',
    '枝肉格付項目14肉質等級2': '14_MQ2',
    '枝肉格付項目15肉質BFSNo': '15_BFS',
    '枝肉格付項目16肉質光沢と質': '16_FLQ',
    '枝肉格付項目17肉質等級3': '17_MQ3',
    '枝肉格付項目18瑕疵': '18_Defect',
    '枝肉格付項目22取引単価': '22_UP',
    '画像解析結果ロース芯面積': 'img_REAi',
    '画像解析結果脂肪割合': 'img_Fat',
    '画像解析結果赤身割合': 'img_Lean',
    '画像解析結果コザシ指数': 'img_FMI',
    '画像解析結果アラザシ指数': 'img_CMI',
    '脂肪酸組成オレイン酸割合': 'fa_C18_1',
    '脂肪酸組成飽和脂肪酸割合': 'fa_SFA',
    '脂肪酸組成一価不飽和脂肪酸割合': 'fa_MUFA',
    # main
    '父牛(登録番号)': 'p1_breed_id',
    '父牛名号': 'p1_name',
    # breeding_value
    '枝肉重量': 'bv_CW',
    'ロース芯\n面積': 'bv_REA',
    'バラの厚さ': 'bv_RT',
    '皮下脂肪\n厚さ': 'bv_SFT',
    '推定歩留': 'bv_YE',
    'BMSNo.': 'bv_BMS',
    # main
    'DNA濃度': 'DNA_conc',
    '本牛名号': 'name',
    '父名号': 'p1_name',
    '父牛（登録番号）': 'p1_breed_id',
    '父牛（名号）': 'p1_name',
    '父牛': 'p1_name',
    '名号': 'name',
    '父番号': 'p1_breed_id',
    '所有者名': 'owner',
    # breeding_value
    'bv_枝重': 'bv_CW',
    'bv_ロース芯': 'bv_REA',
    'bv_バラ厚': 'bv_RT',
    'bv_皮下脂肪厚': 'bv_SFT',
    'bv_歩留': 'bv_YE',
    'bv_オレイン酸': 'bv_C18_1',
    'bv_初産月齢': 'bv_AFC',
    'bv_分娩間隔': 'bv_CI',
}

DTYPE = {
    # meta
    'source': 'string',
    'sheet': 'string',
    # other
    'チューブID': 'string',
    'ラックID': 'string',
    'ポジション': 'string',
    '説明／備考': 'string',
    'サンプルタイプ': 'string',
    # main
    'cat_id': 'string',
    'sample_name': 'string',
    'specimen': 'string',
    'death': 'datetime64[ns]',
    'sex': 'string',
    'raising': 'string',
    'birth': 'string',
    'age': 'Int64',
    'farm': 'string',
    # other
    '枝肉の写真': 'string',
    # main
    'DNA_conc': 'float',
    'snp_id': 'string',
    # other
    'SNP解析結果': 'string',
    '遺伝子型解析結果': 'string',
    # phenotype
    '01_Grade': 'string',
    '21_CW': 'float',
    '03_REA': 'float',
    '04_RT': 'float',
    '05_SFT': 'float',
    '06_YE': 'float',
    '07_BMS': 'Int64',
    '08_MG': 'Int64',
    '09_BCS': 'Int64',
    '10_MLus': 'Int64',
    '11_MQ1': 'Int64',
    '12_Firm': 'Int64',
    '13_Tex': 'Int64',
    '14_MQ2': 'Int64',
    '15_BFS': 'Int64',
    '16_FLQ': 'Int64',
    '17_MQ3': 'Int64',
    '18_Defect': 'Int64',
    '22_UP': 'float',
    'img_REAi': 'float',
    'img_Fat': 'float',
    'img_Lean': 'float',
    'img_FMI': 'float',
    'img_CMI': 'float',
    'fa_C18_1': 'float',
    'fa_SFA': 'float',
    'fa_MUFA': 'float',
    # main
    'breed_id': 'string',
    'p1_breed_id': 'string',
    'p1_name': 'string',
    'p1_cat_id': 'string',
    # breeding_value
    'bv_CW': 'float',
    'bv_REA': 'float',
    'bv_RT': 'float',
    'bv_SFT': 'float',
    'bv_YE': 'float',
    'bv_BMS': 'float',
    # main
    'name': 'string',
    'owner': 'string',
    # breeding_value
    'bv_C18_1': 'float',
    'bv_SFA': 'float',
    'bv_MUFA': 'float',
    'bv_AFC': 'float',
    'bv_CI': 'float',
}

COLUMN_ORDER = [
    # main
    'cat_id', 'breed_id', 'name',
    'snp_id', 'has_snp', 'dupli_snp', 'DNA_conc',
    'birth', 'death', 'age', 'sex', 'raising', 'species',
    'p1_cat_id', 'p1_name', 'p1_breed_id',
    'm1_cat_id', 'm1_name',
    'specimen',
    'farm', 'owner',
    # phenotype
    '01_Grade', '21_CW', '03_REA', '04_RT', '05_SFT', '06_YE', '07_BMS', '08_MG', '09_BCS',
    '10_MLus', '11_MQ1', '12_Firm', '13_Tex', '14_MQ2', '15_BFS', '16_FLQ', '17_MQ3',
    '18_Defect', '22_UP',
    'img_REAi', 'img_Fat', 'img_Lean', 'img_FMI', 'img_CMI',
    'fa_C18_1', 'fa_SFA', 'fa_MUFA',
    # breeding_value
    'bv_CW', 'bv_REA', 'bv_RT', 'bv_SFT', 'bv_YE', 'bv_BMS', 'bv_C18_1', 'bv_SFA', 'bv_MUFA',
    'bv_AFC', 'bv_CI',
    # meta
    'source', 'sheet', 'group',
    # other
    'sample_name', 'チューブID', 'ラックID', 'ポジション', '説明／備考', 'サンプルタイプ', '枝肉の写真',
    'SNP解析結果', '遺伝子型解析結果', 'SNP解析結果.1', '遺伝子型解析結果.1',
]

# 既知の誤記修正（同一cat_idで食い違う個体属性を、正しい値に上書き）
CORRECTIONS = {
    # cat_id: {列: 正しい値}
    "1240239281": {"death": pd.Timestamp("2025-11-18"), "age": 277},  # 血液のと畜日/月齢が誤記(骨格筋が正)
}

_ID_COLS = {"cat_id", "p1_breed_id"}      # float由来のID → 10桁ゼロ埋め文字列
_DATE_COLS = {"death", "birth"}           # 日付は datetime で保持(日付演算のため)
_Z2H = str.maketrans("０１２３４５６７８９", "0123456789")   # 全角数字→半角
_KANA = re.compile(r"[ぁ-ゟ゠-ヿー]")     # ひらがな・カタカナ(あれば雌、無ければ種雄牛)


# ==============================================================================
# 内部ヘルパー
# ==============================================================================
def _head(title):
    """ログのセクション見出し(区切り線)を出力。各パイプライン関数の冒頭で1回呼ぶ。"""
    w = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in title)
    print(f"\n──── {title} " + "─" * max(4, 40 - w))


def _sub(msg):
    """ログのセクション内 詳細行(インデント)を出力。"""
    print(f"   {msg}")


def _sub_table(df):
    """ログのセクション内に DataFrame を字下げして出力。"""
    print("\n".join("      " + ln for ln in df.to_string(index=False).splitlines()))


def _n(x):
    """3桁区切りの数値文字列。"""
    return f"{int(x):,}"


def _norm_name(x):
    """Sample Name(通し番号)を文字列化。整数値の float は .0 を落とす。"""
    if pd.isna(x):
        return pd.NA
    if isinstance(x, float) and x == int(x):
        return str(int(x))
    return str(x).strip()


def _clean_id(s, width=10):
    """float由来のID → Int64 → 0/欠損はNA → 10桁ゼロ埋め文字列。
    (Excelがint保存で先頭0を落とすため zfill で復元。個体識別番号/登録番号は10桁)。
    """
    x = pd.to_numeric(s, errors="coerce").astype("Int64")
    x = x.mask(x == 0)                       # 0 = ID無し → NA
    return x.astype("string").str.zfill(width)


def _norm_farm(s):
    """農家名/所有者名の正規化: スペース除去, 全角括弧→半角, 末尾ダッシュ除去, （記載なし）→NA。"""
    s = s.astype("string")
    s = s.str.replace(r"[\s　]", "", regex=True)
    s = s.str.translate(str.maketrans("（）", "()"))
    s = s.str.replace(r"[―ー]+$", "", regex=True)
    return s.mask(s.isin(["(記載なし)", ""]))


def _parse_wareki(v):
    """和暦(令和/平成/昭和)日付 or Excelシリアル値 → Timestamp。"""
    if pd.isna(v):
        return pd.NaT
    s = str(v).strip()
    if s.isdigit() and len(s) <= 6:                       # Excelシリアル
        return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(s))
    m = re.match(r"(令和|平成|昭和)(\d+)年(\d+)月(\d+)日", s)
    if m:
        base = {"令和": 2018, "平成": 1988, "昭和": 1925}[m.group(1)]
        return pd.Timestamp(base + int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return pd.to_datetime(s, errors="coerce")


def _pednorm(s):
    """血統名号の正規化: 末尾 _N/_? を除去, 全角数字→半角, 喜→貴。突合キー用。"""
    if pd.isna(s) or str(s).strip() in ("", "nan"):
        return None
    return re.sub(r"_(\d+|\?)$", "", str(s).strip()).translate(_Z2H).replace("喜", "貴")


def _norm_id10(x):
    """任意の値 → 数字のみ抽出 → 10桁ゼロ埋め。0/空はNA。NLBC突合キー用。"""
    s = "" if pd.isna(x) else re.sub(r"\D", "", str(x))
    return s.zfill(10) if s and int(s) != 0 else pd.NA


def _months(birth, death):
    """暦月差(日でfloor) = 出荷月齢。どちらか欠損なら NA。"""
    if pd.isna(birth) or pd.isna(death):
        return pd.NA
    m = (death.year - birth.year) * 12 + (death.month - birth.month) - (death.day < birth.day)
    return int(m)


def _is_kanji_only(s):
    """name が漢字のみ(ひらがな・カタカナを含まない)＝種雄牛。雌はかなを含む。"""
    if pd.isna(s):
        return False
    s = str(s).strip()
    return bool(s) and _KANA.search(s) is None


def _dedup_columns(d):
    """リネーム後に同名列ができたら非NULL優先で1本化。"""
    if not d.columns.duplicated().any():
        return d
    return pd.DataFrame({name: d.loc[:, d.columns == name].bfill(axis=1).iloc[:, 0]
                         for name in pd.unique(d.columns)})


def _find_header(path, sheet, key=KEY, max_scan=8):
    """シート先頭 max_scan 行から key(通し番号) を含む見出し行の位置を返す。無ければ None。"""
    raw = pd.read_excel(path, sheet_name=sheet, header=None, nrows=max_scan)
    for i in range(len(raw)):
        if (raw.iloc[i].astype(str) == key).any():
            return i
    return None


# ---- truth(正解表)ビルド用ヘルパー ----
def _parse_sample_list(path) -> pd.DataFrame:
    """AX??_Sample List.xlsx を [snp_id, sample_name, position, ax, plate] の縦持ち表にする。

    3様式に対応: "Well No."+単一プレート / "Well No."+複数プレート(AX020) / "CEL File"列。
    position はプレート上のウェル位置(A01等)。snp_id 末尾(_{well}.CEL)から一律に取る。
    """
    path = Path(path)
    ax = re.search(r"(AX\d{3})", path.name).group(1)
    raw = pd.read_excel(path, sheet_name=0, header=None)

    hdr_rows = raw.index[(raw == "Sample Name").any(axis=1)]        # 見出し行 = "Sample Name" を含む行
    if len(hdr_rows) == 0:
        raise ValueError(f"見出し行(Sample Name)が見つからない: {path.name}")
    r_h = hdr_rows[0]

    key_cols = [c for c in raw.columns                              # キー列 = "Well No." / "CEL File"
                if str(raw.iat[r_h, c]).strip() in ("Well No.", "CEL File")]
    multi = len(key_cols) > 1                                       # AX020は複数プレート

    records = []
    for plate_no, c in enumerate(key_cols, start=1):
        kind = str(raw.iat[r_h, c]).strip()                        # "Well No." or "CEL File"
        pair = raw.iloc[r_h + 1:, [c, c + 1]].copy()
        pair.columns = ["key", "sample_name"]
        pair = pair[pair["key"].notna()]                           # プレート境界の空セルを除去

        for _, row in pair.iterrows():
            key = str(row["key"]).strip()
            if key == "" or key.lower() == "nan":
                continue
            if kind == "CEL File":
                snp_id = key
            elif multi:
                snp_id = f"{ax}-{plate_no:02d}_{key}.CEL"
            else:
                snp_id = f"{ax}_{key}.CEL"
            position = snp_id.rsplit("_", 1)[-1].removesuffix(".CEL")   # 末尾のウェル位置
            records.append((snp_id, _norm_name(row["sample_name"]), position, ax, plate_no))

    return pd.DataFrame(records, columns=["snp_id", "sample_name", "position", "ax", "plate"])


def _load_all_sample_lists(snp_dir=SNP_DIR) -> pd.DataFrame:
    """SNP配下の全 AX??_Sample List.xlsx を読み、正解表(通し番号→snp_id)に統合する。"""
    paths = sorted(Path(snp_dir).rglob("AX*_Sample List.xlsx"))
    if not paths:
        raise FileNotFoundError(f"Sample List が見つかりません: {snp_dir}")
    return pd.concat([_parse_sample_list(p) for p in paths], ignore_index=True)


def _load_dna_concentration(snp_dir=SNP_DIR) -> pd.DataFrame:
    """各バッチの『…サンプルQC結果….xlsx』(濃度測定シート)から DNA濃度 [ax, sample_name, dna_ng_ul] を集める。

    濃度QCがあるのは新しい6バッチ(AX034/037/041/045/050/056)のみ。'Concentration'を含む行を探して特定。
    Wellは96連番でCEL(384奇数)と別なので使わず、Sample Name で紐づける。
    """
    recs = []
    for f in sorted(Path(snp_dir).rglob("*サンプルQC結果*.xlsx")):
        ax = re.search(r"AX\d{3}", f.name).group(0)
        sheet = pd.ExcelFile(f).sheet_names[0]
        scan = pd.read_excel(f, sheet_name=sheet, header=None, nrows=20)
        hrow = next(i for i in range(len(scan))
                    if scan.iloc[i].astype(str).str.contains("Concentration").any())
        d = pd.read_excel(f, sheet_name=sheet, header=hrow).rename(columns=lambda c: str(c).strip())
        conc = [c for c in d.columns if "Concentration" in c][0]
        t = pd.DataFrame({
            "ax": ax,
            "sample_name": d["Sample Name"].map(_norm_name),
            "dna_ng_ul": pd.to_numeric(d[conc], errors="coerce"),
        })
        recs.append(t[t["sample_name"].notna()])
    return pd.concat(recs, ignore_index=True)


# ---- NLBC統合用ヘルパー ----
def _load_nlbc():
    """NLBC個体情報(nlbc_main.csv ok行)＋死亡日(nlbc_log.csv と畜/死亡の最古日)を読み込む。

    返り値: (_nb, _nb_death)
      _nb       … k(10桁cat_id)をindexに nb_birth/nb_sex/nb_m1/kind を持つ個体表
      _nb_death … k → 死亡日(Timestamp) の Series
    """
    _nb = pd.read_csv(NLBC_DIR / "nlbc_main.csv", dtype=str)
    _nb = _nb[_nb["status"] == "ok"].copy()
    _nb["k"] = _nb["cat_id"].map(_norm_id10)
    _nb["nb_birth"] = pd.to_datetime(_nb["birth"], format="%Y.%m.%d", errors="coerce")
    _nb["nb_sex"] = _nb["sex"].map({"メス": "F", "オス": "M", "去勢（雄）": "C"})
    _nb["nb_m1"] = _nb["m1_cat_id"].map(_norm_id10)
    _nb = _nb.dropna(subset=["k"]).drop_duplicates("k").set_index("k")

    _log = pd.read_csv(NLBC_DIR / "nlbc_log.csv", dtype=str)      # death=異動履歴の と畜/死亡 の最古日のみ
    _log["k"] = _log["cat_id"].map(_norm_id10)
    _dth = _log[_log["異動内容"].isin(["と畜", "死亡"])].copy()
    _dth["d"] = pd.to_datetime(_dth["異動年月日"], format="%Y.%m.%d", errors="coerce")
    _dth = _dth.dropna(subset=["d"]).sort_values("d").drop_duplicates("k", keep="first")
    _nb_death = _dth.set_index("k")["d"]
    return _nb, _nb_death


def _apply_nlbc_fill(combined, col, newval, label):
    """空欄補完＋衝突はNLBC優先で上書き。衝突をprintし、変更maskを返す。"""
    old = combined[col]
    conflict = old.notna() & newval.notna() & (old != newval)
    if conflict.any():
        _t = pd.DataFrame({"cat_id": combined.loc[conflict, "cat_id"],
                           "name":   combined.loc[conflict, "name"],
                           "既存":   old[conflict].astype(str),
                           "NLBC":   newval[conflict].astype(str)})
        _sub(f"{label}: 衝突 {_n(conflict.sum())}件 → NLBC優先で上書き")
        _sub_table(_t)
    fill = old.isna() & newval.notna()
    changed = conflict | fill
    combined.loc[changed, col] = newval[changed]
    _sub(f"{label}: 補完 {_n(fill.sum())} + 上書き {_n(conflict.sum())} = 計 {_n(changed.sum())}行変更")
    return changed


def _load_sire_registry():
    """骨格筋Excelの『種雄牛名号と登録番号』を読み、breed_id(10桁)を付けて返す。"""
    reg = pd.read_excel(MUSCLE_PATH, sheet_name="種雄牛名号と登録番号").dropna(subset=["名号", "登録番号"])
    reg["breed_id"] = _clean_id(reg["登録番号"])                  # p1_breed_id と同じ10桁文字列に揃える
    return reg


# ==============================================================================
# 公開パイプライン関数
# ==============================================================================
def build_truth_table() -> pd.DataFrame:
    """snp_id紐づけの正解表(通し番号「sample_name」 ⇔ snp_id)を作成。

    ・高知大学(仔牛)に独自prefix(KC-)を付与
    ・DNA濃度をQC結果から結合
    ・使用データ: SNP配下の AX??_Sample List.xlsx, *サンプルQC結果*.xlsx
    """
    truth = _load_all_sample_lists()
    _calf = truth["snp_id"].isin(KOCHI_CALF_IDS)                  # 高知大学(仔牛)22件に KC- を付与
    truth.loc[_calf, "sample_name"] = "KC-" + truth.loc[_calf, "sample_name"].astype(str)

    # DNA濃度を (ax, sample_name) で結合（sample_name単独だとAX003の 129/8796 が誤マッチ）
    dna = _load_dna_concentration()
    truth = truth.merge(dna, on=["ax", "sample_name"], how="left")

    n_dna = truth["dna_ng_ul"].notna().sum()
    _head("正解表ビルド")
    _sub(f"{_n(truth.shape[0])}行 / バッチ {truth['ax'].nunique()}種")
    _sub(f"高知大学仔牛 KC-付与 {_n(_calf.sum())}件 / DNA濃度付与 {_n(n_dna)}件")
    return truth


def load_blood() -> pd.DataFrame:
    """旧血液Excelを全列読み、通し番号を接頭辞つき(A1-1等)に補正して縦結合した blood df を返す。

    ・5施設シートはラック接頭辞、高知大学(仔牛)は KC- を通し番号に付与。
    ・使用データ: ☆旧血液サンフ_ル(2023まて_).xlsx
    """
    frames = []
    for sheet in pd.ExcelFile(BLOOD_PATH).sheet_names:
        d = pd.read_excel(BLOOD_PATH, sheet_name=sheet, header=3)
        if "通し番号入庫サンプル" not in d.columns:
            continue
        d = d.loc[:, ~d.columns.astype(str).str.startswith("Unnamed")]
        d = d[d["通し番号入庫サンプル"].notna()].copy()

        name = d["通し番号入庫サンプル"].apply(_norm_name).astype("string")
        rack = (d["ラックID"].astype("string") if "ラックID" in d.columns
                else pd.Series(pd.NA, index=d.index, dtype="string"))
        prefix = SHEET_PREFIX.get(sheet)
        if prefix is None:
            prefix = rack.map(RACK_PREFIX).fillna("")             # シート優先 → ラック
        d["通し番号入庫サンプル"] = (prefix + name).astype("string")   # 通し番号列そのものを補正
        d.insert(0, "source", BLOOD_PATH.name)
        d.insert(1, "sheet", sheet)
        frames.append(d)
    with warnings.catch_warnings():                              # 全NA列concatのFutureWarning抑制
        warnings.simplefilter("ignore", FutureWarning)
        blood = pd.concat(frames, ignore_index=True)

    n_rack = blood["ラックID"].isin(RACK_PREFIX).sum()
    n_sheet = blood["sheet"].isin(SHEET_PREFIX).sum()
    _head("血液サンプル読込")
    _sub(f"{_n(len(blood))}行 × {blood.shape[1]}列 / {blood['sheet'].nunique()}シート")
    _sub(f"ラック接頭辞 {_n(n_rack)}件 + シート接頭辞KC- {_n(n_sheet)}件")
    return blood


def _load_muscle_sheets():
    """骨格筋Excel: 通し番号を持つシートをロード
    
    ・使用データ: ☆旧骨格筋サンフ_ル(2023まて_).xlsx
    """
    frames = []
    for sheet in pd.ExcelFile(MUSCLE_PATH).sheet_names:
        h = _find_header(MUSCLE_PATH, sheet)
        if h is None:                                            # 通し番号なし = 参照シート
            continue
        d = pd.read_excel(MUSCLE_PATH, sheet_name=sheet, header=h)
        d = d.loc[:, ~d.columns.astype(str).str.startswith("Unnamed")]
        d = d[d[KEY].notna()].copy()
        d[KEY] = d[KEY].map(_norm_name).astype("string")
        d.insert(0, "source", MUSCLE_PATH.name)
        d.insert(1, "sheet", sheet)
        frames.append(d)
    return frames


def _load_sheet1():
    """血液Excelの Sheet1(育種価マスタ)をロード

    ・使用データ: ☆旧血液サンフ_ル(2023まて_).xlsx/Sheet1
    """
    d = pd.read_excel(BLOOD_PATH, sheet_name="Sheet1", header=0)
    d = d.loc[:, ~d.columns.astype(str).str.startswith("Unnamed")]
    d = d[d["個体識別番号"].notna()].copy()
    d.insert(0, "source", BLOOD_PATH.name)
    d.insert(1, "sheet", "Sheet1")
    return d


def combine_sources(blood) -> pd.DataFrame:
    """血液＋骨格筋＋Sheet1 を縦結合 → 一括リネーム → 同名列を1本化して combined df を返す。"""
    frames = [blood] + _load_muscle_sheets() + [_load_sheet1()]
    with warnings.catch_warnings():                             # 全NA列concatのFutureWarning抑制
        warnings.simplefilter("ignore", FutureWarning)
        combined = pd.concat(frames, ignore_index=True)
    combined = _dedup_columns(combined.rename(columns=RENAME))
    _n_s1 = int((combined["sheet"] == "Sheet1").sum())
    _head("縦結合＋リネーム")
    _sub(f"{_n(combined.shape[0])}行 × {combined.shape[1]}列 "
         f"(サンプル {_n(len(combined) - _n_s1)} + Sheet1 {_n(_n_s1)})")
    return combined


def clean_values(combined) -> pd.DataFrame:
    """combined df の値をクリーニング。カラムの英語化
    
    ・specimen/raising変換,
    ・農家名正規化
    ・img文字→NaN
    ・bv -999.999→NaN
    """
    if "specimen" in combined:
        combined["specimen"] = combined["specimen"].map(
            {"血液": "blood", "筋肉組織": "muscle", "毛": "hair"}).astype("string")
    if "raising" in combined:
        combined["raising"] = combined["raising"].map({"肥育": "fat", "繁殖": "breed"}).astype("string")
    for c in ("farm", "owner"):
        if c in combined:
            combined[c] = _norm_farm(combined[c])
    if "img_REAi" in combined:
        combined["img_REAi"] = pd.to_numeric(combined["img_REAi"], errors="coerce")   # A/B/C等の文字→NaN
    for c in [c for c in combined.columns if c.startswith("bv_")]:
        combined[c] = pd.to_numeric(combined[c], errors="coerce").replace(-999.999, np.nan)  # 育種価の欠損記号
    _head("値クリーニング")
    _sub("specimen/raising英語化・農家名正規化・img文字→NaN・bv欠損記号→NaN")
    return combined


def cast_types(combined) -> pd.DataFrame:
    """combined df の型をキャスト
    
    ・ID→10桁文字列 / 日付→datetime / Int64 / float / string
    """
    for col, dt in DTYPE.items():
        if col not in combined.columns:
            continue
        if col in _ID_COLS:
            combined[col] = _clean_id(combined[col])
        elif col in _DATE_COLS:
            combined[col] = pd.to_datetime(combined[col], errors="coerce")
        elif dt == "Int64":
            combined[col] = pd.to_numeric(combined[col], errors="coerce").round().astype("Int64")
        elif dt == "float":
            combined[col] = pd.to_numeric(combined[col], errors="coerce")
        elif dt == "string":
            combined[col] = combined[col].astype("string")
        elif dt == "datetime64[ns]":
            combined[col] = pd.to_datetime(combined[col], errors="coerce")
    _head("型キャスト")
    _sub("ID→10桁文字列 / 日付→datetime / Int64 / float / string")
    return combined


def apply_corrections(combined) -> pd.DataFrame:
    """特定のcat_id個体の既知の誤記を、正しい値で上書き"""
    for _cid, _fix in CORRECTIONS.items():
        _m = combined["cat_id"] == _cid
        for _col, _val in _fix.items():
            combined.loc[_m, _col] = _val
    _head("既知誤記の補正")
    _sub(f"正しい値で上書き修正: {len(CORRECTIONS)}個体")
    return combined


def reorder_columns(combined) -> pd.DataFrame:
    """COLUMN_ORDER の順に並び替え"""
    _ordered = [c for c in COLUMN_ORDER if c in combined.columns]
    _rest = [c for c in combined.columns if c not in COLUMN_ORDER]
    combined = combined[_ordered + _rest]
    _head("列並び替え")
    _sub(f"{_n(combined.shape[0])}行 × {combined.shape[1]}列"
         + (f" / COLUMN_ORDER外(末尾): {_rest}" if _rest else ""))
    return combined


def uniquify_sheet1_names(combined) -> pd.DataFrame:
    """Sheet1(育種価マスタ)の名号(name)重複を末尾 _1/_2… で一意化"""
    _s1 = (combined["sheet"] == "Sheet1") & combined["name"].notna()
    _nm = combined.loc[_s1, "name"]
    _size = _nm.groupby(_nm).transform("size")                  # 同名が何個あるか
    _cum = _nm.groupby(_nm).cumcount().add(1).astype("string")  # 1,2,3…(出現順)
    combined.loc[_s1, "name"] = _nm.where(_size == 1, _nm.str.cat(_cum, sep="_"))
    _head("Sheet1名号の一意化")
    _sub(f"重複 {_n((_size > 1).sum())}行 に _N を付与")
    return combined


def merge_sheet1(combined) -> pd.DataFrame:
    """Sheet1(育種価マスタ)を cat_id でサンプル行に肉付けマージ

    ・Sheet1行の cat_id が非Sheet1行にあれば bv_/name/owner/p1_ を空欄に補完。
    ・両方に値があって食い違えば衝突エラー
    """
    _s1_mask = combined["sheet"] == "Sheet1"
    _s1 = combined[_s1_mask]
    _oth = combined[~_s1_mask].copy()

    # Sheet1が供給する列(サンプル行へ肉付けする対象)
    merge_cols = ["name", "p1_name", "p1_breed_id", "owner"] + [c for c in combined.columns if c.startswith("bv_")]

    _s1_keyed = _s1[_s1["cat_id"].notna()].drop_duplicates("cat_id").set_index("cat_id")
    if _s1_keyed.index.duplicated().any():
        raise ValueError("Sheet1の cat_id が重複しています（マージのキーに使えません）")

    _s1_vals = {c: _oth["cat_id"].map(_s1_keyed[c]) for c in merge_cols}

    # --- 衝突チェック: 両方に値があって食い違う列があればエラー ---
    for c in merge_cols:
        a, b = _oth[c], _s1_vals[c]
        both = a.notna() & b.notna()
        if not both.any():
            continue
        aa, bb = a[both], b[both]
        if pd.api.types.is_numeric_dtype(a):
            mism = ~np.isclose(aa.astype(float).values, bb.astype(float).values)
        else:
            mism = aa.astype("string").values != bb.astype("string").values
        if mism.any():
            _bad = pd.DataFrame({"cat_id": _oth.loc[both, "cat_id"].values[mism],
                                 "sample": aa.values[mism], "sheet1": bb.values[mism]})
            raise ValueError(f"マージ衝突: 列 '{c}' で {int(mism.sum())} 件 食い違い\n{_bad.head(10)}")

    # --- サンプル行が null の箇所に Sheet1 値を埋める ---
    for c in merge_cols:
        _oth[c] = _oth[c].fillna(_s1_vals[c])

    # --- マージに使われた Sheet1 行を除去、残りは保持 ---
    _used = set(_oth["cat_id"].dropna()) & set(_s1_keyed.index)
    _s1_remain = _s1[~_s1["cat_id"].isin(_used)]
    with warnings.catch_warnings():                             # 全NA列concatのFutureWarning抑制
        warnings.simplefilter("ignore", FutureWarning)
        combined = pd.concat([_oth, _s1_remain], ignore_index=True)[combined.columns]

    _head("Sheet1マージ")
    _sub(f"サンプル {_n(len(_oth))}行 + Sheet1残 {_n(len(_s1_remain))}行 = {_n(len(combined))}行")
    _sub(f"重複Sheet1行を {_n(len(_used))}件マージ削除 / 衝突 0")

    # 同一cat_idで name が片方だけ入っている行に既知の name を補完（例: 桜山 の畜試→骨格筋）
    _known_name = combined.dropna(subset=["cat_id", "name"]).drop_duplicates("cat_id").set_index("cat_id")["name"]
    _nfill = combined["name"].isna() & combined["cat_id"].notna()
    combined.loc[_nfill, "name"] = combined.loc[_nfill, "cat_id"].map(_known_name)
    _sub(f"同一cat_id内 name補完: {_n(combined.loc[_nfill, 'name'].notna().sum())}件")
    return combined


def merge_kochi_dam_snp(combined) -> pd.DataFrame:
    """高知大 母牛リストを cat_id で突合"""
    _dam = pd.read_excel(DAM_SNP_XLSX, sheet_name="牛管理リスト", header=0)
    _dam["cat_id"] = _clean_id(_dam["認証番号"])                # 10桁ゼロ埋め(既存cat_idと同形式)
    _dam["snp"] = _dam["SNP Sample Filename"].astype("string")
    _dam = _dam.dropna(subset=["cat_id"]).drop_duplicates("cat_id")

    # (1) 既存行に snp_id を補完（空の所だけ／食い違いはprint） ---
    _v = combined["cat_id"].map(_dam.set_index("cat_id")["snp"])
    _conf = combined["snp_id"].notna() & _v.notna() & (combined["snp_id"] != _v)
    _head("高知大母マージ(snp_id/新規行)")
    if _conf.any():
        _sub("dam提供と既存snp_idが食い違い（既存維持）:")
        _sub_table(combined.loc[_conf, ["cat_id", "name", "snp_id"]].assign(dam=_v[_conf]))
    _fill = combined["snp_id"].isna() & _v.notna()
    combined.loc[_fill, "snp_id"] = _v[_fill]
    _sub(f"snp_id補完 {_n(_fill.sum())}件 / 食い違い {_n(_conf.sum())}件")

    # (2) combinedに無い母牛を行として追加（name/birth/snp_id） ---
    _new = _dam[~_dam["cat_id"].isin(set(combined["cat_id"].dropna()))]
    _rows = pd.DataFrame({
        "source": DAM_SNP_XLSX.name,
        "cat_id": _new["cat_id"],
        "name":   _new["名号"].astype("string"),
        "birth":  _new["生年月日"].map(_parse_wareki),
        "snp_id": _new["snp"],
    })
    combined = pd.concat([combined, _rows], ignore_index=True)
    _sub(f"高知大 母牛を新規追加 {_n(len(_rows))}行 → 全体 {_n(len(combined))}行")
    return combined


def fill_kochi_dam_parents(combined) -> pd.DataFrame:
    """高知大 母牛リストの 父→p1_name / 母→m1_name を補完"""
    _fo = pd.read_excel(DAM_FND_XLSX, sheet_name="牛管理リスト (2)", header=1)
    _fo["cat_id"] = _clean_id(_fo["認証番号"])
    _fo = _fo.dropna(subset=["cat_id"]).drop_duplicates("cat_id")
    _vp = combined["cat_id"].map(_fo.set_index("cat_id")["父"].astype("string"))
    _vm = combined["cat_id"].map(_fo.set_index("cat_id")["母"].astype("string"))
    _fp = combined["p1_name"].isna() & _vp.notna()
    combined.loc[_fp, "p1_name"] = _vp[_fp]
    if "m1_name" not in combined.columns:                       # m1_nameは通常[結合9]で作るが、先に用意
        combined["m1_name"] = pd.Series(pd.NA, index=combined.index, dtype="string")
    _fm = combined["m1_name"].isna() & _vm.notna()
    combined.loc[_fm, "m1_name"] = _vm[_fm]
    _head("高知大母マージ(父母名)")
    _sub(f"父→p1_name補完 {_n(_fp.sum())} / 母→m1_name付与 {_n(_fm.sum())}")
    return combined


def fix_snp_id(combined, truth) -> pd.DataFrame:
    """snp_id を正解表(truth)で補正・補完(キー: sample_name)。

    ・記入済みが正解候補にあればそのまま。
    ・食い違い→正解で上書き / 空→補完。
    ・候補複数かつ記入も不一致 → 曖昧として触らない(記録のみ)。
    """
    # sample_name → 正しいsnp_idの集合（重複sample_name=129/8796 対策で集合にする）
    _truth_map = (truth.dropna(subset=["sample_name"])
                  .groupby("sample_name")["snp_id"].apply(lambda s: sorted(set(s))))

    _targets = combined.index[(combined["sheet"] != "Sheet1") & combined["sample_name"].notna()]
    _log = []
    for i in _targets:
        sn = combined.at[i, "sample_name"]
        cand = _truth_map.get(sn)
        if cand is None:                          # 正解表に無い → 触らない
            continue
        old = combined.at[i, "snp_id"]
        if pd.notna(old) and old in cand:         # 記入済みが正解 → そのまま
            continue
        if len(cand) == 1:                        # 補正(上書き) or 補完(空埋め)
            combined.at[i, "snp_id"] = cand[0]
            _log.append((combined.at[i, "sheet"], sn, combined.at[i, "cat_id"], old, cand[0],
                         "補完" if pd.isna(old) else "補正"))
        else:                                     # 候補複数かつ記入も不一致 → 曖昧(未修正)
            _log.append((combined.at[i, "sheet"], sn, combined.at[i, "cat_id"], old, "/".join(cand), "曖昧(未修正)"))

    _log_df = pd.DataFrame(_log, columns=["sheet", "sample_name", "cat_id", "記入済みsnp_id", "正解snp_id", "種別"])
    _n_fix = int((_log_df["種別"] == "補正").sum())
    _n_fill = int((_log_df["種別"] == "補完").sum())
    _n_amb = int((_log_df["種別"] == "曖昧(未修正)").sum())
    _head("snp_id補正")
    _sub(f"上書き(補正) {_n(_n_fix)}件 / 補完 {_n(_n_fill)}件 / 曖昧(未修正) {_n(_n_amb)}件")
    _sub(f"補正後: 非欠損 {_n(combined['snp_id'].notna().sum())}件 / "
         f"重複 {_n(combined['snp_id'].dropna().duplicated().sum())}件")
    return combined


def add_breed_id(combined) -> pd.DataFrame:
    """種雄牛sheet(名号→登録番号)から既存行に breed_id を付与"""
    _reg = _load_sire_registry()
    _name2breed = dict(zip(_reg["名号"].astype("string"), _reg["breed_id"]))
    if "breed_id" not in combined.columns:                     # 個体の登録番号。p1_breed_id の手前に作る
        combined.insert(combined.columns.get_loc("p1_breed_id"), "breed_id",
                        pd.array([pd.NA] * len(combined), dtype="string"))
    combined["breed_id"] = combined["breed_id"].fillna(combined["name"].map(_name2breed))
    _head("breed_id付与")
    _sub(f"名号一致で付与: {_n(combined['name'].map(_name2breed).notna().sum())}件")
    return combined


def resolve_p1_cat_id(combined) -> pd.DataFrame:
    """p1_cat_id を解決: 
    
    ・① p1_breed_id→breed_id一致行の cat_id
    ・② 空だけ 父名号(p1_name)一致で補完
    """
    if "p1_cat_id" not in combined.columns:                    # 父の個体識別番号。p1_name の直後に作る
        combined.insert(combined.columns.get_loc("p1_name") + 1, "p1_cat_id",
                        pd.array([pd.NA] * len(combined), dtype="string"))
    _breed2cat = (combined.dropna(subset=["breed_id", "cat_id"])
                  .drop_duplicates("breed_id").set_index("breed_id")["cat_id"])
    combined["p1_cat_id"] = combined["p1_breed_id"].map(_breed2cat)              # ① breed_id法
    _n_bid = int(combined["p1_cat_id"].notna().sum())
    # 同一個体が複数行に出るだけのケースを先に畳む。行単位で keep=False すると
    # 血液+骨格筋で2回測った種雄牛などが「同名複数」と誤判定されて捨てられる。
    _uniq = combined.dropna(subset=["name", "cat_id"]).drop_duplicates(["name", "cat_id"])
    _name2cat = _uniq.drop_duplicates("name", keep=False).set_index("name")["cat_id"]  # 真に一意な名号のみ
    _n_amb = int(_uniq["name"].nunique() - len(_name2cat))       # 同名で複数cat_id → 曖昧として除外
    combined["p1_cat_id"] = combined["p1_cat_id"].fillna(combined["p1_name"].map(_name2cat))  # ② name法
    _head("p1_cat_id解決")
    _sub(f"解決 {_n(combined['p1_cat_id'].notna().sum())}件"
         f"（breed_id法 {_n(_n_bid)} + name法 {_n(int(combined['p1_cat_id'].notna().sum()) - _n_bid)}）")
    _sub(f"曖昧(同名で複数cat_id)により name法から除外した名号: {_n(_n_amb)}件")
    return combined


def add_missing_individuals(combined) -> pd.DataFrame:
    """名前基準で未登録の個体を新規行として追加。"""
    _reg = _load_sire_registry()
    _cand = pd.concat([
        _reg.rename(columns={"名号": "name"})[["name", "breed_id"]],            # レジストリ種雄牛
        (combined.dropna(subset=["p1_name"]).drop_duplicates("p1_name")[["p1_name", "p1_breed_id"]]
         .rename(columns={"p1_name": "name", "p1_breed_id": "breed_id"})),      # 参照された父
    ], ignore_index=True).dropna(subset=["name"]).drop_duplicates("name")
    _new = _cand[~_cand["name"].isin(set(combined["name"].dropna()))][["name", "breed_id"]].astype("string")
    combined = pd.concat([combined, _new.reset_index(drop=True)], ignore_index=True)
    _head("未登録個体の追加")
    _sub(f"新規行追加 {_n(len(_new))}件 → {_n(len(combined))}行 × {combined.shape[1]}列")
    return combined


def backfill_pedigree_names(combined) -> pd.DataFrame:
    """高知大 母牛リストの血統名号を「子→父/母」エッジで df に反映(空欄のみ・列は増やさない)。

    ・種雄牛→父方祖父(p1)/父方祖母(m1)、各祖父母→曽祖父(p1)。
    ・名前を正規化(全半角/喜貴/_N)して突合、一意な行だけ補完。
    """
    _ped = pd.read_excel(DAM_SNP_XLSX, sheet_name="牛管理リスト", header=0)
    _cf, _cm = {}, {}                                          # 子(正規化名)→父 / →母
    for _, _r in _ped.iterrows():
        for _c, _f in [("種雄牛", "父方祖父"), ("父方祖父", "父方祖父曽祖父"), ("父方祖母", "父方祖母曽祖父"),
                       ("母方祖父", "母方祖父曽祖父"), ("母方祖母", "母方祖母曽祖父")]:
            _ck = _pednorm(_r[_c])
            if _ck and _pednorm(_r[_f]):
                _cf.setdefault(_ck, str(_r[_f]).strip())
        _ck = _pednorm(_r["種雄牛"])
        if _ck and _pednorm(_r["父方祖母"]):
            _cm.setdefault(_ck, str(_r["父方祖母"]).strip())

    _nb = combined["name"].map(_pednorm)
    _cnt = _nb.value_counts()
    _unique = set(_cnt[_cnt == 1].index)                       # 一意名のみ(曖昧はスキップ)
    if "m1_name" not in combined.columns:
        combined["m1_name"] = pd.Series(pd.NA, index=combined.index, dtype="string")

    _np1 = _nm1 = 0
    for _ck, _fv in _cf.items():
        if _ck in _unique:
            _m = (_nb == _ck) & combined["p1_name"].isna()
            if _m.any():
                combined.loc[_m, "p1_name"] = _fv
                _np1 += int(_m.sum())
    for _ck, _mv in _cm.items():
        if _ck in _unique:
            _m = (_nb == _ck) & combined["m1_name"].isna()
            if _m.any():
                combined.loc[_m, "m1_name"] = _mv
                _nm1 += int(_m.sum())
    _head("血統名号のbackfill")
    _sub(f"父方＋母方: p1_name {_n(_np1)}件 / m1_name {_n(_nm1)}件 補完")
    return combined


def scrape_nlbc(combined, wait: float = 2.0, batch_save: int = 30):
    """NLBCで母系・個体情報を全件取得（cat_id起点 → 母を尽きるまで再帰)。

    ・結果は NLBC_DIR/nlbc_main.csv・nlbc_log.csv に追記
    ・⚠ フル実行は母系込みで数千〜1万個体規模＝数時間
    """
    _seed = combined["cat_id"].dropna().unique()
    _head("NLBCスクレイプ")
    _sub(f"起点 cat_id {_n(len(_seed))}個体 → 検索開始 [wait={wait} batch_save={batch_save}]")
    df_main, df_log = search_pedigree(_seed, out_dir=NLBC_DIR, wait=wait, batch_save=batch_save)
    _sub(f"取得: 個体 {_n(len(df_main))}件 / 異動 {_n(len(df_log))}件 / "
         f"母記載 {_n(df_main['m1_cat_id'].notna().sum())}件")
    return df_main, df_log


def apply_nlbc_attributes(combined) -> pd.DataFrame:
    """NLBC個体情報を cat_id で突合し birth/death/sex を補完
    
    ・衝突はNLBC優先で上書き
    ・m1_cat_id/species を追加。
    ・sex: メス=F / オス=M / 去勢（雄）=C。表M→NLBC去勢C は精緻化、F絡みの食い違いは矛盾表示。
    ・death: 異動履歴の と畜/死亡 の最古日のみ使用。
    """
    _nb, _nb_death = _load_nlbc()

    combined["k"] = combined["cat_id"].map(_norm_id10)
    _v_birth = combined["k"].map(_nb["nb_birth"])
    _v_sex = combined["k"].map(_nb["nb_sex"])
    _v_death = combined["k"].map(_nb_death)

    _head("NLBC属性の統合")
    # --- birth / death ---
    _ch_birth = _apply_nlbc_fill(combined, "birth", _v_birth, "birth")
    _ch_death = _apply_nlbc_fill(combined, "death", _v_death, "death")

    # --- sex（M→C は精緻化として区別、F絡みの食い違いのみ矛盾表示。いずれもNLBC優先） ---
    _old = combined["sex"]
    _both = _old.notna() & _v_sex.notna()
    _refine = _both & (_old == "M") & (_v_sex == "C")           # 表はM(去勢もMにしていた)→NLBC去勢C
    _contra = _both & (_old != _v_sex) & ~_refine               # F vs M/C 等の本質的食い違い
    if _contra.any():
        _t = pd.DataFrame({"cat_id": combined.loc[_contra, "cat_id"],
                           "farm":   combined.loc[_contra, "farm"],
                           "既存":   _old[_contra].astype(str),
                           "NLBC":   _v_sex[_contra].astype(str)})
        _sub(f"sex: ★矛盾(F絡み等) {_n(_contra.sum())}件 → NLBC優先で上書き")
        _sub_table(_t)
    _fill = _old.isna() & _v_sex.notna()
    _ch_sex = _fill | _refine | _contra
    combined.loc[_ch_sex, "sex"] = _v_sex[_ch_sex]
    _sub(f"sex: 補完 {_n(_fill.sum())} + M→C精緻化 {_n(_refine.sum())} + 矛盾上書き {_n(_contra.sum())} "
         f"= 計 {_n(_ch_sex.sum())}行変更")

    # --- 新列: m1_cat_id(母) / species(種別) ---
    combined["m1_cat_id"] = combined["k"].map(_nb["nb_m1"])
    combined["species"] = combined["k"].map(_nb["kind"]).astype("string")
    _sub(f"m1_cat_id付与 {_n(combined['m1_cat_id'].notna().sum())}行 / "
         f"species付与 {_n(combined['species'].notna().sum())}行")

    combined["_dchg"] = (_ch_birth | _ch_death)                # recalc_age へ渡す一時列
    return combined


def recalc_age(combined) -> pd.DataFrame:
    """birth/death が変わり かつ 両日付が揃う行だけ age(暦月差) を再計算"""
    _recalc = combined["_dchg"] & combined["birth"].notna() & combined["death"].notna()
    _old_age = combined["age"].copy()
    _new_age = combined.loc[_recalc].apply(lambda r: _months(r["birth"], r["death"]), axis=1).astype("Int64")
    combined.loc[_recalc, "age"] = _new_age
    _changed_age = int((_old_age.fillna(-1) != combined["age"].fillna(-1)).sum())
    combined = combined.drop(columns="_dchg")                  # 一時列を除去
    _head("age再計算")
    _sub(f"対象 {_n(_recalc.sum())}行（birth/death変更＆両日付あり）→ 値が変わった {_n(_changed_age)}行")
    return combined


def add_nlbc_ancestors(combined) -> pd.DataFrame:
    """NLBCにあって combined に無い個体(＝辿った祖先)を新規行として追加"""
    _nb, _nb_death = _load_nlbc()
    _existing = set(combined["k"].dropna())
    _new_ids = [k for k in _nb.index if k not in _existing]
    _add = _nb.loc[_new_ids].reset_index()
    _rows = pd.DataFrame({
        "cat_id":    _add["k"],
        "birth":     _add["nb_birth"],
        "sex":       _add["nb_sex"],
        "m1_cat_id": _add["nb_m1"],
        "species":   _add["kind"].astype("string"),
        "death":     _add["k"].map(_nb_death),
        "source":    "NLBC",
    })
    _rows["age"] = _rows.apply(lambda r: _months(r["birth"], r["death"]), axis=1).astype("Int64")
    combined = pd.concat([combined.drop(columns="k"), _rows], ignore_index=True)
    _head("祖先行の追加")
    _sub(f"辿った祖先 {_n(len(_rows))}行を追加 → {_n(len(combined))}行 × {combined.shape[1]}列")
    return combined


def backfill_maternal_ancestors(combined) -> pd.DataFrame:
    """無名のNLBC母系行に、高知大母牛ファイルの名前/父を補完(m1_cat_idで一意特定できる分だけ)。
    """
    _snpd = pd.read_excel(DAM_SNP_XLSX, sheet_name="牛管理リスト", header=0)
    _fnd = pd.read_excel(DAM_FND_XLSX, sheet_name="牛管理リスト (2)", header=1)
    _snpd["cat_id"] = _clean_id(_snpd["認証番号"])
    _fnd["cat_id"] = _clean_id(_fnd["認証番号"])
    _dam_mo = _fnd.dropna(subset=["cat_id"]).drop_duplicates("cat_id").set_index("cat_id")["母"].astype("string")
    _dam_ped = _snpd.dropna(subset=["cat_id"]).drop_duplicates("cat_id").set_index("cat_id")
    _pos = combined.dropna(subset=["cat_id"]).drop_duplicates("cat_id", keep="first")
    _pos = dict(zip(_pos["cat_id"], _pos.index))

    def _fillcat(_cat, _col, _val):
        if _cat is None or pd.isna(_cat) or pd.isna(_val) or str(_val).strip() in ("", "nan"):
            return 0
        _i = _pos.get(_cat)
        if _i is None or pd.notna(combined.at[_i, _col]):
            return 0
        combined.at[_i, _col] = str(_val).strip()
        return 1

    _nbf = 0
    for _cid in _dam_ped.index:
        _i = _pos.get(_cid)
        if _i is None:
            continue
        _mcat = combined.at[_i, "m1_cat_id"]
        if pd.isna(_mcat):                                     # 母を一意特定できない → 入れない
            continue
        _nbf += _fillcat(_mcat, "name", _dam_mo.get(_cid))
        _nbf += _fillcat(_mcat, "p1_name", _dam_ped.at[_cid, "母方祖父"])
        _gi = _pos.get(_mcat)
        if _gi is None:
            continue
        _gcat = combined.at[_gi, "m1_cat_id"]
        if pd.isna(_gcat):
            continue
        _nbf += _fillcat(_gcat, "name", _dam_ped.at[_cid, "母方祖母"])
        _nbf += _fillcat(_gcat, "p1_name", _dam_ped.at[_cid, "母方祖母曽祖父"])
    _head("母系祖先の名前backfill")
    _sub(f"無名NLBC行に名前/父を {_n(_nbf)}セル補完（m1_cat_idで一意特定できたぶん）")
    return combined


def derive_m1_name(combined) -> pd.DataFrame:
    """母の名号を既存個体行(cat_id→name)から引いて補完。
    """
    _name_by_cat = (combined.dropna(subset=["cat_id", "name"])
                    .drop_duplicates("cat_id").set_index("cat_id")["name"])
    _derived = combined["m1_cat_id"].map(_name_by_cat).astype("string")
    if "m1_name" in combined.columns:
        combined["m1_name"] = _derived.fillna(combined["m1_name"])   # m1_cat_id由来を優先・無ければ母カラム
    else:
        combined["m1_name"] = _derived
    _head("m1_name導出")
    _sub(f"m1_name {_n(combined['m1_name'].notna().sum())}件（m1_cat_id由来優先・無ければ母カラム）")

    # m1_cat_idで名前が引けず(_derived空)、母カラム名が同名複数(_N版が存在)で特定不可 → _? を付与
    _ambig = set(combined["name"].dropna().astype("string").str.extract(r"^(.*)_\d+$", expand=False).dropna())
    _unres = (_derived.isna() & combined["m1_name"].notna()
              & ~combined["m1_name"].str.contains(r"_\d+$", regex=True, na=False)
              & combined["m1_name"].isin(_ambig))
    combined.loc[_unres, "m1_name"] = combined.loc[_unres, "m1_name"].astype("string") + "_?"
    _sub(f"うち特定不可で _? 付与: {_n(_unres.sum())}件")

    # --- 検証: m1_cat_id が指す先が行として存在するか（血縁グラフの閉じ具合） ---
    _ids = set(combined["cat_id"].dropna())
    _dangling = combined["m1_cat_id"].dropna()[~combined["m1_cat_id"].dropna().isin(_ids)]
    _sub(f"母記載 {_n(combined['m1_cat_id'].notna().sum())}行 / "
         f"母が行として不在(=辿れた祖先の最上流) {_dangling.nunique()}個体")
    return combined


def add_snp_flags(combined) -> pd.DataFrame:
    """has_snp(実genotypeに存在) / dupli_snp(同一cat_idが2つ以上のgenotype) を付与。"""
    _snpf = sorted(config.PROCESSED_DIR.glob("snp_*/snp_imputed.feather"))
    if not _snpf:
        raise FileNotFoundError("SNPデータが見つかりません: processed/snp_*/snp_imputed.feather")
    _snpset = set(pd.read_feather(_snpf[-1])["snp_id"].astype("string"))     # 実在するgenotypeのCEL集合

    _has = combined["snp_id"].notna() & combined["snp_id"].astype("string").isin(_snpset)
    _cnt = combined[_has].groupby("cat_id")["snp_id"].nunique()              # 個体あたり実genotype数
    _dup = _has & combined["cat_id"].isin(set(_cnt[_cnt >= 2].index))
    combined["has_snp"] = _has.astype(bool)
    combined["dupli_snp"] = _dup.astype(bool)

    _head("SNPフラグ付与")
    _sub(f"has_snp {_n(_has.sum())}件（snp_idありだがgenotype無し "
         f"{_n((combined['snp_id'].notna() & ~_has).sum())}件）")
    _sub(f"dupli_snp {_n(_dup.sum())}行 / {combined.loc[_dup, 'cat_id'].nunique()}個体（同一個体で複数genotype）")
    return combined


def assign_group(combined) -> pd.DataFrame:
    """group列(複数メンバーシップ)を付与。並び替えは reorder_columns で別途行う。

    ・排他な主グループ(source由来・帯): 血液/骨格筋/Sheet1育種価/NLBC母系/父 … table_report.add_group が判定。
    ・横断メンバーシップ(オーバーラップ可):
        高知大母      = 高知大母リストの認証番号(cat_id)に該当する全個体
        父(種雄牛)    = name が漢字のみ(かなを含まない)
        Sheet1育種価  = bv_* 列のいずれかが非欠損(育種価データ保有)。Sheet1の育種価は既存個体へ
                        肉付けされるため排他バンドでは過小 → 育種価を持つ全個体に横断付与(血液/骨格筋と両属可)。
    ・group は ";"区切りの複数ラベル(例 "血液;Sheet1育種価" / "Sheet1育種価;高知大母")。
    """
    _primary = pd.Series(table_report.add_group(combined), index=combined.index).astype("object")

    # 高知大母: リストの認証番号=cat_id に該当する全個体
    _kcat = set(_clean_id(pd.read_excel(DAM_SNP_XLSX, sheet_name="牛管理リスト", header=0)["認証番号"]).dropna())
    _is_kochi = combined["cat_id"].isin(_kcat)

    # 父(種雄牛): name が漢字のみ
    _is_sire = combined["name"].map(_is_kanji_only)

    # Sheet1育種価: bv_* のいずれかが非欠損（育種価データ保有）
    _bv_cols = [c for c in combined.columns if c.startswith("bv_")]
    _has_bv = combined[_bv_cols].notna().any(axis=1) if _bv_cols else pd.Series(False, index=combined.index)

    def _multi(_p, _bv, _k, _s):
        _ls = [] if pd.isna(_p) else [str(_p)]
        for _lbl, _flag in [("Sheet1育種価", _bv), ("高知大母", _k), ("父(種雄牛)", _s)]:
            if _flag and _lbl not in _ls:
                _ls.append(_lbl)
        return ";".join(_ls)

    combined["group"] = [_multi(p, bv, k, s)
                         for p, bv, k, s in zip(_primary, _has_bv, _is_kochi, _is_sire)]
    _head("group付与")
    _sub(f"横断メンバーシップ: Sheet1育種価 {_n(_has_bv.sum())} / "
         f"高知大母 {_n(_is_kochi.sum())} / 父 {_n(_is_sire.sum())}個体")
    return combined


def save_outputs(combined, version: str = "20260708") -> pd.DataFrame:
    """parquet + xlsx + HTML + manifest.json を processed/sample_<version>/ に出力。

    ・parquet=型保持(cat_id先頭0/datetime/Int64/bool)。xlsx=Excelで開ける形。HTML=動的ヒートマップ。
    ・group付与・列並び替えは呼び出し前に済ませておくこと。
    """
    out = config.PROCESSED_DIR / f"sample_{version}"
    out.mkdir(parents=True, exist_ok=True)

    combined.to_parquet(out / "sample_table.parquet", index=False)
    xlsx_report.build_xlsx(combined, out / "sample_table.xlsx")              # 整形 + カラム説明シート
    table_report.build_html_report(combined, out / "sample_table.html")

    # group は複数メンバーシップ(";"区切り) → グループごとの帰属個体数で集計
    _memb = combined["group"].fillna("").str.split(";")
    _gcount = {g: int(_memb.apply(lambda lst: g in lst).sum()) for g in table_report.GROUP_ORDER}
    json.dump({"version": version, "rows": int(len(combined)), "cols": int(combined.shape[1]),
               "groups": _gcount,
               "has_snp": int(combined["has_snp"].sum()), "dupli_snp": int(combined["dupli_snp"].sum())},
              open(out / "manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    _head("保存")
    _sub(f"{out}")
    _sub(f"parquet / xlsx / html / manifest.json  ({_n(len(combined))}行 × {combined.shape[1]}列)")
    _sub(f"group(メンバーシップ): {_gcount}")
    return combined
