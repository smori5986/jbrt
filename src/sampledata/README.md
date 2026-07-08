# サンプル結合テーブル カラム説明

- `processed/sample_YYYYMMDD/sample_table.parquet` の列定義
- **9,364 行 × 73 列**

## 入力データ（元ファイルとシート）

<details>
<summary><b>サンプル表の元Excel</b>（<code>JBRT_data/raw/sample_data/</code>）</summary>

- **`20251029/☆旧血液サンフ_ル(2023まて_).xlsx`** … 血液サンプル ＋ 育種価マスタ
  - 血液サンプル: `A1_中央家畜保健衛生所` / `A2_中央・田野支所` / `A4_中央・嶺北支所` / `B1_西部家畜保健衛生所` / `B3_西部・梼原支所` / `畜試種雄牛` / `県繁殖（雌)` / `高知県雄(雌)追加` / `高知大学（仔牛）`
  - 育種価マスタ: `Sheet1`
- **`20260701/☆骨格筋サンフ_ル(2024_2026)1-1000.xlsx`**
  - 骨格筋サンプル: `骨格筋1-100` 〜 `骨格筋901-1000`（10シート）
  - 種雄牛情報: `種雄牛名号と登録番号`
  - ※ `畜産農家リスト` は未使用
- **`20260514_kochi_u_dams/`** : 高知大 母牛リスト
  - `cattle_management_list (SNPデータ有り).xlsx`
    - **`牛管理リスト`**
    - ※`Sheet1`は未使用
  - `cattle_management_list (始祖割合あり).xlsx`
    - **`牛管理リスト (2)`**
    - ※`牛管理リスト`は未使用

</details>

<details>
<summary><b>補正・付与に使う外部データ</b></summary>

- **snp_id正解表**:
    - `raw/SNP/*/AX*_Sample List.xlsx`: 通し番号↔snp_id
    - `raw/SNP/*/*サンプルQC結果*.xlsx`: DNA濃度(C2セル)
- **NLBC**（母系・出生/雌雄/種別/死亡）: Webスクレイプ
    - `raw/nlbc_data/nlbc_main.csv` / `nlbc_log.csv`
- **SNP genotype**（has_snp判定）:
    - `processed/snp_*/snp_imputed.feather`

</details>

## カラム定義（ジャンル別）

<details>
<summary><b>main</b>（個体の基本属性・血統・SNP）</summary>

1. **cat_id**
    - 型: string
    - 非欠損: 4294
    - 内容: 個体識別番号
2. **breed_id**
    - 型: string
    - 非欠損: 244
    - 内容: 登録番号（血統登録番号）
3. **name**
    - 型: string
    - 非欠損: 7524
    - 内容: 名号（牛の名前）。同名重複は末尾 `_N` で一意化
4. **snp_id**
    - 型: string
    - 非欠損: 1359
    - 内容: SNP解析コード＝CELファイル名（genotypingの識別子。SNPデータとの結合キー）
5. **has_snp**
    - 型: bool
    - 非欠損: 9364
    - 内容: snp_id が実SNPデータ(feather)に存在するか（True=genotypeあり）
6. **dupli_snp**
    - 型: bool
    - 非欠損: 9364
    - 内容: 同一個体(cat_id)が複数のgenotypeを持つ（複数回測定された）
7. **DNA_conc**
    - 型: float
    - 非欠損: 833
    - 内容: DNA濃度 (ng/μL)
8. **birth**
    - 型: datetime
    - 非欠損: 4290
    - 内容: 出生年月日
9. **death**
    - 型: datetime
    - 非欠損: 3584
    - 内容: と畜日／死亡日（NLBC異動履歴の と畜 or 死亡日）
10. **age**
    - 型: Int64
    - 非欠損: 3587
    - 内容: 出荷月齢（birth→death の月差）
11. **sex**
    - 型: string
    - 非欠損: 4361
    - 内容: 雌雄。`F`=メス / `M`=オス / `C`=去勢
12. **raising**
    - 型: string
    - 非欠損: 1411
    - 内容: 肥育繁殖区分。`fat`=肥育 / `breed`=繁殖
13. **species**
    - 型: string
    - 非欠損: 4289
    - 内容: 品種（褐毛和種 / ホルスタイン種 等。NLBC由来）
14. **p1_cat_id**
    - 型: string
    - 非欠損: 1201
    - 内容: 父の個体識別番号
15. **p1_name**
    - 型: string
    - 非欠損: 8061
    - 内容: 父の名号（種雄牛。漢字のみ）
16. **p1_breed_id**
    - 型: string
    - 非欠損: 7589
    - 内容: 父の登録番号
17. **m1_cat_id**
    - 型: string
    - 非欠損: 3374
    - 内容: 母の個体識別番号
18. **m1_name**
    - 型: string
    - 非欠損: 2470
    - 内容: 母の名号。`_?` = 同名複数で特定不可
19. **specimen**
    - 型: string
    - 非欠損: 1133
    - 内容: サンプル種別。`blood` / `muscle` / `hair`
