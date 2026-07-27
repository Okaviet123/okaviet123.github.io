#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_hakusho.py — 蒲郡市公共施設白書（RAW/hakusho/hakusho_r2kaitei.pdf）から
施設単位のデータを抽出し、DATA/shisetsu_list.csv（references/data_schema.md の
標準スキーマ）を作る。

白書の構造（1本のPDFを実際に読んで確認済み、2026-07-27）:
- 第3章（施設用途ごと）: 3-1〜3-12の各節がさらに「小分類」の副節に分かれ、
  各副節が「施設名称」の見出し行1行のみで始まる（例: 「庁舎・車庫」
  「公民館」「消防資機材庫等」）。この見出し行の直後に、施設ごとの行を持つ
  3つの表が続く:
    - 図N   老朽化状況（小分類）: 施設名称・延床面積(㎡)・建築年度・老朽化度
    - 図N+1 利用状況（小分類）  : 施設名称・延床面積・H26〜R1年度別利用者数・6年平均
    - 図N+2 コスト状況（小分類）: 施設名称・施設/事業運営/人/指定管理料の内訳・合計
  （利用状況・コスト状況とも「6ヵ年度（H26〜R1）の平均値」という注記がある。
  年度別の実額ではなく6年平均のみを採用する。）
  ※図3-88のキャプションは「老朽化状況（消防署）」と印字されているが、直前の
  副節見出しは「消防資機材庫等」であり、施設名（西部防災センター・三谷防災倉庫・
  形原防災倉庫）も消防署ではない。白書側のキャプション誤記と判断し、副節見出し
  （消防資機材庫等）を正としている。
- 第4章（地区別）: 4-3〜4-9の各節に「公共施設一覧（◯◯地区）」という表があり、
  地区利用型・全市利用型を問わずその地区に属する施設が一覧になっている。
  施設用途（大分類・中分類）の列は縦結合セルでpdftotext上崩れるため使わず、
  施設名称と地区の対応関係の取得だけに使う（大分類・小分類は第3章側の見出しから
  取得する方が確実なため）。

方式: pdftotext -layout の出力を \\f（フォームフィード）でページ単位に分割し、
ページ番号を保持したまま行単位の正規表現で抽出する。施設名をキーに3系統の
表（老朽化状況／利用状況／コスト状況／地区一覧）をマージする。

