#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_kessancard.py — 蒲郡市の決算関連資料（RAW/kessancard/ 配下のPDF・xlsx）から
財政指標の時系列CSVを作る。

前提の訂正（2026-07-27、フェーズ3の実物確認で判明）:
`SKILLS/muni-facility-report/scripts/parse_kessancard.py`（豊橋市#1の「決算カード」
＝Ａ・Ｂ・Ｃ等の記号付き単票様式、をテンプレート化したもの）をそのまま流用したが、
蒲郡市がTARGETSの「決算カード」ラベルで公開しているPDFの中身は実際には
**「財政状況資料集」**（総務省の様式で、記号ではなくラベル直後に「当年度・前年度」
の2列で数値が並ぶ、総括表1ページ＋普通会計の状況1ページ以降の複数ページ様式）
だった。年度によって以下3種の様式が混在する:

  1. H18〜H21（1ページ、"財政状況等一覧表"）: 旧・簡易様式。歳入/歳出/形式収支/
     実質収支/地方債現在高（百万円単位、"普通会計"合計行）のみ。財政力指数・
     経常収支比率・実質公債費比率・将来負担比率・積立金・地方税・住基人口・
     性質別歳出の内訳は掲載がなく、該当列は空欄になる（様式に存在しない項目で
     あり、抽出ミスではない）。
  2. H22, H23, H24, H25, H26, H28, H29（PDF、"財政状況資料集"）: 総括表＋普通会計
     の状況の様式。H24のみ入手できたPDFが総括表(1ページ目)止まりで、地方税・
     性質別歳出（人件費/扶助費/公債費/普通建設事業費）は掲載ページがなく空欄。
  3. H27, H30, R01〜R06（xlsx、"財政状況資料集"）: 同じ様式のExcel版。「総括表」
     「普通会計の状況」シートが2と同一の情報を持つ。

方式:
- PDFは pdftotext -layout でテキスト化。xlsxはopenpyxlでシートを読み、各行を
  「ラベル 数値 数値 ラベル 数値 …」の疑似テキスト行に変換する。PDF・xlsxとも
  同じラベル起点の正規表現抽出ロジックで処理できる。
- 総括表・普通会計の状況の当年度・前年度2列は「当年度が先」（財政状況資料集の
  ヘッダ「区分 令和6年度(千円) 令和5年度(千円)」の並び順どおり）。当年度値のみ採用。
- ラベル直後に空白のみを挟んで数値が続く場合だけを一致とみなす（例:
  「地方税の状況」という見出しの「地方税」に誤爆しない。「地方税 13,897,389 …」
  という実データ行にのみ一致する）。
- △ ▲ － の全角/半角マイナス記号は負数。数値そのものが続かない「－」単独は欠損
  （空欄）として扱う。
- 取れない値は空欄。推測で埋めない。

使い方: RAW/kessancard/ にPDF・xlsxを置いてから
  python3 parse_kessancard.py
