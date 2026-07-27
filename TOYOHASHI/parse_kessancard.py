#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_kessancard.py — 豊橋市 決算カードPDF（総務省様式）から財政指標の時系列CSVを作る。

入力 : RAW/kessancard/kessancard_H14.pdf 〜 kessancard_R06.pdf（23年分）
出力 : DATA/kessancard_timeseries.csv
方式 : pdftotext -layout（poppler-utils）を subprocess で呼び、テキストを正規表現で解析。
       ※ CJK非埋め込みフォントのPDF（H14,H16,H22-H27等）は poppler-data パッケージが
         ないと空テキストになる。要 `apt-get install poppler-data`。

方針 :
- ラベルは文字間の空白ゆらぎ（「実 質 公 債費 比率」等）に対応するため、
  各文字の間に \s* を挟んだ正規表現で照合する。
- 取れない値は空欄。推測で埋めない。
- △ は負数。― / − / – は欠損（空欄）扱い。
- 整合チェック: 歳入A - 歳出B = 差引C、C - 翌年度繰越財源D = 実質収支E を全年度で検証し
  結果を標準出力に出す（notesへ転記用）。
"""

import csv
import os
import re
import subprocess
import sys
import unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE, "RAW", "kessancard")
OUT_CSV = os.path.join(BASE, "DATA", "kessancard_timeseries.csv")

# ---------------------------------------------------------------- 基本ユーティリティ

NUM_RE = re.compile(r"(△\s*)?(\d[\d,]*(?:\.\d+)?)")


def z2h(s: str) -> str:
    """全角英数字→半角。"""
    return unicodedata.normalize("NFKC", s)


def label_re(label: str) -> re.Pattern:
    """「積立金現在高」→ 積\s*立\s*金\s*現\s*在\s*高 のような空白許容パターン。"""
    return re.compile(r"\s*".join(re.escape(c) for c in label))


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


# ---------------------------------------------------------------- 年度

ERA_BASE = {"H": 1988, "R": 2018}  # 平成N年 = 1988+N, 令和N年 = 2018+N
ERA_NAME = {"H": "平成", "R": "令和"}


def year_from_filename(fname: str):
    m = re.match(r"kessancard_([HR])(\d+)\.pdf$", fname)
    era, n = m.group(1), int(m.group(2))
    wareki = f"{ERA_NAME[era]}{'元' if n == 1 else n}年度"
    return ERA_BASE[era] + n, wareki, era, n


# ---------------------------------------------------------------- 抽出ロジック

# 決算収支表（前年度・当年度の2列）: 識別記号（Ａ,Ｂ,Ｃ,Ｄ,Ｅ）の後ろの
# 数値のうち [前年度, 当年度, (右段の値)...] の2番目が当年度値。


def extract_summary_row(lines, label, letter):
    """ラベルを含む行（またはその直後2行）で識別文字 letter を探し、
    letter の後ろの数値の2番目（=当年度列）を返す。
    ※ 差引Ｃのようにラベル行と数値行が分かれる年度に対応。"""
    lab = label_re(label)
    for i, ln in enumerate(lines):
        m = lab.search(ln)
        if not m:
            continue
        for j in range(i, min(i + 3, len(lines))):
            seg0 = lines[j][m.end():] if j == i else lines[j]
            pos = seg0.find(letter)
            if pos < 0:
                continue
            seg = seg0[pos + len(letter):]
            vals = [parse_num(s, d) for s, d in NUM_RE.findall(seg)]
            if len(vals) >= 2:
                return vals[1]
            break  # letter は見つかったが2列そろわない → この出現は不採用
    return None


def extract_single(lines, label, unit=None, lookahead=0, pick="first", raw=False):
    """ラベルの後ろの数値を1つ返す。unit='千円' なら「数値 千円」の形のみ採用。
    lookahead>0 ならラベル行の後続行も探す。pick='last' なら同一行内の最後の数値。
    raw=True なら数値文字列をそのまま返す（財政力指数 0.990 の末尾ゼロ保持用）。"""
    lab = label_re(label)
    if unit:
        vpat = re.compile(r"(△\s*)?(\d[\d,]*(?:\.\d+)?)\s*" + re.escape(unit))
    else:
        vpat = NUM_RE
    for i, ln in enumerate(lines):
        m = lab.search(ln)
        if not m:
            continue
        found = vpat.findall(ln[m.end():])
        if found:
            s, d = found[-1] if pick == "last" else found[0]
            return d if raw else parse_num(s, d)
        for j in range(i + 1, min(i + 1 + lookahead, len(lines))):
            found = vpat.findall(lines[j])
            if found:
                s, d = found[0]
                return d if raw else parse_num(s, d)
        return None
    return None


def extract_seishitsu(lines, label):
    """性質別歳出の項目: ラベルにマッチする最初の行のラベル直後の数値=決算額。
    ラベルが別語の一部になっている行（公債費比率・実質公債費比率・うち人件費等）は飛ばす。"""
    lab = label_re(label)
    for ln in lines:
        m = lab.search(ln)
        if not m:
            continue
        compact = re.sub(r"\s", "", ln)
        if any(x in compact for x in
               (label + "比率", "うち" + label, label + "負担")):
            continue
        vals = NUM_RE.findall(ln[m.end():])
        if vals:
            return parse_num(*vals[0])
    return None


def extract_jisshitsu_shushi_hiritsu(lines):
    """実質収支比率。通常はラベル行の右に「N.N ％」。
    H19-H21様式ではラベル行に「％」のみで、数値がラベルの1行上、
    参考値（臨財債除き）が括弧付きで1行下に置かれるため、上下の行も探す。
    「※実質収支比率（ ）は分母に…」の注記行は除外する。"""
    lab = label_re("実質収支比率")
    for i, ln in enumerate(lines):
        m = lab.search(ln)
        if not m:
            continue
        if "※" in ln[:m.start()][-8:]:  # 注記行はスキップ
            continue
        # 同一行のラベル直後
        found = NUM_RE.findall(ln[m.end():])
        if found:
            return parse_num(*found[0])
        # 1行上・1行下のラベル位置以降（括弧付き参考値は除外）
        col = max(0, m.start() - 5)
        for j in (i - 1, i + 1):
            if 0 <= j < len(lines):
                seg = re.sub(r"[(（][^)）]*[)）]", "", lines[j][col:])
                seg = seg.split("※")[0]
                found = NUM_RE.findall(seg)
                if found:
                    return parse_num(*found[0])
        return None
    return None


def extract_keijo_shushi(lines):
    """経常収支比率: ラベル行（表本体の右下）を見つけ、その行〜次の4行で
    最初に現れる「数値 ％」を返す。列見出しの分断語（経常収/支比率）は除外される。"""
    lab = label_re("経常収支比率")
    vpat = re.compile(r"(\d+(?:\.\d+)?)\s*％")
    for i, ln in enumerate(lines):
        m = lab.search(ln)
        if not m:
            continue
        for j in range(i, min(i + 5, len(lines))):
            seg = lines[j][m.end():] if j == i else lines[j]
            v = vpat.search(seg)
            if v:
                return float(v.group(1))
        return None
    return None


def extract_population(lines, era, n):
    """住民基本台帳人口。カード上段の (N)1.1 または (N)3.31 の最初の出現
    （= 年度末時点の新しい方）を採り、数値はラベル行またはその直前2行の「数値 人」。"""
    lab = re.compile(r"[(（](\d+)[)）]\s*(1\.1|3\.31)")
    pnum = re.compile(r"(\d[\d,]*)\s*人")
    for i, ln in enumerate(lines[:40]):
        ln_h = z2h(ln)
        m = lab.search(ln_h)
        if not m:
            continue
        basis = f"{'平成' if era == 'H' else '令和'}{int(m.group(1))}.{m.group(2)}"
        for j in (i, i - 1, i - 2):
            if j < 0:
                continue
            v = pnum.search(lines[j])
            if v:
                return parse_num("", v.group(1)), basis
        return None, basis
    return None, None


def extract_ratio_2col(lines, label):
    """健全化判断比率など（前年度・当年度の2列、初出年は1列）: 最後の数値=当年度。"""
    lab = label_re(label)
    for ln in lines:
        m = lab.search(ln)
        if not m:
            continue
        vals = [parse_num(s, d) for s, d in NUM_RE.findall(ln[m.end():])]
        if vals:
            return vals[-1]
        return None
    return None


def parse_one(pdf_path: str):
    fname = os.path.basename(pdf_path)
    seireki, wareki, era, n = year_from_filename(fname)
    lines = pdftotext(pdf_path)

    row = {"年度_西暦": seireki, "年度_和暦": wareki, "出典ファイル": fname}

    pop, basis = extract_population(lines, era, n)
    row["住基人口"] = pop
    row["住基人口_基準日"] = basis

    row["歳入総額A_千円"] = extract_summary_row(lines, "歳入総額", "Ａ")
    row["歳出総額B_千円"] = extract_summary_row(lines, "歳出総額", "Ｂ")
    row["歳入歳出差引C_千円"] = extract_summary_row(lines, "歳入歳出差引額", "Ｃ")
    row["翌年度繰越財源D_千円"] = extract_summary_row(lines, "翌年度へ繰越すべき財源", "Ｄ")
    row["実質収支E_千円"] = extract_summary_row(lines, "実質収支", "Ｅ")

    # 歳入内訳: 「地方税」で始まる行の最初の数値（決算額）
    chihozei = None
    lab = label_re("地方税")
    for ln in lines:
        compact = re.sub(r"\s", "", ln)
        if compact.startswith("地方税"):
            m = lab.search(ln)
            vals = NUM_RE.findall(ln[m.end():])
            if vals:
                chihozei = parse_num(*vals[0])
                break
    row["地方税_千円"] = chihozei

    row["地方債現在高_千円"] = extract_single(lines, "地方債現在高", unit="千円")
    row["積立金現在高_千円"] = extract_single(lines, "積立金現在高", unit="千円", lookahead=3)
    row["うち財政調整基金_千円"] = extract_single(lines, "うち財調", unit="千円")

    row["財政力指数"] = extract_single(lines, "財政力指数", pick="first", raw=True)
    row["実質収支比率_%"] = extract_jisshitsu_shushi_hiritsu(lines)
    row["経常収支比率_%"] = extract_keijo_shushi(lines)
    row["実質公債費比率_%"] = extract_ratio_2col(lines, "実質公債費比率")
    row["将来負担比率_%"] = extract_ratio_2col(lines, "将来負担比率")
    row["ラスパイレス指数"] = None  # 豊橋市の決算カード様式には記載なし（全年度確認済み）

    row["人件費_千円"] = extract_seishitsu(lines, "人件費")
    row["扶助費_千円"] = extract_seishitsu(lines, "扶助費")
    row["公債費_千円"] = extract_seishitsu(lines, "公債費")
    row["普通建設事業費_千円"] = extract_seishitsu(lines, "普通建設事業費")

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


def main():
    files = sorted(
        f for f in os.listdir(RAW_DIR)
        if re.match(r"kessancard_[HR]\d+\.pdf$", f)
    )
    # 年度順（H→R）に並べる
    files.sort(key=lambda f: year_from_filename(f)[0])

    rows, problems = [], []
    for f in files:
        try:
            row = parse_one(os.path.join(RAW_DIR, f))
        except Exception as e:
            problems.append(f"{f}: 解析失敗 ({e})")
            row = {"出典ファイル": f}
            s, w, _, _ = year_from_filename(f)
            row["年度_西暦"], row["年度_和暦"] = s, w
        rows.append(row)

    # 整合チェック
    print("=== 整合チェック（A-B=C, C-D=E） ===")
    for r in rows:
        y = r.get("年度_和暦", "?")
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

    # 欠損レポート
    print("\n=== 欠損項目 ===")
    for r in rows:
        missing = [c for c in COLUMNS if r.get(c) is None and c != "ラスパイレス指数"]
        if missing:
            print(f"{r.get('年度_和暦')}: {', '.join(missing)}")

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