20. **farm**
    - 型: string
    - 非欠損: 1352
    - 内容: 出生及び飼養農家名
21. **owner**
    - 型: string
    - 非欠損: 7238
    - 内容: 所有者名

</details>

<details>
<summary><b>phenotype</b>（枝肉格付・画像解析・脂肪酸）</summary>

### 枝肉格付項目
22. **01_Grade**
    - 型: string
    - 非欠損: 942
    - 略: Grade = Carcass Grade
    - 内容: 枝肉格付等級（A5等の総合等級。文字含む）
23. **21_CW**
    - 型: float
    - 非欠損: 942
    - 略: CW = Carcass Weight
    - 内容: 枝肉重量 (kg)
24. **03_REA**
    - 型: float
    - 非欠損: 942
    - 略: REA = Rib Eye Area
    - 内容: ロース芯面積 (cm²)＝胸最長筋面積
25. **04_RT**
    - 型: float
    - 非欠損: 942
    - 略: RT = Rib Thickness
    - 内容: バラの厚さ (cm)
26. **05_SFT**
    - 型: float
    - 非欠損: 942
    - 略: SFT = Subcutaneous Fat Thickness
    - 内容: 皮下脂肪の厚さ (cm)
27. **06_YE**
    - 型: float
    - 非欠損: 942
    - 略: YE = Yield Estimate（歩留基準値）
    - 内容: 歩留基準値
28. **07_BMS**
    - 型: Int64
    - 非欠損: 942
    - 略: BMS = Beef Marbling Standard
    - 内容: 脂肪交雑 BMS No.
29. **08_MG**
    - 型: Int64
    - 非欠損: 942
    - 略: MG = Marbling Grade
    - 内容: 脂肪交雑等級
30. **09_BCS**
    - 型: Int64
    - 非欠損: 942
    - 略: BCS = Beef Color Standard
    - 内容: 肉色 BCS No.
31. **10_MLus**
    - 型: Int64
    - 非欠損: 942
    - 略: MLus = Meat Lustre
    - 内容: 肉の光沢
32. **11_MQ1**
    - 型: Int64
    - 非欠損: 942
    - 略: MQ1 = Meat Quality grade 1
    - 内容: 肉質等級①
33. **12_Firm**
    - 型: Int64
    - 非欠損: 942
    - 略: Firm = Firmness
    - 内容: 肉の締まり
34. **13_Tex**
    - 型: Int64
    - 非欠損: 942
    - 略: Tex = Texture
    - 内容: 肉のきめ
35. **14_MQ2**
    - 型: Int64
    - 非欠損: 942
    - 略: MQ2 = Meat Quality grade 2
    - 内容: 肉質等級②
36. **15_BFS**
    - 型: Int64
    - 非欠損: 942
    - 略: BFS = Beef Fat Standard
    - 内容: 脂肪色 BFS No.
37. **16_FLQ**
    - 型: Int64
    - 非欠損: 942
    - 略: FLQ = Fat Lustre and Quality
    - 内容: 脂肪の光沢と質
38. **17_MQ3**
    - 型: Int64
    - 非欠損: 942
    - 略: MQ3 = Meat Quality grade 3
    - 内容: 肉質等級③
39. **18_Defect**
    - 型: Int64
    - 非欠損: 942
    - 略: Defect = Defect / Blemish
    - 内容: 瑕疵
40. **22_UP**
    - 型: float
    - 非欠損: 927
    - 略: UP = Unit Price
    - 内容: 取引単価 (円/kg)

### 画像解析
41. **img_REAi**
    - 型: float
    - 非欠損: 544
    - 略: REAi = Rib Eye Area (image-derived)
    - 内容: 画像解析ロース芯面積
42. **img_Fat**
    - 型: float
    - 非欠損: 561
    - 略: Fat = Fat ratio
    - 内容: 画像解析 脂肪割合
43. **img_Lean**
    - 型: float
    - 非欠損: 544
    - 略: Lean = Lean meat ratio
    - 内容: 画像解析 赤身割合
44. **img_FMI**
    - 型: float
    - 非欠損: 544
    - 略: FMI = Fine Marbling Index（コザシ）
    - 内容: 画像解析 コザシ指数
45. **img_CMI**
    - 型: float
    - 非欠損: 544
    - 略: CMI = Coarse Marbling Index（アラザシ）
    - 内容: 画像解析 アラザシ指数

### 脂肪酸組成
46. **fa_C18_1**
    - 型: float
    - 非欠損: 907
    - 略: C18:1 = Oleic acid（オレイン酸）
    - 内容: オレイン酸割合
47. **fa_SFA**
    - 型: float
    - 非欠損: 903
    - 略: SFA = Saturated Fatty Acids
    - 内容: 飽和脂肪酸割合
48. **fa_MUFA**
    - 型: float
    - 非欠損: 907
    - 略: MUFA = Monounsaturated Fatty Acids
    - 内容: 一価不飽和脂肪酸割合

