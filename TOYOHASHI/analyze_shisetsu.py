#!/usr/bin/env python3
"""shisetsu_list.csv から派生テーブルを生成する。

出力:
- DATA/derived_nendai_bunpu.csv   建築年代(10年区切り)×延床面積・施設数
- DATA/derived_kouku_summary.csv  小学校区別の施設数・延床・築40年以上比率
- DATA/derived_chikuko_top.csv    築40年以上かつ延床面積上位50施設
すべての数値は shisetsu_list.csv（出典: 豊橋市公共施設白書2025 個別票）由来。
"""
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
BASE_YEAR = 2026  # 築年数の基準年（白書2025は2024年度実績、公開年2026に合わせる）


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

    # 1. 年代別分布
    decades = defaultdict(lambda: [0, 0.0])
    for r in dated:
        d = int(r["建築年度_最古棟"]) // 10 * 10
        decades[d][0] += 1
        decades[d][1] += float(r["延べ床面積合計_m2"])
    write("derived_nendai_bunpu.csv",
          ["建築年代", "施設数", "延床面積合計_m2", "築年数レンジ_2026年時点"],
          [[f"{d}年代", n, round(a, 1), f"{max(0, BASE_YEAR-d-9)}〜{BASE_YEAR-d}年"]
           for d, (n, a) in sorted(decades.items())])

    # 2. 校区別サマリー
    kouku = defaultdict(lambda: {"n": 0, "m2": 0.0, "old_n": 0, "old_m2": 0.0})
    for r in dated:
        k = r["小学校区"] or "（校区記載なし）"
        m2 = float(r["延べ床面積合計_m2"])
        kouku[k]["n"] += 1
        kouku[k]["m2"] += m2
        if BASE_YEAR - int(r["建築年度_最古棟"]) >= 40:
            kouku[k]["old_n"] += 1
            kouku[k]["old_m2"] += m2
    write("derived_kouku_summary.csv",
          ["小学校区", "施設数", "延床面積合計_m2", "築40年以上_施設数",
           "築40年以上_延床m2", "築40年以上_延床比率_%"],
          [[k, v["n"], f"{v['m2']:.4f}", v["old_n"], f"{v['old_m2']:.4f}",
            round(v["old_m2"] / v["m2"] * 100, 1) if v["m2"] else ""]
           for k, v in sorted(kouku.items(), key=lambda x: -x[1]["m2"])])

    # 3. 築40年以上×延床上位50
    old = [r for r in dated if BASE_YEAR - int(r["建築年度_最古棟"]) >= 40]
    old.sort(key=lambda r: -float(r["延べ床面積合計_m2"]))
    write("derived_chikuko_top.csv",
          ["施設名", "施設分類_大分類", "小学校区", "建築年度_最古棟",
           "築年数_2026年時点", "延べ床面積合計_m2", "支出2024_円",
           "利用者数2024_人", "出典PDF", "出典ページ"],
          [[r["施設名"], r["施設分類_大分類"], r["小学校区"],
            r["建築年度_最古棟"], BASE_YEAR - int(r["建築年度_最古棟"]),
            r["延べ床面積合計_m2"], r["支出2024_円"], r["利用者数2024_人"],
            r["出典PDF"], r["出典ページ"]] for r in old[:50]])


if __name__ == "__main__":
    main()
