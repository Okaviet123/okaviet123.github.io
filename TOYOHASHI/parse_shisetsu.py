#!/usr/bin/env python3
"""豊橋市公共施設白書2025 個別票PDF → 施設一覧CSV パーサー

RAW/hakusho/kobetsu_*.pdf (9本のうち個別票8本; hakusho2025_full.pdf は対象外) を
pdftotext -layout でテキスト化し、1施設=1行の CSV (DATA/shisetsu_list.csv) を生成する。

設計メモ:
- 各施設は「豊橋市公共施設白書 個別票」ヘッダー行で始まる(全ファイル計413回出現)。
- 主要行は全413施設で書式が完全に一致することを事前調査で確認済み:
    収 入 <v22> <v23> <v24> 利用者数(人） <u22> <u23> <u24>
    支 出 <v22> <v23> <v24>
    その他支出 <v22> <v23> <v24> 1人当たり <市民c22> <c23> <c24>
    減価償却費 <v22> <v23> <v24> 1人当たり <利用者c22> <c23> <c24>
    施設建築面積合計 <v> ㎡ 施設延べ床面積合計 <v> ㎡ ...
- 「－」「―」等のダッシュは欠損として空欄にする。推測で埋めない。
- 建築年度は「９．建物の明細」以降の行の YYYY（元号N）から最古の西暦年を採る。
  (「７．主な保全履歴」にも同形式の年が出るため、必ず明細ヘッダー以降に限定する)
- 3施設(梅薮地区津波防災センター/西部住宅/屋内プール・アイスアリーナ)は個別票1ページ目が
  画像のみ(テキスト層なし)のため pdftotext では抽出不能。ヘッダーも取れないため、
  テキスト空白ページを施設境界として分割した上で、pdftoppm で描画した画像から
  目視転記した値(IMAGE_PAGE_SUPPLEMENT)を充てる。転記元ページは各エントリに明記。
  施設名は白書本編(hakusho2025_full.pdf)の目次でも確認済み(全416施設、通番118/377/387)。
"""

import csv
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
RAW_DIR = BASE / "RAW" / "hakusho"
DATA_DIR = BASE / "DATA"

PDFS = [
    "kobetsu_bunka_shakaikyouiku.pdf",
    "kobetsu_gakkou.pdf",
    "kobetsu_gyousei.pdf",
    "kobetsu_iryou_fukushi.pdf",
    "kobetsu_kosodate.pdf",
    "kobetsu_sangyou.pdf",
    "kobetsu_sonota.pdf",
    "kobetsu_sports.pdf",
]

HEADER_RE = re.compile(r"豊橋市公共施設白書\s+個別票")
DASHES = {"－", "―", "ー", "-", "—", "‐"}

# 元号付き年度 (例: 1988（昭和63） / 2019（平成31） / 2023（令和5）)
ERA_YEAR_RE = re.compile(r"(\d{4})（(?:明治|大正|昭和|平成|令和)")

RE_NAME = re.compile(r"^\s*施設名\s+(.+?)\s*$")
RE_BUNRUI = re.compile(r"^\s*分\s*類\s+(.+?)\s*$")
RE_BUKA = re.compile(r"^\s*所管部課\s+(.+?)\s*$")
RE_ADDR = re.compile(r"^\s*所在地\s+(.+?)\s*$")
RE_SHOGAKKO = re.compile(r"^\s*小学校区\s+(.+?)\s*\(\s*[\d,]+\s*人\)")
RE_AREA = re.compile(
    r"施設建築面積合計\s+(\S+)\s+㎡\s+施設延べ床面積合計\s+(\S+)\s+㎡"
)
RE_SHUNYU = re.compile(
    r"収\s*入\s+(\S+)\s+(\S+)\s+(\S+)\s+利用者数\(人）\s+(\S+)\s+(\S+)\s+(\S+)"
)
RE_SHISHUTSU = re.compile(r"^\s*支\s*出\s+(\S+)\s+(\S+)\s+(\S+)\s*$")
RE_SONOTA_SHISHUTSU = re.compile(
    r"その他支出\s+(\S+)\s+(\S+)\s+(\S+)\s+1人当たり\s+(\S+)\s+(\S+)\s+(\S+)"
)
RE_GENKA = re.compile(
    r"減価償却費\s+(\S+)\s+(\S+)\s+(\S+)\s+1人当たり\s+(\S+)\s+(\S+)\s+(\S+)"
)
RE_MEISAI = re.compile(r"９．建物の明細")

