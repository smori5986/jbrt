# 🐂　jbrt

- JBRTプロジェクトの共通ユーティリティ
- データパス設定（`jbrt.config`）とSNP前処理関数（`jbrt.snp`）を提供

## インストール

```bash
pip install "git+https://github.com/smori5986/jbrt.git"
```

開発用（ソースを編集しながら使う）:

```bash
git clone https://github.com/smori5986/jbrt.git
cd jbrt
pip install -e .
```

## データの置き場所

`jbrt` はデータを含まない。データの場所を環境変数で指定する:

```bash
export JBRT_DATA_DIR=/path/to/JBRT_data
```

未設定なら `config.py` の `DEFAULT_DATA_DIR` が使われる。

想定するディレクトリ構成:

```
JBRT_data/
├── raw/                  # 生データ
│   ├── SNP/                # Genotyping TXT（提供元のまま置く）
│   ├── SNP_meta/           # アレイ注釈CSV（SNPの染色体・物理位置など）
│   └── sample_data/        # 個体情報・表現型・血統などサンプル付随データ
└── processed/            # 前処理済みデータ
```

## SNP前処理

- `jbrt.snp`：Genotyping TXT の読み込み〜フィルタ〜補完〜並び替えの純粋関数
- 実行例：`notebooks/preprocess_snp.ipynb`

## ライセンス

MIT License（[LICENSE](LICENSE) を参照）。