"""

import csv
import os
import re
import subprocess
import sys
import unicodedata

import openpyxl

BASE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE, "RAW", "kessancard")
OUT_CSV = os.path.join(BASE, "DATA", "kessancard_timeseries.csv")

# ---------------------------------------------------------------- 基本ユーティリティ

NUM_RE = re.compile(r"(△|▲|-|−)?\s*(\d[\d,]*(?:\.\d+)?)")


def z2h(s: str) -> str:
    """全角英数字→半角。"""
    return unicodedata.normalize("NFKC", s)


def parse_num(sign: str, digits: str):
    v = float(digits.replace(",", "")) if "." in digits else int(digits.replace(",", ""))
    return -v if sign else v


def pdftotext(pdf_path: str) -> list:
    r = subprocess.run(
        ["pdftotext", "-layout", pdf_path, "-"],
        capture_output=True, text=True, check=True,
    )
    if "Missing language pack" in r.stderr and not r.stdout.strip():
        raise RuntimeError(
            f"{os.path.basename(pdf_path)}: poppler-data 未導入のためCJK抽出不可。"
            " `apt-get install poppler-data` を実行してください。")
    return r.stdout.splitlines()


def pdftotext_pages(pdf_path: str) -> list:
    """ページごとのテキスト（\\fフォームフィード区切り）のリストを返す。
    総括表（1ページ目）に限定して検索することで、後続ページの類似団体比較・
    経年分析グラフ内の無関係な数値を誤って拾わないようにするために使う
    （敵対的校閲で発見: 将来負担比率が「－」の年度に、後続ページの類似団体
    平均値を誤って採用していた）。"""
    r = subprocess.run(
        ["pdftotext", "-layout", pdf_path, "-"],
        capture_output=True, text=True, check=True,
    )
    if "Missing language pack" in r.stderr and not r.stdout.strip():
        raise RuntimeError(
            f"{os.path.basename(pdf_path)}: poppler-data 未導入のためCJK抽出不可。"
            " `apt-get install poppler-data` を実行してください。")
    pages = r.stdout.split("\f")
    if pages and pages[-1].strip() == "":
        pages = pages[:-1]
    return pages


def xlsx_to_lines(xlsx_path: str, sheet_names) -> list:
    """指定シートの各行を疑似テキスト行（セル値をスペース区切りで連結）に変換する。
    シートの並び順・行の並び順を保つ（ラベルの「最初の出現」を PDF と同様に扱うため）。"""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    lines = []
    for sheet in sheet_names:
        if sheet not in wb.sheetnames:
            continue
        ws = wb[sheet]
        for row in ws.iter_rows():
            cells = [c.value for c in row if c.value is not None]
            if cells:
                lines.append(" ".join(str(c).replace("\n", " ") for c in cells))
    return lines


# ---------------------------------------------------------------- 年度

ERA_BASE = {"H": 1988, "R": 2018, "S": 1925}  # 平成N=1988+N, 令和N=2018+N, 昭和N=1925+N
ERA_NAME = {"H": "平成", "R": "令和", "S": "昭和"}
ERA_KANJI = {"平成": "H", "令和": "R", "昭和": "S"}

YEAR_IN_CONTENT_RE = re.compile(r"(平成|令和|昭和)\s*(元|\d+)\s*年\s*度")


def _year_tuple(era_kanji_or_code: str, n_str: str):
    n = 1 if n_str == "元" else int(n_str)
    era = ERA_KANJI.get(era_kanji_or_code, era_kanji_or_code)
    wareki = f"{ERA_NAME[era]}{'元' if n == 1 else n}年度"
    return ERA_BASE[era] + n, wareki, era, n


def year_from_content(lines):
    for ln in lines[:15]:
        m = YEAR_IN_CONTENT_RE.search(z2h(ln))
        if m:
            return _year_tuple(m.group(1), m.group(2))
    return None


# ---------------------------------------------------------------- ラベル起点の数値抽出
# 財政状況資料集は「ラベル [空白のみ] 数値1 [空白のみ] 数値2 …」の並びで、旧来の
# 決算カードのようなＡ・Ｂ・Ｃ等の識別記号を持たない。ラベル直後に空白だけを挟んで
# 数値が続く場合のみ採用することで、「地方税の状況」のような見出しへの誤爆を避ける。

def label_nums(lines, label, n=2):
    """`label` の後ろに続く（空白のみを挟んだ）数値を最大n個、最初の出現から返す。
    数値が1つも続かない出現（見出し等）はスキップして次の出現を探す。
    ラベル自体の文字間に幅の広いカーニング空白が入る年度（例: H23の「歳 入総額」）
    にも対応するため、ラベルの各文字の間に \\s* を許容する。"""
    tok = re.compile(r"[△▲\-−]?\d[\d,]*(?:\.\d+)?")
    label_pat = r"\s*".join(re.escape(c) for c in label)
    pat = re.compile(label_pat + r"[ \t]*((?:" + tok.pattern + r"[ \t]*){1,%d})" % n)
    for ln in lines:
        m = pat.search(ln)
        if not m:
            continue
        vals = [parse_num(s, d) for s, d in NUM_RE.findall(m.group(1))]
        if vals:
            return vals
    return None


def label_num(lines, label):
    vals = label_nums(lines, label, n=1)
    return vals[0] if vals else None


def label_nums_next_line(lines, label, n=2, min_digits=4):
    """label_numsのフォールバック。年度によってはpdftotext -layoutの列位置
    推定が乱れ、ラベルとその数値が1行分ずれる（例: H25・H26の「歳入総額」で、
    ラベルは表題行の末尾に、実際の数値は次の行の途中に出現する）。
    ラベルを含む行の「次の行」から、桁数がmin_digits以上の数値を探す
    （分類コード「Ⅱ－０」等の小さい数値を誤って拾わないため、財政の千円単位の
    合計額は必ず4桁以上になることを利用してフィルタする）。"""
    label_pat = r"\s*".join(re.escape(c) for c in label)
    lab_re = re.compile(label_pat)
    for i in range(len(lines) - 1):
        if not lab_re.search(lines[i]):
            continue
        found = []
        for s, d in NUM_RE.findall(lines[i + 1]):
            if len(d.replace(",", "")) >= min_digits:
                found.append(parse_num(s, d))
                if len(found) >= n:
                    break
        if found:
            return found
    return None


def label_num_with_optional_note(lines, label):
    """label_numと同じだが、ラベル直後に「(※6)」のような脚注記号が挟まる
    年度にも対応する（例:「ラスパイレス指数(※6) 107.9 (99.7)」）。
    括弧書きの参考値（(99.7)等）は対象外とし、最初の素の数値のみを採る。"""
    tok = r"[△▲\-−]?\d[\d,]*(?:\.\d+)?"
    label_pat = r"\s*".join(re.escape(c) for c in label)
    pat = re.compile(label_pat + r"(?:[\(（]※?\d+[\)）])?[ \t]*(" + tok + r")")
    for ln in lines:
        m = pat.search(ln)
        if not m:
            continue
        nm = NUM_RE.match(m.group(1))
        if nm:
            return parse_num(nm.group(1), nm.group(2))
    return None


POP_RE = re.compile(r"([令平昭]?)(\d+)\.(\d+)\.(\d+)[\(（]\s*人\s*[\)）]\s*(\d[\d,]*)")


def extract_juki_population(lines, era):
    """住民基本台帳人口: 「◯◯.◯◯.◯◯(人) 数値」の最初の出現を採る
    （財政状況資料集は基準日1つのみを掲載する様式）。"""
    for ln in lines[:80]:
        m = POP_RE.search(ln)
        if not m:
            continue
        kanji, y, mo, d, val = m.groups()
        era_name = {"令": "令和", "平": "平成", "昭": "昭和"}.get(kanji, ERA_NAME[era])
        basis = f"{era_name}{y}.{mo}.{d}"
        return parse_num("", val), basis
    return None, None


# ---------------------------------------------------------------- 様式別パーサー

ZAISEI_TITLE_RE = re.compile(r"財政状況資料集")
ICHIRAN_TITLE_RE = re.compile(r"財政状況等一覧表")


def parse_zaisei(page1_lines, full_lines, era, n):
    """財政状況資料集（総括表＋普通会計の状況）。ページ2以降が無い年度（H24）は
    地方税・性質別歳出が自動的に空欄になる（該当ラベルが見つからないため）。

    総括表の項目（財政力指数・実質収支比率・経常収支比率・実質公債費比率・
    将来負担比率・歳入総額等・地方債現在高・積立金・住基人口）は必ず1ページ目
    だけで探す。敵対的校閲で判明: 全文検索だと、将来負担比率が「－」（該当なし）
    の年度に、後続ページの「類似団体内平均値」等の無関係な数値を誤って
    採用してしまうことがあった（H28・H29で発生）。地方税・人件費等の性質別
    歳出は2ページ目「普通会計の状況」にしかないため、そちらはfull_linesを使う。"""
    row = {}
    pop, basis = extract_juki_population(page1_lines, era)
    row["住基人口"] = pop
    row["住基人口_基準日"] = basis

    def first(label):
        v = label_nums(page1_lines, label, n=2)
        return v[0] if v else None

    # 歳入総額のみ、ラベルと数値が1行ずれるレイアウト崩れが起きる年度がある
    # （H25・H26。敵対的校閲で発見）。他の項目（特に将来負担比率のように
    # 「－」＝本当に値が無い年度が普通にある項目）にまでこのフォールバックを
    # 広げると、次の行にある無関係な数値（人口・面積等）を誤って拾ってしまう
    # ため、歳入総額だけに限定して適用する。
    nyuu = first("歳入総額")
    if nyuu is None:
        v = label_nums_next_line(page1_lines, "歳入総額", n=2)
        nyuu = v[0] if v else None
    row["歳入総額A_千円"] = nyuu
    row["歳出総額B_千円"] = first("歳出総額")
    row["歳入歳出差引C_千円"] = first("歳入歳出差引")
    row["翌年度繰越財源D_千円"] = first("翌年度に繰越すべき財源")
    row["実質収支E_千円"] = first("実質収支")
    row["地方税_千円"] = label_num(full_lines, "地方税")
    row["地方債現在高_千円"] = first("地方債現在高")
    row["財政力指数"] = first("財政力指数")
    row["実質収支比率_%"] = first("実質収支比率")
    row["経常収支比率_%"] = first("経常収支比率")
    row["実質公債費比率_%"] = first("実質公債費比率")
    row["将来負担比率_%"] = first("将来負担比率")
    row["人件費_千円"] = label_num(full_lines, "人件費")
    row["扶助費_千円"] = label_num(full_lines, "扶助費")
    row["公債費_千円"] = label_num(full_lines, "公債費")
    row["普通建設事業費_千円"] = label_num(full_lines, "普通建設事業費")

    zaikin = first("財政調整基金")
    gensai = first("減債基金")
    sonota = first("その他特定目的基金")
    row["うち財政調整基金_千円"] = zaikin
    row["積立金現在高_千円"] = (
        zaikin + gensai + sonota if None not in (zaikin, gensai, sonota) else None
    )
    # ラスパイレス指数: 「ラスパイレス指数(※6) 107.9 (99.7)」のように脚注番号が
    # 数値の直前に挟まる年度があるため、ラベル直後に(※N)等の脚注記号が
    # 続くケースを許容してから最初の数値（括弧内の参考値ではない方）を採る。
    row["ラスパイレス指数"] = label_num_with_optional_note(page1_lines, "ラスパイレス指数")
    return row


def parse_ichiran(lines):
    """財政状況等一覧表（H18〜H21、旧・簡易様式）。年度によって内部様式が違う:
    - H18: 「普通会計」合計行（歳入/歳出/形式収支/実質収支/地方債現在高）＋
      「５ 財政指数」節（財政力指数・実質収支比率・実質公債費比率・経常収支比率、
      いずれも当該年度の単一値）。
    - H19〜H21: 合計行のラベルが「一般会計等」に変わる。加えて「６．財政指標の状況」
      節に財政力指数・実質公債費比率・将来負担比率・経常収支比率が「決算A（前年度）
      決算B（当該年度） 差引」の2列（＋差引）で載る（当該年度＝2番目の値）。
      「５．充当可能基金の状況」に財政調整基金・減債基金・その他充当可能基金が
      同じ2列形式で載る（積立金現在高相当）。
    単位は百万円 → 千円に換算するため合計行の値は×1000。財政指標（比率・指数）は
    単位なしなのでそのまま。この様式に無い項目（住基人口・地方税・性質別歳出の
    内訳・ラスパイレス指数等）は空欄のまま。"""
    row = {}
    vals = label_nums(lines, "普通会計", n=6) or label_nums(lines, "一般会計等", n=6)
    if vals and len(vals) >= 5:
        nyu, shutsu, keishiki, jisshitsu, chihosai = vals[:5]
        row["歳入総額A_千円"] = nyu * 1000
        row["歳出総額B_千円"] = shutsu * 1000
        row["歳入歳出差引C_千円"] = keishiki * 1000
        row["実質収支E_千円"] = jisshitsu * 1000
        row["地方債現在高_千円"] = chihosai * 1000

    def current_year_value(label):
        """H18: 単一値（当該年度のみ掲載）→そのまま。
        H19-21: 「決算A(前年度) 決算B(当該年度) 差引」→2番目の値。
        値が1個しか取れない場合、それが「当該年度のみ掲載」（H18方式）なのか
        「当該年度が－で前年度Aだけが残った」ものなのかは行の形からは区別できない
        ため、呼び出し側で個別に判断すること（将来負担比率の特殊処理を参照）。"""
        v = label_nums(lines, label, n=2)
        if not v:
            return None
        return v[1] if len(v) >= 2 else v[0]

    row["財政力指数"] = current_year_value("財政力指数")
    row["実質収支比率_%"] = current_year_value("実質収支比率")  # H18のみ掲載
    row["経常収支比率_%"] = current_year_value("経常収支比率")
    row["実質公債費比率_%"] = current_year_value("実質公債費比率")
    row["将来負担比率_%"] = ichiran_shourai_futan_hiritsu(lines)

    # 「充当可能基金の状況」節は単位が百万円のため×1000して千円に揃える。
    # 個々の基金を合算せず、原本に印字されている「充当可能基金 計」の行を
    # そのまま使う（敵対的校閲で判明: 個別項目の合算は、原本自身が個別項目を
    # 四捨五入した後の値を印字しているため、原本の「計」印字値と食い違うことが
    # あった。例: H19の財政調整基金1,450+減債基金265+その他9,831=11,546だが、
    # 原本の「計」は11,545）。
    zaikin = current_year_value("財政調整基金")
    row["うち財政調整基金_千円"] = zaikin * 1000 if zaikin is not None else None
    kei = current_year_value("充当可能基金計")
    row["積立金現在高_千円"] = kei * 1000 if kei is not None else None
    return row


def ichiran_shourai_futan_hiritsu(lines):
    """将来負担比率（H19-21の「６．財政指標の状況」節のみに掲載）。
    敵対的校閲で判明した2つの誤り:
    - H19（この指標が初めて開示された年度）は前年度Aの列自体が無く、
      行は「決算B(当該年度) 早期健全化基準」の2値になる。早期健全化基準は
      将来負担比率について全国一律350.0%と法令で定められた定数のため、
      2番目の値がちょうど350.0なら、それは基準であって前年度Bではないと
      判断し、1番目の値を当該年度として採る。
    - 当該年度が「－」（発生なし）の年度は、前年度Aの値だけが1個の数値として
      残ってしまい、それを当該年度の値と誤認しやすい（H21で発生）。将来負担
      比率にはH18方式（単一値のみ掲載）のケースが存在しないため、1個しか
      取れない場合は前年度の値が残っているとみなし、空欄にする。"""
    v = label_nums(lines, "将来負担比率", n=2)
    if not v:
        return None
    if len(v) >= 2:
        return v[0] if v[1] == 350.0 else v[1]
    return None


def parse_one(path: str):
    fname = os.path.basename(path)
    ext = os.path.splitext(fname)[1].lower()

    if ext == ".xlsx":
        # シート名だけでは年度が分からないため「総括表」シートの表題セルから拾う。
        # 総括表の項目は「総括表」シート単独（page1相当）で探し、地方税・性質別
        # 歳出は「普通会計の状況」シートを加えたfull_linesで探す（後続ページの
        # 無関係な数値を誤って拾わないため。PDF側と同じ理由）。
        page1_lines = xlsx_to_lines(path, ["総括表"])
        full_lines = page1_lines + xlsx_to_lines(path, ["普通会計の状況"])
        year_info = year_from_content(page1_lines)
        if year_info is None:
            raise RuntimeError("年度を特定できません（総括表シートに令和/平成+年度の表記が見当たらない）")
        seireki, wareki, era, n = year_info
        row = parse_zaisei(page1_lines, full_lines, era, n)
    elif ext == ".pdf":
        pages = pdftotext_pages(path)
        page1_lines = pages[0].splitlines() if pages else []
        full_lines = "\n".join(pages).splitlines()
        year_info = year_from_content(page1_lines)
        if year_info is None:
            raise RuntimeError("年度を特定できません（中身に令和/平成/昭和+年度の表記が見当たらない）")
        seireki, wareki, era, n = year_info
        header = "\n".join(page1_lines[:5])
        if ZAISEI_TITLE_RE.search(header):
            row = parse_zaisei(page1_lines, full_lines, era, n)
        elif ICHIRAN_TITLE_RE.search(header):
            row = parse_ichiran(full_lines)
        else:
            raise RuntimeError(f"未知の様式（表題に「財政状況資料集」「財政状況等一覧表」のいずれも見当たらない）")
    else:
        raise RuntimeError(f"未対応の拡張子: {ext}")

    row = {"年度_西暦": seireki, "年度_和暦": wareki, "出典ファイル": fname, **{c: row.get(c) for c in COLUMNS if c not in ("年度_西暦", "年度_和暦", "出典ファイル")}}
    return row


COLUMNS = [
    "年度_西暦", "年度_和暦", "出典ファイル",
    "住基人口", "住基人口_基準日",
    "歳入総額A_千円", "歳出総額B_千円", "歳入歳出差引C_千円",
    "翌年度繰越財源D_千円", "実質収支E_千円",
    "地方税_千円", "地方債現在高_千円", "積立金現在高_千円", "うち財政調整基金_千円",
    "財政力指数", "実質収支比率_%", "経常収支比率_%",
    "実質公債費比率_%", "将来負担比率_%", "ラスパイレス指数",
    "人件費_千円", "扶助費_千円", "公債費_千円", "普通建設事業費_千円",
]


def main() -> None:
    files = sorted(f for f in os.listdir(RAW_DIR) if f.lower().endswith((".pdf", ".xlsx")))
    if not files:
        print(f"{RAW_DIR} にPDF/xlsxが見つかりません。決算関連資料を置いてから実行してください。")
        return

    rows, problems = [], []
    for f in files:
        try:
            row = parse_one(os.path.join(RAW_DIR, f))
        except Exception as e:
            problems.append(f"{f}: 解析失敗 ({e})")
            row = {"出典ファイル": f, "年度_西暦": None, "年度_和暦": None}
        rows.append(row)

    rows.sort(key=lambda r: (r.get("年度_西暦") is None, r.get("年度_西暦") or 0))

    print("=== 整合チェック（A-B=C, C-D=E） ===")
    for r in rows:
        y = r.get("年度_和暦") or f"?({r.get('出典ファイル')})"
        A, B = r.get("歳入総額A_千円"), r.get("歳出総額B_千円")
        C, D, E = (r.get("歳入歳出差引C_千円"), r.get("翌年度繰越財源D_千円"),
                   r.get("実質収支E_千円"))
        msgs = []
        if None in (A, B, C):
            msgs.append("A/B/C欠損")
        elif A - B != C:
            msgs.append(f"A-B={A-B} != C={C}")
        if None in (C, D, E):
            msgs.append("C/D/E欠損")
        elif C - D != E:
            msgs.append(f"C-D={C-D} != E={E}")
        status = "; ".join(msgs) if msgs else "OK"
        print(f"{y}: {status}")
        if msgs:
            problems.append(f"{y}: {status}")

    print("\n=== 欠損項目 ===")
    for r in rows:
        missing = [c for c in COLUMNS if r.get(c) is None and c != "ラスパイレス指数"]
        if missing:
            print(f"{r.get('年度_和暦') or r.get('出典ファイル')}: {', '.join(missing)}")

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in COLUMNS})
    print(f"\n出力: {OUT_CSV} ({len(rows)}年度)")
    if problems:
        print(f"要確認: {len(problems)}件")
        sys.exit(0)


if __name__ == "__main__":
    main()