# 個別票1ページ目が画像のみ(テキスト層なし)の施設。
# pdftoppm -r 150 で描画した画像から目視転記(2026-07-27)。キーは (PDFファイル名, PDF内ページ番号)。
# 「－」の項目は空欄のまま。建築年度は後続テキストページの「９．建物の明細」から通常どおり抽出する。
IMAGE_PAGE_SUPPLEMENT = {
    ("kobetsu_gyousei.pdf", 219): {  # 白書掲載ページ p.814
        "施設名": "梅薮地区津波防災センター",
        "施設分類_大分類": "行政系施設",
        "施設分類_小分類": "防災施設",
        "所管部課": "防災危機管理課",
        "所在地": "愛知県豊橋市梅薮町字西神２５番地の１",
        "小学校区": "前芝",
        "延べ床面積合計_m2": "266.38",
        "建築面積合計_m2": "272.20",
        "収入2024_円": "151074",
        "支出2024_円": "172365",
        "減価償却費2024_円": "7139242",
        "利用者数2024_人": "",  # 原本「－」
        "市民1人当たりコスト2024_円": "20",
        "利用者1人当たりコスト2024_円": "",  # 原本「－」
    },
    ("kobetsu_gyousei.pdf", 239): {  # 白書掲載ページ p.834
        "施設名": "西部住宅",
        "施設分類_大分類": "行政系施設",
        "施設分類_小分類": "市営住宅",
        "所管部課": "建設部 住宅課",
        "所在地": "愛知県豊橋市牟呂町字東里２９番地の１",
        "小学校区": "汐田",
        "延べ床面積合計_m2": "36145.06",
        "建築面積合計_m2": "7379.45",
        "収入2024_円": "775924563",  # 注: 市営住宅の収支は全住宅の合計金額(原本注記)
        "支出2024_円": "1137568020",
        "減価償却費2024_円": "213504159",
        "利用者数2024_人": "349",  # 原本注記: 入居戸数(単位:戸)
        "市民1人当たりコスト2024_円": "1567",
        "利用者1人当たりコスト2024_円": "1647988",
    },
    ("kobetsu_sports.pdf", 41): {  # 白書掲載ページ p.296
        "施設名": "屋内プール・アイスアリーナ",
        "施設分類_大分類": "スポーツ系施設",
        "施設分類_小分類": "スポーツ施設",
        "所管部課": "文化・スポーツ部 スポーツ課",
        "所在地": "愛知県豊橋市神野新田町字メノ割１番地の３",
        "小学校区": "吉田方",
        "延べ床面積合計_m2": "11644.33",
        "建築面積合計_m2": "9422.16",
        "収入2024_円": "12535",
        "支出2024_円": "158185430",
        "減価償却費2024_円": "105065800",
        "利用者数2024_人": "118543",
        "市民1人当たりコスト2024_円": "717",
        "利用者1人当たりコスト2024_円": "2221",
    },
}

FIELDNAMES = [
    "施設名",
    "施設分類_大分類",
    "施設分類_小分類",
    "所管部課",
    "所在地",
    "小学校区",
    "延べ床面積合計_m2",
    "建築面積合計_m2",
    "建築年度_最古棟",
    "収入2024_円",
    "支出2024_円",
    "減価償却費2024_円",
    "利用者数2024_人",
    "市民1人当たりコスト2024_円",
    "利用者1人当たりコスト2024_円",
    "出典PDF",
    "出典ページ",
]


def clean_num(token):
    """数値トークンを正規化。ダッシュ類は空欄。カンマは除去。"""
    if token is None:
        return ""
    t = token.strip()
    if not t or all(ch in DASHES for ch in t):
        return ""
    return t.replace(",", "")