取れない値（対象外の老朽化度、―表記の利用者数・コスト等）は空欄のまま出す。
推測で埋めない。
"""

import csv
import os
import re
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(BASE, "RAW", "hakusho", "hakusho_r2kaitei.pdf")
OUT_CSV = os.path.join(BASE, "DATA", "shisetsu_list.csv")
SRC_NAME = os.path.basename(PDF_PATH)

ERA_BASE = {"S": 1925, "H": 1988, "R": 2018}

# 3章の小分類→大分類（TOCおよび各副節見出しの実物で確認済み）。
# 「公営住宅等」「公営住宅」表記ゆれ、図3-88のキャプション誤記（消防署→実際は
# 消防資機材庫等）はここで吸収する。
SHOUBUNRUI_TO_DAIBUNRUI = {
    "庁舎・車庫": "庁舎等施設",
    "市民会館": "公民館等施設",
    "公民館": "公民館等施設",
    "博物館等": "生涯学習施設",
    "図書館": "生涯学習施設",
    "スポーツ施設等": "運動・公園施設",
    "公園": "運動・公園施設",
    "小学校": "学校教育施設",
    "中学校": "学校教育施設",
    "専門学校": "学校教育施設",
    "その他（学校教育）": "学校教育施設",
    "保育園": "児童福祉施設",
    "児童館": "児童福祉施設",
    "福祉センター等": "保健・福祉施設",
    "ごみ処理施設等": "衛生施設",
    "公営住宅": "公営住宅施設",
    "公営住宅等": "公営住宅施設",
    "観光施設": "観光施設",
    "消防署": "消防・防災施設",
    "消防資機材庫等": "消防・防災施設",
    "駅周辺施設": "その他施設",
    "その他": "その他施設",
}

DISTRICTS = ["大塚", "三谷", "蒲郡北", "蒲郡南", "塩津", "形原", "西浦"]

# 地区別施設一覧表で、施設名の前に同じ行として現れる縦結合セルのラベル語
# （利用種別・施設用途大分類・施設用途中分類）。空白の数が年度によって1個だけ
# だったり2個以上だったりして揺れるため、空白の数ではなくラベルそのものの
# 既知集合で判定してはぎ取る。
CATEGORY_PREFIX_WORDS = sorted(
    set(SHOUBUNRUI_TO_DAIBUNRUI) | set(SHOUBUNRUI_TO_DAIBUNRUI.values()) | {
        "地区利用型施設", "全市利用型施設", "児童遊園地等",
    },
    key=len, reverse=True,
)


def strip_category_prefix(text: str) -> str:
    """先頭のラベル語を剥がす。ただし剥がした結果が空になる場合は剥がさない
    （「市民会館」「図書館」のように小分類名＝施設名そのものの場合に、
    施設名を消し去ってしまわないようにするため）。"""
    t = text.strip()
    changed = True
    while changed:
        changed = False
        for w in CATEGORY_PREFIX_WORDS:
            if t.startswith(w):
                rest = t[len(w):].lstrip()
                if rest and rest != t:
                    t = rest
                    changed = True
                    break
    return t


def pdf_pages(pdf_path):
    """ページごとのテキストのリスト（1ページ=1要素、0始まりindex=ページ番号-1）を返す。"""
    r = subprocess.run(["pdftotext", "-layout", pdf_path, "-"],
                        capture_output=True, text=True, check=True)
    pages = r.stdout.split("\f")
    if pages and pages[-1].strip() == "":
        pages = pages[:-1]
    return pages


def era_to_seireki(token: str):
    m = re.match(r"([SHR])(元|\d+)", token)
    if not m:
        return None
    n = 1 if m.group(2) == "元" else int(m.group(2))
    return ERA_BASE[m.group(1)] + n


# 延床面積(㎡) + 建築年度 + 老朽化度(数値 or 対象外) で終わる行の「尾部」だけを
# 先にマッチさせ、その手前のテキストを施設名候補とする。地区別施設一覧表では
# 施設用途（大分類・中分類）の縦結合セルが施設名の前に同じ行として現れることが
# あるため（例:「小学校      大塚小学校」）、2つ以上の空白で区切られた最後の
# セグメントだけを施設名として採用する。
ROW_TAIL_RE = re.compile(
    r"[ \t]+(?P<area>[\d,]+)[ \t]+(?P<year>[SHR](?:元|\d+))[ \t]+(?P<aging>[\d.]+|対象外)\b"
)
NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def parse_facility_row(line):
    """行から (施設名, 延床面積_m2, 建築年度_西暦, 老朽化度) を取り出す。
    マッチしなければ None。"""
    m = ROW_TAIL_RE.search(line)
    if not m:
        return None
    prefix = line[:m.start()].strip()
    if not prefix:
        return None
    name = strip_category_prefix(prefix)
    if not name:
        return None
    area = float(m.group("area").replace(",", ""))
    year = era_to_seireki(m.group("year"))
    aging = m.group("aging")
    return name, area, year, (None if aging == "対象外" else float(aging))


def parse_aging_table(lines):
    """老朽化状況（小分類）表: {施設名: (延床面積_m2, 建築年度_西暦, 老朽化度)}"""
    out = {}
    for ln in lines:
        r = parse_facility_row(ln)
        if not r:
            continue
        name, area, year, agedeg = r
        out[name] = (area, year, agedeg)
    return out


def parse_usage_table(lines):
    """利用状況（小分類）表: {施設名: 利用者数_6年平均}
    行末の数値列のうち最後に出現するものが「6年平均」列（年度別の値が―で欠けて
    いても6年平均は最終列に位置するため、最後の数値を採用すれば良い）。"""
    out = {}
    for ln in lines:
        m = re.match(r"^[ \t]*(?P<name>[^\s\d][^\d]*?)[ \t]+(?P<area>[\d,]+)[ \t]+(?P<rest>.*)$", ln)
        if not m:
            continue
        nums = NUM_RE.findall(m.group("rest"))
        if not nums:
            continue
        name = m.group("name").strip()
        out[name] = int(nums[-1].replace(",", ""))
    return out


def parse_cost_table(lines):
    """コスト状況（小分類）表: {施設名: 支出合計_6年平均_千円}（最終列=合計）。"""
    out = {}
    for ln in lines:
        m = re.match(r"^[ \t]*(?P<name>[^\s\d][^\d]*?)[ \t]+(?P<rest>[\d,\-\s]+)$", ln)
        if not m:
            continue
        nums = NUM_RE.findall(m.group("rest"))
        if len(nums) < 2:
            continue
        name = m.group("name").strip()
        out[name] = int(nums[-1].replace(",", ""))
    return out


def collect_pages_text(pages, start_idx, max_pages=6):
    """start_idxページから、次の小分類見出し（別の既知ラベル行）に当たるまで
    最大max_pagesページ分のテキストをまとめて返す（表がページをまたぐ場合に対応）。"""
    return "\n".join(pages[start_idx:start_idx + max_pages])


def extract_daisan_shou(pages):
    """第3章: 小分類ごとの老朽化状況/利用状況/コスト状況をマージして返す。
    戻り値: {施設名: {"小分類":..,"大分類":..,"延床面積_m2":..,"建築年度":..,
                      "老朽化度":..,"利用者数_6年平均":..,"支出6年平均_千円":..,
                      "出典ページ":N}}"""
    result = {}
    known_labels = set(SHOUBUNRUI_TO_DAIBUNRUI)
    for i, page in enumerate(pages):
        for line in page.splitlines():
            label = line.strip()
            if label not in known_labels:
                continue
            # 小分類見出し行を発見。直後の数ページ分から3表を切り出す。
            block = collect_pages_text(pages, i, max_pages=6)
            block_lines = block.splitlines()
            daibunrui = SHOUBUNRUI_TO_DAIBUNRUI[label]

            def section(title_kw, lines):
                out, capturing = [], False
                for ln in lines:
                    if not capturing and title_kw in ln and "老朽化状況" in ln or \
                       not capturing and title_kw in ln and ("利用状況" in ln or "コスト状況" in ln):
                        capturing = True
                        continue
                    if capturing:
                        if re.search(r"図\s*3-\d+|データ掲載上の条件|^3-\d+\s", ln):
                            break
                        out.append(ln)
                return out

            aging_lines = section(f"老朽化状況（{label}）", block_lines)
            usage_lines = section(f"利用状況（{label}）", block_lines)
            cost_lines = section(f"コスト状況（{label}）", block_lines)

            aging = parse_aging_table(aging_lines)
            usage = parse_usage_table(usage_lines)
            cost = parse_cost_table(cost_lines)

            for name, (area, year, agedeg) in aging.items():
                result[name] = {
                    "施設名": name,
                    "施設分類_大分類": daibunrui,
                    "施設分類_小分類": label,
                    "延べ床面積合計_m2": area,
                    "建築年度_最古棟": year,
                    "老朽化度": agedeg,
                    "利用者数_人": usage.get(name),
                    "支出6年平均_円": cost[name] * 1000 if name in cost else None,
                    "出典ページ": i + 1,
                }
    return result


def extract_dai4_shou_districts(pages, known_names):
    """第4章: 地区別公共施設一覧表から {施設名: 地区} を返す。
    この表の「施設用途（大分類・中分類）」ラベルは、第3章の小分類見出しと表記が
    微妙に違う（例:「庁舎・車庫」⇔「庁舎･倉庫」、全角/半角の中点、「その他
    （学校教育）」⇔「その他(学校給食)」）ことがあり、既知ラベル語での前方一致
    除去では取りこぼす。そのため、第3章側で既に確定している施設名の集合
    （known_names）を使い、行頭からのテキストが「どの既知施設名で終わるか」
    で照合する（施設名が最長一致するものを採用）。"""
    known_sorted = sorted(known_names, key=len, reverse=True)
    out = {}
    for i, page in enumerate(pages):
        m = re.search(r"公共施設一覧[（(](.+?)地区[）)]", page)
        if not m:
            continue
        district = m.group(1)
        if district not in DISTRICTS:
            continue
        block = collect_pages_text(pages, i, max_pages=4)
        for ln in block.splitlines():
            if "データ掲載上の条件" in ln:
                break
            tm = ROW_TAIL_RE.search(ln)
            if not tm:
                continue
            prefix = ln[:tm.start()].strip()
            for name in known_sorted:
                if prefix.endswith(name):
                    out[name] = district
                    break
    return out


COLUMNS = [
    "施設名", "施設分類_大分類", "施設分類_小分類", "所管部課", "所在地",
    "地区", "延べ床面積合計_m2", "建築面積合計_m2", "建築年度_最古棟",
    "老朽化度", "支出6年平均_円", "減価償却費_円", "利用者数_人",
    "市民1人当たりコスト_円", "利用者1人当たりコスト_円",
    "出典PDF", "出典ページ",
]


def main():
    pages = pdf_pages(PDF_PATH)
    print(f"総ページ数: {len(pages)}")

    facilities = extract_daisan_shou(pages)
    districts = extract_dai4_shou_districts(pages, facilities.keys())

    matched_district = sum(1 for n in facilities if n in districts)
    print(f"第3章から抽出した施設: {len(facilities)}件")
    print(f"第4章の地区別一覧から地区が判明した施設: {matched_district}/{len(facilities)}件")

    unmatched = [n for n in facilities if n not in districts]
    if unmatched:
        print(f"地区が特定できなかった施設（{len(unmatched)}件）: {', '.join(unmatched[:20])}"
              + (" ..." if len(unmatched) > 20 else ""))

    rows = []
    for name, f in sorted(facilities.items(), key=lambda x: (x[1]["施設分類_大分類"], x[1]["出典ページ"])):
        rows.append({
            "施設名": name,
            "施設分類_大分類": f["施設分類_大分類"],
            "施設分類_小分類": f["施設分類_小分類"],
            "所管部課": "",
            "所在地": "",
            "地区": districts.get(name, ""),
            "延べ床面積合計_m2": f["延べ床面積合計_m2"],
            "建築面積合計_m2": "",
            "建築年度_最古棟": f["建築年度_最古棟"],
            "老朽化度": f["老朽化度"] if f["老朽化度"] is not None else "",
            "支出6年平均_円": f["支出6年平均_円"] if f["支出6年平均_円"] is not None else "",
            "減価償却費_円": "",
            "利用者数_人": f["利用者数_人"] if f["利用者数_人"] is not None else "",
            "市民1人当たりコスト_円": "",
            "利用者1人当たりコスト_円": "",
            "出典PDF": SRC_NAME,
            "出典ページ": f"p.{f['出典ページ']}",
        })

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"\n出力: {OUT_CSV} ({len(rows)}施設)")

    no_year = sum(1 for r in rows if r["建築年度_最古棟"] == "")
    no_area = sum(1 for r in rows if r["延べ床面積合計_m2"] == "")
    no_usage = sum(1 for r in rows if r["利用者数_人"] == "")
    no_cost = sum(1 for r in rows if r["支出6年平均_円"] == "")
    print(f"欠損: 建築年度={no_year}, 延床面積={no_area}, 利用者数={no_usage}, 支出={no_cost}")


if __name__ == "__main__":
    main()
