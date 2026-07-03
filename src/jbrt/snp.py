"""SNPジェノタイピングデータの前処理ユーティリティ.

すべて DataFrame を受け取り DataFrame を返す純粋関数。パスや進捗表示
(print) は持たないので、実験ごとのスクリプト側でパス・固有処理・ログを
担当する。

前提:
    データの向き  : 行=サンプル, 列=SNP (probeset_id)
    ジェノタイプ  : 文字列 "AA"/"AB"/"BB"、または 数値 0/1/2 (Bアレルの個数)
"""

import logging
from pathlib import Path

import pandas as pd
from pandas.api.types import CategoricalDtype
from scipy.stats import chi2

logger = logging.getLogger(__name__)

# 有効なジェノタイプと数値コード (Bアレルの個数)
VALID_GENOTYPES = ("AA", "AB", "BB")
GENOTYPE_TO_CODE = {"AA": 0, "AB": 1, "BB": 2}

__all__ = [
    "VALID_GENOTYPES",
    "GENOTYPE_TO_CODE",
    "load_genotyping_txt",
    "concat_common_snps",
    "filter_missing",
    "to_numeric",
    "filter_maf",
    "filter_hwe",
    "mean_impute",
    "load_metadata",
    "reorder_by_metadata",
]


def load_genotyping_txt(path) -> pd.DataFrame:
    """1つの Genotyping TXT を読み込み、サンプル×SNP の DataFrame を返す.

    - 先頭のメタ行は ``probeset_id`` で始まるヘッダー行まで読み飛ばす。
    - ``*_call_code`` 列(各サンプルのコール)だけ抽出し、サフィックスを除去。
    - SNP×サンプル を転置してサンプル×SNP にする。
    """
    path = Path(path)

    # ヘッダー (probeset_id で始まる行) を探す
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        header_line_idx = next(
            idx for idx, line in enumerate(f) if line.startswith("probeset_id")
        )

    df = pd.read_csv(
        path, sep="\t", skiprows=header_line_idx,
        encoding="utf-8", low_memory=False,
    )

    # probeset_id + 各サンプルの *_call_code 列だけ残す
    sample_cols = [c for c in df.columns if c.endswith("_call_code")]
    df = df[["probeset_id"] + sample_cols]
    df.columns = ["probeset_id"] + [c.replace("_call_code", "") for c in sample_cols]

    # 転置: SNP×サンプル → サンプル×SNP
    df = df.set_index("probeset_id").T
    df.index.name = "sample_id"
    return df


def concat_common_snps(dfs) -> pd.DataFrame:
    """複数バッチを共通SNP(列の積集合)で揃えて縦(サンプル方向)に結合する."""
    dfs = list(dfs)
    if len(dfs) == 1:
        return dfs[0]

    common = set(dfs[0].columns)
    for d in dfs[1:]:
        common &= set(d.columns)
    common = sorted(common)

    return pd.concat([d[common] for d in dfs], axis=0)


def filter_missing(df: pd.DataFrame, threshold: float = 0.05) -> pd.DataFrame:
    """無効値→NaN、欠損率>=threshold の行・列を除外し、定数列を除外する.

    欠損率は無効値をNaN化した直後 (列・行の除外前) の値で評価する。
    """
    # AA/AB/BB 以外を NaN に
    df_nan = df.where(df.isin(VALID_GENOTYPES))

    row_missing = df_nan.isna().mean(axis=1)
    col_missing = df_nan.isna().mean(axis=0)

    # 高欠損の列・行を除外
    drop_cols = col_missing[col_missing >= threshold].index
    drop_rows = row_missing[row_missing >= threshold].index
    out = df_nan.drop(columns=drop_cols).drop(index=drop_rows)

    # 定数列 (ユニーク値が1以下) を除外
    constant_cols = out.columns[out.nunique(dropna=True) <= 1]

    logger.info(
        "欠損処理: 欠損列除外=%d, 欠損行除外=%d, 定数列除外=%d (閾値=%.0f%%)",
        len(drop_cols), len(drop_rows), len(constant_cols), threshold * 100,
    )
    return out.drop(columns=constant_cols)


def to_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """文字列ジェノタイプ "AA"/"AB"/"BB" を 0/1/2 に変換する."""
    with pd.option_context("future.no_silent_downcasting", True):
        return df.replace(GENOTYPE_TO_CODE).infer_objects(copy=False)


def filter_maf(df: pd.DataFrame, threshold: float = 0.01) -> pd.DataFrame:
    """MAF < threshold のSNP(列)を除外する. 入力は数値(0/1/2)."""
    af = df.mean() / 2                       # Bアレル頻度
    maf = af.where(af <= 0.5, 1 - af)        # マイナーアレル頻度
    keep = maf >= threshold
    logger.info("MAFフィルタ: %d列除外 (MAF < %g)", int((~keep).sum()), threshold)
    return df.loc[:, keep]


def filter_hwe(df: pd.DataFrame, threshold: float = 1e-4) -> pd.DataFrame:
    """HWE検定(カイ二乗, df=1)で p < threshold のSNPを除外する. 入力は数値."""
    n = df.notna().sum()
    n0, n1, n2 = (df == 0).sum(), (df == 1).sum(), (df == 2).sum()
    p = (2 * n0 + n1) / (2 * n)             # Aアレル頻度
    q = 1 - p
    e0, e1, e2 = n * p**2, n * 2 * p * q, n * q**2
    chi_sq = (n0 - e0)**2 / e0 + (n1 - e1)**2 / e1 + (n2 - e2)**2 / e2
    pvals = 1 - chi2.cdf(chi_sq, df=1)
    keep = pvals >= threshold
    logger.info("HWEフィルタ: %d列除外 (p < %g)", int((~keep).sum()), threshold)
    return df.loc[:, keep]


def mean_impute(df: pd.DataFrame) -> pd.DataFrame:
    """各列(SNP)の欠損を、その列の平均値で補完する."""
    return df.apply(lambda col: col.fillna(col.mean()), axis=0)


def load_metadata(path, skiprows: int = 20) -> pd.DataFrame:
    """アレイ注釈CSVを読み込み、染色体→物理位置順にソートして返す.

    染色体の並びは 1〜29, X, Y, MT。``Physical Position`` はカンマ除去して数値化。
    """
    meta = pd.read_csv(path, skiprows=skiprows, header=0)

    meta["Physical Position"] = (
        meta["Physical Position"]
        .astype(str).str.replace(",", "", regex=False).str.strip()
        .pipe(pd.to_numeric, errors="coerce")
    )

    chrom_order = [str(i) for i in range(1, 30)] + ["X", "Y", "MT"]
    chrom_dtype = CategoricalDtype(categories=chrom_order, ordered=True)
    meta["Chromosome"] = (
        meta["Chromosome"].astype(str).replace("nan", pd.NA).astype(chrom_dtype)
    )

    return meta.sort_values(
        by=["Chromosome", "Physical Position"],
        ascending=[True, True],
        na_position="last",
    ).reset_index(drop=True)


def reorder_by_metadata(
    df: pd.DataFrame, meta: pd.DataFrame, id_col: str = "Probe Set ID"
) -> pd.DataFrame:
    """meta の id_col の順序に合わせて df の列を並び替える(共通IDのみ残す)."""
    meta_ids = meta[id_col].astype(str).tolist()
    cols = set(df.columns.astype(str))
    common = [pid for pid in meta_ids if pid in cols]
    return df[common].copy()