def extract_text_lines(pdf_path):
    """pdftotext -layout の結果を (行, PDFページ番号1始まり) のリストで返す。"""
    out = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    lines = []
    page = 1
    for raw_line in out.split("\n"):
        # 改ページ(\f)は行頭に付く
        while raw_line.startswith("\f"):
            page += 1
            raw_line = raw_line[1:]
        if "\f" in raw_line:
            # 行中の\f (通常は発生しないが念のため)
            parts = raw_line.split("\f")
            for i, part in enumerate(parts):
                lines.append((part, page + i))
            page += len(parts) - 1
            continue
        lines.append((raw_line, page))
    return lines


def blank_text_pages(lines):
    """テキストが1行もないページ番号の集合(末尾\\f由来の見かけ上のページは除く)。"""
    page_has_text = {}
    for ln, pg in lines:
        page_has_text.setdefault(pg, False)
        if ln.strip():
            page_has_text[pg] = True
    max_text_page = max((pg for pg, has in page_has_text.items() if has), default=0)
    # 完全に空のページは連続\fにより行が1本も生成されないことがあるため、
    # 1..max_text_page の範囲で「テキストを持つ行が無いページ」を空白ページとする
    return {
        pg
        for pg in range(1, max_text_page + 1)
        if not page_has_text.get(pg, False)
    }


def split_facilities(lines):
    """個別票ヘッダー行を境に施設ブロックへ分割する。

    さらに、ブロック途中にテキスト空白ページ(画像のみの個別票1ページ目)がある場合は
    そこでも分割する。分割後半は「1ページ目が画像の施設」ブロックとなり、
    (blank_page番号, ブロック) として返す。
    戻り値: (ヘッダー出現数, [(blank_page or None, block), ...])
    """
    blanks = blank_text_pages(lines)
    starts = [i for i, (ln, _pg) in enumerate(lines) if HEADER_RE.search(ln)]
    blocks = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        block = lines[start:end]
        # ブロック内の空白ページ(先頭ページ以外)で分割。
        # 空白ページ自体は行を生成しないことがあるため「空白ページより後の最初の行」で切る。
        blank_in_block = sorted(
            pg for pg in blanks if block[0][1] < pg <= block[-1][1]
        )
        cut = None
        blank_pg = None
        if blank_in_block:
            blank_pg = blank_in_block[0]
            for j, (_ln, pg) in enumerate(block):
                if pg >= blank_pg:
                    cut = j
                    break
        if cut is not None and any(ln.strip() for ln, _pg in block[cut:]):
            blocks.append((None, block[:cut]))
            # 出典ページが空白ページ(=画像の1ページ目)から始まるよう疑似行を先頭に置く
            blocks.append((blank_pg, [("", blank_pg)] + block[cut:]))
        else:
            blocks.append((None, block))
    return len(starts), blocks


def first_match(regex, block):
    for ln, _pg in block:
        m = regex.search(ln)
        if m:
            return m
    return None


