"""プロジェクト共通のパス設定.

使い方:
    from jbrt.config import RAW_DIR, PROCESSED_DIR
    df = pd.read_feather(PROCESSED_DIR / "snpdata.feather")

データ置き場の指定方法（優先順）:
    1. 環境変数 JBRT_DATA_DIR があればそれを使う。
       例:  export JBRT_DATA_DIR=/path/to/JBRT_data
    2. 無ければ下の DEFAULT_DATA_DIR を使う。
       環境変数を使わない人は、この1行を自分の環境に合わせて書き換えるだけでよい。
"""

import os
from pathlib import Path

# --- ルート ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# --- データディレクトリ ---------------------------------------------------
# 既定のデータ置き場
# 環境変数を使わない場合は、この行を自分の環境に合わせて書き換える。
DEFAULT_DATA_DIR = PROJECT_ROOT.parent / "JBRT_data"

# 環境変数 JBRT_DATA_DIR があればそれを最優先。無ければ既定値。
_env_data_dir = os.environ.get("JBRT_DATA_DIR")
DATA_DIR = Path(_env_data_dir).expanduser() if _env_data_dir else DEFAULT_DATA_DIR

# raw(生データ) と processed(前処理済み) の二分割。
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

__all__ = [
    "PROJECT_ROOT",
    "DATA_DIR",
    "RAW_DIR",
    "PROCESSED_DIR",
]
