#!/usr/bin/env python3
"""DATA/shisetsu_list.csv から派生テーブルを生成する汎用スクリプト。
豊橋#1の analyze_shisetsu.py から一般化したもの。

出力:
- DATA/derived_nendai_bunpu.csv   建築年代(10年区切り)×延床面積・施設数
- DATA/derived_kouku_summary.csv  地域単位別の施設数・延床・築古比率
- DATA/derived_chikuko_top.csv    築古かつ延床面積上位N施設

前提: DATA/shisetsu_list.csv が references/data_schema.md の標準スキーマに
沿っていること（施設名/施設分類_大分類/建築年度_最古棟/延べ床面積合計_m2 の
列名は固定。地域単位の列名だけ市に合わせて DISTRICT_COL で指定する）。
"""
import csv
from collections import defaultdict
from pathlib import Path

# ==== ここを市ごとに調整する ====
ROOT = Path(__file__).parent
BASE_YEAR = 2026        # 築年数の基準年（レポート公開年に合わせる）
OLD_THRESHOLD = 40      # 「築古」とみなす年数の下限
TOP_N = 50              # 築古×延床上位テーブルの件数
DISTRICT_COL = "小学校区"  # 地域単位の列名（校区/地区/町丁目など、市によって変える）
SPEND_COL = "支出2024_円"       # 直近年度の支出額列（年度部分は市に合わせて変える）
USERS_COL = "利用者数2024_人"   # 直近年度の利用者数列
# ================================


def load():
    with (ROOT / "DATA" / "shisetsu_list.csv").open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write(name, header, rows):
    p = ROOT / "DATA" / name
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {p.name}: {len(rows)} rows")


def main():
    rows = load()
    dated = [r for r in rows if r["建築年度_最古棟"] and r["延べ床面積合計_m2"]]
    if not dated:
        print("建築年度・延床面積がある行がありません。列名がスキーマ通りか確認してください。")
        return

    # 1. 年代別分布
    decades = defaultdict(lambda: [0, 0.0])
    for r in dated:
        d = int(r["建築年度_最古棟"]) // 10 * 10
        decades[d][0] += 1
        decades[d][1] += float(r["延べ床面積合計_m2"])
    write("derived_nendai_bunpu.csv",
          ["建築年代", "施設数", "延床面積合計_m2", f"築年数レンジ_{BASE_YEAR}年時点"],
          [[f"{d}年代", n, round(a, 1), f"{max(0, BASE_YEAR-d-9)}〜{BASE_YEAR-d}年"]
           for d, (n, a) in sorted(decades.items())])

    # 2. 地域単位別サマリー（中間値は丸めずに保持 = 二重丸め誤差を防ぐ）
    dist = defaultdict(lambda: {"n": 0, "m2": 0.0, "old_n": 0, "old_m2": 0.0})
    for r in dated:
        k = r[DISTRICT_COL] or f"（{DISTRICT_COL}記載なし）"
        m2 = float(r["延べ床面積合計_m2"])
        dist[k]["n"] += 1
        dist[k]["m2"] += m2
        if BASE_YEAR - int(r["建築年度_最古棟"]) >= OLD_THRESHOLD:
            dist[k]["old_n"] += 1
            dist[k]["old_m2"] += m2
    write("derived_kouku_summary.csv",
          [DISTRICT_COL, "施設数", "延床面積合計_m2", f"築{OLD_THRESHOLD}年以上_施設数",
           f"築{OLD_THRESHOLD}年以上_延床m2", f"築{OLD_THRESHOLD}年以上_延床比率_%"],
          [[k, v["n"], f"{v['m2']:.4f}", v["old_n"], f"{v['old_m2']:.4f}",
            round(v["old_m2"] / v["m2"] * 100, 1) if v["m2"] else ""]
           for k, v in sorted(dist.items(), key=lambda x: -x[1]["m2"])])

    # 3. 築古×延床上位N
    old = [r for r in dated if BASE_YEAR - int(r["建築年度_最古棟"]) >= OLD_THRESHOLD]
    old.sort(key=lambda r: -float(r["延べ床面積合計_m2"]))
    write("derived_chikuko_top.csv",
          ["施設名", "施設分類_大分類", DISTRICT_COL, "建築年度_最古棟",
           f"築年数_{BASE_YEAR}年時点", "延べ床面積合計_m2", SPEND_COL,
           USERS_COL, "出典PDF", "出典ページ"],
          [[r["施設名"], r["施設分類_大分類"], r[DISTRICT_COL],
            r["建築年度_最古棟"], BASE_YEAR - int(r["建築年度_最古棟"]),
            r["延べ床面積合計_m2"], r.get(SPEND_COL, ""), r.get(USERS_COL, ""),
            r["出典PDF"], r["出典ページ"]] for r in old[:TOP_N]])

    total = sum(float(r["延べ床面積合計_m2"]) for r in dated)
    old_total = sum(float(r["延べ床面積合計_m2"]) for r in old)
    print(f"\n{len(dated)}施設中、築{OLD_THRESHOLD}年以上は{len(old)}施設 "
          f"（延床ベースで {old_total/total*100:.0f}%）")


if __name__ == "__main__":
    main()