def parse_facility(block, pdf_name, cap_page=None, supplement=None):
    """cap_page: 次施設の開始ページ。ブロック末尾には次施設ページの
    冒頭行(ページ右上の施設名ラベル等)が含まれるため、終了ページはその手前で打ち切る。"""
    rec = dict.fromkeys(FIELDNAMES, "")
    rec["出典PDF"] = pdf_name
    p0 = block[0][1]
    last_content_page = p0
    for ln, pg in block:
        if ln.strip():
            last_content_page = pg
    if cap_page is not None:
        last_content_page = min(last_content_page, cap_page - 1)
    last_content_page = max(last_content_page, p0)
    rec["出典ページ"] = (
        f"p.{p0}" if last_content_page == p0 else f"p.{p0}-{last_content_page}"
    )

    m = first_match(RE_NAME, block)
    if m:
        rec["施設名"] = re.sub(r"\s+", " ", m.group(1)).strip()

    m = first_match(RE_BUNRUI, block)
    if m:
        parts = m.group(1).split(None, 1)
        rec["施設分類_大分類"] = parts[0]
        if len(parts) > 1:
            rec["施設分類_小分類"] = parts[1].strip()

    m = first_match(RE_BUKA, block)
    if m:
        rec["所管部課"] = re.sub(r"\s+", " ", m.group(1)).strip()

    m = first_match(RE_ADDR, block)
    if m:
        rec["所在地"] = re.sub(r"\s+", " ", m.group(1)).strip()

    m = first_match(RE_SHOGAKKO, block)
    if m:
        rec["小学校区"] = re.sub(r"\s+", " ", m.group(1)).strip()

    m = first_match(RE_AREA, block)
    if m:
        rec["建築面積合計_m2"] = clean_num(m.group(1))
        rec["延べ床面積合計_m2"] = clean_num(m.group(2))

    m = first_match(RE_SHUNYU, block)
    if m:
        rec["収入2024_円"] = clean_num(m.group(3))
        rec["利用者数2024_人"] = clean_num(m.group(6))

    m = first_match(RE_SHISHUTSU, block)
    if m:
        rec["支出2024_円"] = clean_num(m.group(3))

    m = first_match(RE_SONOTA_SHISHUTSU, block)
    if m:
        rec["市民1人当たりコスト2024_円"] = clean_num(m.group(6))

    m = first_match(RE_GENKA, block)
    if m:
        rec["減価償却費2024_円"] = clean_num(m.group(3))
        rec["利用者1人当たりコスト2024_円"] = clean_num(m.group(6))

    # 建築年度: ９．建物の明細 以降(継続ページの再掲ヘッダー含む)の元号付き年から最古を採る
    meisai_start = None
    for i, (ln, _pg) in enumerate(block):
        if RE_MEISAI.search(ln):
            meisai_start = i
            break
    if meisai_start is not None:
        years = []
        for ln, _pg in block[meisai_start + 1 :]:
            for ym in ERA_YEAR_RE.finditer(ln):
                years.append(int(ym.group(1)))
        if years:
            rec["建築年度_最古棟"] = str(min(years))

    if supplement:
        for k, v in supplement.items():
            rec[k] = v

    return rec


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_records = []
    per_pdf = []  # (pdf名, ヘッダー出現数, 抽出施設数)
    for pdf_name in PDFS:
        pdf_path = RAW_DIR / pdf_name
        if not pdf_path.exists():
            print(f"ERROR: not found: {pdf_path}", file=sys.stderr)
            sys.exit(1)
        lines = extract_text_lines(pdf_path)
        n_headers, blocks = split_facilities(lines)
        records = []
        n_image_pages = 0
        for i, (blank_pg, b) in enumerate(blocks):
            cap = blocks[i + 1][1][0][1] if i + 1 < len(blocks) else None
            supp = None
            if blank_pg is not None:
                n_image_pages += 1
                supp = IMAGE_PAGE_SUPPLEMENT.get((pdf_name, blank_pg))
                if supp is None:
                    print(
                        f"WARNING: {pdf_name} p.{blank_pg} は画像のみのページですが"
                        f"転記データが未登録です(空欄のまま出力)",
                        file=sys.stderr,
                    )
            records.append(parse_facility(b, pdf_name, cap_page=cap, supplement=supp))
        per_pdf.append((pdf_name, n_headers, n_image_pages, len(records)))
        all_records.extend(records)

    out_csv = DATA_DIR / "shisetsu_list.csv"
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_records)

    # 集計・整合性チェックを標準出力に出す
    total = len(all_records)
    print(f"total facilities: {total}")
    for name, nh, ni, nr in per_pdf:
        flag = "OK" if nh + ni == nr else "MISMATCH"
        print(
            f"  {name}: text_headers={nh} image_only_pages={ni} "
            f"extracted={nr} [{flag}]"
        )

    empty_names = [r for r in all_records if not r["施設名"]]
    print(f"empty facility names: {len(empty_names)}")
    seen = {}
    for r in all_records:
        key = r["施設名"]
        seen.setdefault(key, []).append(r["出典PDF"])
    dups = {k: v for k, v in seen.items() if len(v) > 1}
    print(f"duplicate facility names: {len(dups)}")
    for k, v in sorted(dups.items()):
        print(f"  DUP: {k} <- {v}")

    # 欠損集計
    for col in FIELDNAMES:
        n_empty = sum(1 for r in all_records if not r[col])
        if n_empty:
            print(f"empty[{col}] = {n_empty}")


if __name__ == "__main__":
    main()
