"""NLBC 牛個体情報検索 (https://www.id.nlbc.go.jp/CattleSearch/) のスクレイパ。

個体識別番号(cat_id)を渡すと、個体情報(出生/雌雄/母牛ID/種別)と異動履歴を取得する。

設計:
  - firefox の起動が一番重いので、driver は 1 回だけ作ってリストを回す(search_many)。
  - search_one は driver を使い回して 1 頭ぶんを処理する部品。
  - ブラウザは snap 非依存の素の firefox を使う(このサーバ用):
      firefox : /home/s_mori/opt/firefox/firefox
      geckodriver : /home/s_mori/opt/geckodriver

使い方:
    from nlbc_scraper import search_many
    df_info, df_transfer = search_many(["1140049058", "1140048488"])
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

FIREFOX_BIN = "/home/s_mori/opt/firefox/firefox"
GECKODRIVER = "/home/s_mori/opt/geckodriver"
BASE_URL = "https://www.id.nlbc.go.jp/CattleSearch/search/agreement"


def make_driver(headless: bool = True):
    """ローカルの素の firefox で WebDriver を1つ作る(Docker/Seleniumサーバ不要)。"""
    opts = Options()
    if headless:
        opts.add_argument("--headless")
    opts.binary_location = FIREFOX_BIN
    return webdriver.Firefox(service=Service(GECKODRIVER), options=opts)


def search_one(driver, cow_id: str, wait: float = 2.0) -> dict:
    """1頭ぶんを検索して情報を返す。driver は使い回す(quitしない)。

    返り値 dict:
      cat_id, birth, sex, m1_cat_id, kind, transfers(list[dict]), ok(bool)
    見つからない/失敗時は ok=False で他は None/空。
    """
    cow_id = str(cow_id).strip()
    # status: "ok"(取得成功) / "not_found"(該当テーブル無し) / "error"(例外)
    rec = {"cat_id": cow_id, "birth": None, "sex": None, "m1_cat_id": None,
           "kind": None, "transfers": [], "status": "error", "error": None}
    try:
        driver.get(BASE_URL)
        # 同意ボタンがあれば押す(セッションが同意を覚えていない場合、毎回出る)
        agree = driver.find_elements(By.XPATH, '//input[@alt="同意する"]')
        if agree:
            agree[0].click()
            time.sleep(0.5)
        # 個体識別番号を入力 → 検索
        box = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "txtIDNO")))
        box.clear()
        box.send_keys(cow_id)
        time.sleep(0.3)
        btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, '//input[@alt="検索"]')))
        driver.execute_script("arguments[0].scrollIntoView(true);", btn)
        btn.click()
        time.sleep(wait)
    except Exception as e:  # noqa: BLE001 (検索操作の失敗は個体単位でスキップ)
        rec["status"] = "error"
        rec["error"] = f"{type(e).__name__}: {str(e).splitlines()[0][:200]}"
        return rec

    tables = BeautifulSoup(driver.page_source, "html.parser").find_all("table", {"border": "2"})
    if len(tables) < 2:
        rec["status"] = "not_found"    # 該当なし or ページ構造が想定外
        rec["error"] = f"結果テーブルが{len(tables)}個(2未満)"
        return rec

    # --- 個体情報テーブル(1つ目): [個体識別番号, 出生の年月日, 雌雄の別, 母牛の個体識別番号, 種別] ---
    cols = tables[0].find_all("tr")[1].find_all("td")
    _get = lambda i: (cols[i].get_text(strip=True) or None) if i < len(cols) else None
    rec["birth"] = _get(1)
    rec["sex"] = _get(2)
    rec["m1_cat_id"] = _get(3)
    rec["kind"] = _get(4)

    # --- 異動情報テーブル(2つ目): 各行 [連番, 異動内容, 年月日, 都道府県, 市区町村, 名称] ---
    moves = []
    for row in tables[1].find_all("tr"):
        c = row.find_all("td")
        if len(c) < 6:
            continue
        moves.append({
            "cat_id": cow_id,
            "異動内容": c[1].get_text(strip=True),
            "異動年月日": c[2].get_text(strip=True),
            "都道府県": c[3].get_text(strip=True),
            "市区町村": c[4].get_text(strip=True),
            "名称": c[5].get_text(strip=True),
        })
    rec["transfers"] = moves
    rec["status"] = "ok"
    return rec


def search_many(cow_ids, headless: bool = True, wait: float = 2.0, progress: bool = True):
    """個体識別番号のリストを検索し、(個体情報df, 異動履歴df) を返す。

    driver は1回だけ作ってリストを回す(高速)。個体単位の失敗はスキップして続行。
    """
    ids = [str(c).strip() for c in cow_ids if str(c).strip()]
    if progress:
        try:
            from tqdm import tqdm
            ids_iter = tqdm(ids)
        except ImportError:
            ids_iter = ids
    else:
        ids_iter = ids

    driver = make_driver(headless=headless)
    info_rows, transfer_rows = [], []
    try:
        for cid in ids_iter:
            rec = search_one(driver, cid, wait=wait)
            info_rows.append({k: rec[k] for k in
                              ("cat_id", "birth", "sex", "m1_cat_id", "kind", "status", "error")})
            transfer_rows.extend(rec["transfers"])
    finally:
        driver.quit()

    df_info = pd.DataFrame(info_rows)
    df_transfer = pd.DataFrame(transfer_rows)

    # --- エラー/該当なしの集計と一覧表示 ---
    vc = df_info["status"].value_counts().to_dict()
    n_ok = vc.get("ok", 0)
    n_nf = vc.get("not_found", 0)
    n_err = vc.get("error", 0)
    print(f"[検索完了] {len(df_info)}件: ok={n_ok} / not_found={n_nf} / error={n_err}")
    failed = df_info[df_info["status"] != "ok"]
    if len(failed):
        print("失敗した個体:")
        for _, r in failed.iterrows():
            print(f"  {r['cat_id']}  [{r['status']}]  {r['error']}")
    return df_info, df_transfer


def _norm_id(x) -> str | None:
    """個体識別番号を数字のみ→10桁ゼロ埋め文字列に正規化。不正/空は None。"""
    if x is None:
        return None
    d = re.sub(r"\D", "", str(x))
    if not d or int(d) == 0:
        return None
    return d.zfill(10) if len(d) <= 10 else d


def _append_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    """rows を CSV に追記(ヘッダはファイルが無い時だけ)。全列を文字列で書く。"""
    if not rows:
        return
    df = pd.DataFrame(rows, columns=columns).astype("string")
    df.to_csv(path, mode="a", header=not path.exists(), index=False, encoding="utf-8-sig")


MAIN_COLS = ["cat_id", "birth", "sex", "m1_cat_id", "kind", "status", "error"]
LOG_COLS = ["cat_id", "異動内容", "異動年月日", "都道府県", "市区町村", "名称"]


def search_pedigree(seed_ids, out_dir, batch_save: int = 30, headless: bool = True,
                    wait: float = 2.0, max_gen: int | None = None):
    """cat_id を起点に、母(m1_cat_id)を辿って候補が尽きるまで再帰的にNLBC検索する。

    - 保存: out_dir/nlbc_main.csv(個体情報) と nlbc_log.csv(異動履歴) に **追記**。
      値は全部文字列(CSV, dtype=str想定)なので先頭0/日付が崩れない。
    - チェックポイント: batch_save 件ごとに追記保存。中断しても末尾数件のみ損失。
    - レジューム: 既存 nlbc_main.csv の cat_id は検索済みとしてスキップ。同じ out_dir で
      再実行すれば続きから走る。
    - フロンティア(次に検索する集合)は毎世代ディスクから再計算するので中断に強い。

    戻り値: (df_main, df_log)  ※ファイルからの読み直し(dtype=str)。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    main_path = out_dir / "nlbc_main.csv"
    log_path = out_dir / "nlbc_log.csv"

    seed = {i for i in (_norm_id(s) for s in seed_ids) if i}
    gen = 0
    while True:
        # 検索済み集合 と 次のフロンティアを、保存済みCSVから再計算
        if main_path.exists():
            prev = pd.read_csv(main_path, dtype=str)
            searched = {i for i in (_norm_id(c) for c in prev["cat_id"]) if i}
            mothers = {i for i in (_norm_id(m) for m in prev["m1_cat_id"].dropna()) if i}
        else:
            searched, mothers = set(), set()
        frontier = sorted((seed | mothers) - searched)
        if not frontier:
            break
        gen += 1
        if max_gen is not None and gen > max_gen:
            print(f"[打ち切り] max_gen={max_gen} に達したので停止 (frontier {len(frontier)}件 未検索)")
            break

        print(f"\n=== 世代{gen}: {len(frontier)}件 検索 (検索済 {len(searched)}) ===")
        try:
            from tqdm import tqdm
            it = tqdm(frontier)
        except ImportError:
            it = frontier

        driver = make_driver(headless=headless)
        buf_main, buf_log = [], []
        n_ok = n_nf = n_err = 0
        try:
            for cid in it:
                rec = search_one(driver, cid, wait=wait)
                n_ok += rec["status"] == "ok"
                n_nf += rec["status"] == "not_found"
                n_err += rec["status"] == "error"
                buf_main.append({k: rec[k] for k in MAIN_COLS})
                buf_log.extend(rec["transfers"])
                if len(buf_main) >= batch_save:           # ★チェックポイント保存
                    _append_csv(main_path, buf_main, MAIN_COLS)
                    _append_csv(log_path, buf_log, LOG_COLS)
                    buf_main, buf_log = [], []
        finally:
            _append_csv(main_path, buf_main, MAIN_COLS)    # 残りをflush
            _append_csv(log_path, buf_log, LOG_COLS)
            driver.quit()
        print(f"  完了: ok={n_ok} / not_found={n_nf} / error={n_err}")

    df_main = pd.read_csv(main_path, dtype=str) if main_path.exists() else pd.DataFrame(columns=MAIN_COLS)
    df_log = pd.read_csv(log_path, dtype=str) if log_path.exists() else pd.DataFrame(columns=LOG_COLS)
    n_mo = df_main["m1_cat_id"].notna().sum() if len(df_main) else 0
    print(f"\n[全世代完了] 個体 {len(df_main)}件 / 異動 {len(df_log)}件 / 母記載 {n_mo}件")
    fail = df_main[df_main["status"] != "ok"] if len(df_main) else df_main
    if len(fail):
        print(f"  失敗(not_found/error) {len(fail)}件: 例", fail["cat_id"].head(10).tolist())
    return df_main, df_log


if __name__ == "__main__":
    import sys
    _ids = sys.argv[1:] or ["1140049058", "1140048488"]
    info, transfer = search_many(_ids)
    print(info.to_string(index=False))
    print("\n--- 異動履歴 ---")
    print(transfer.to_string(index=False))