</details>

<details>
<summary><b>breeding_value</b>（育種価。<code>bv_</code> 接頭辞）</summary>

> 育種価(EBV)は接頭辞 `bv_` ＋ 上記 phenotype と同じ Short を流用（略の由来も同じ）。

49. **bv_CW**
    - 型: float
    - 非欠損: 5884
    - 略: CW = Carcass Weight (EBV)
    - 内容: 枝肉重量 育種価
50. **bv_REA**
    - 型: float
    - 非欠損: 5884
    - 略: REA = Rib Eye Area (EBV)
    - 内容: ロース芯面積 育種価
51. **bv_RT**
    - 型: float
    - 非欠損: 5884
    - 略: RT = Rib Thickness (EBV)
    - 内容: バラ厚 育種価
52. **bv_SFT**
    - 型: float
    - 非欠損: 5884
    - 略: SFT = Subcutaneous Fat Thickness (EBV)
    - 内容: 皮下脂肪厚 育種価
53. **bv_YE**
    - 型: float
    - 非欠損: 5884
    - 略: YE = Yield Estimate (EBV)
    - 内容: 推定歩留 育種価
54. **bv_BMS**
    - 型: float
    - 非欠損: 5884
    - 略: BMS = Beef Marbling Standard (EBV)
    - 内容: 脂肪交雑 BMS 育種価
55. **bv_C18_1**
    - 型: float
    - 非欠損: 1642
    - 略: C18:1 = Oleic acid (EBV)
    - 内容: オレイン酸 育種価
56. **bv_SFA**
    - 型: float
    - 非欠損: 1642
    - 略: SFA = Saturated Fatty Acids (EBV)
    - 内容: 飽和脂肪酸 育種価
57. **bv_MUFA**
    - 型: float
    - 非欠損: 1642
    - 略: MUFA = Monounsaturated Fatty Acids (EBV)
    - 内容: 一価不飽和脂肪酸 育種価
58. **bv_AFC**
    - 型: float
    - 非欠損: 4784
    - 略: AFC = Age at First Calving (EBV)
    - 内容: 初産月齢 育種価
59. **bv_CI**
    - 型: float
    - 非欠損: 4784
    - 略: CI = Calving Interval (EBV)
    - 内容: 分娩間隔 育種価

</details>

<details>
<summary><b>meta</b>（由来メタ情報）</summary>

60. **source**
    - 型: string
    - 非欠損: 9124
    - 内容: 由来ファイル名（旧血液Excel / 骨格筋Excel / `NLBC` / 高知大母リスト）。空=種雄牛の名号だけ追加した行
61. **sheet**
    - 型: string
    - 非欠損: 8291
    - 内容: 由来シート名（施設シート / `Sheet1`(育種価マスタ) / `骨格筋N-M` 等）
62. **group**
    - 型: string
    - 非欠損: 9364
    - 内容: 由来グループ。`;`区切りの複数ラベル（1個体が複数帰属可）。排他=血液/骨格筋/Sheet1育種価/NLBC母系、横断=高知大母/父(種雄牛)

</details>

<details>
<summary><b>other</b>（補助識別子・保管情報・未使用列）</summary>

63. **sample_name**
    - 型: string
    - 非欠損: 1433
    - 内容: 通し番号（入庫サンプルの連番。サンプルリスト↔CEL の橋渡しに使う補助キー）
64. **チューブID**
    - 型: string
    - 非欠損: 1000
    - 内容: 保管チューブID
65. **ラックID**
    - 型: string
    - 非欠損: 1433
    - 内容: 保管ラックID
66. **ポジション**
    - 型: string
    - 非欠損: 1402
    - 内容: ラック内ポジション
67. **説明／備考**
    - 型: string
    - 非欠損: 64
    - 内容: 備考
68. **サンプルタイプ**
    - 型: string
    - 非欠損: 0
    - 内容: 全空（未使用）
69. **枝肉の写真**
    - 型: string
    - 非欠損: 0
    - 内容: 全空（未使用）
70. **SNP解析結果**
    - 型: string
    - 非欠損: 0
    - 内容: 全空（未使用）
71. **遺伝子型解析結果**
    - 型: string
    - 非欠損: 0
    - 内容: 全空（未使用）
72. **SNP解析結果.1**
    - 型: float
    - 非欠損: 0
    - 内容: 全空（未使用・重複ヘッダ由来）
73. **遺伝子型解析結果.1**
    - 型: float
    - 非欠損: 0
    - 内容: 全空（未使用・重複ヘッダ由来）

</details>

---

## 残タスク（claude作成）

- [ ] **fat_breed(raising) の補完** … `name`あり＆`raising`空 → `breed`(繁殖) を補完
- [ ] **farm の食い違い 4個体**（`1240239281` `1399709796` `1267672214` `1253491645`）… 出生農家 vs 飼養農家、どちらを正とするか未定
- [ ] **個体単位テーブルへの正規化**（任意）… `cat_id`重複15個体をどう畳むか


