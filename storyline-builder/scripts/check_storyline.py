#!/usr/bin/env python3
"""
check_storyline.py
コンサルティング・スライド骨子（ストーリーライン）の機械検証スクリプト

検証項目:
1. Action Titles（主張タイトル判定）:
   - スライド内「アクションタイトル:」または見出しテキストを抽出
   - 体言止め・ラベル病（「〜の概要」「〜の分析」「〜について」「〜の課題」等）の検知 (FAIL)
   - タイトル文字数の適切性 (WARN: < 15文字 または > 65文字)
   - 述語・主張の有無
2. Headline-Flow（通読性）の抽出と可視化:
   - 全スライドのアクションタイトルのみを順に並べ、ストーリーが一筋に通っているか確認できるように出力
3. 必須構造チェック:
   - 表紙・エグゼクティブサマリの存在
   - 各スライドの構成（型ID / Archetype ID、論拠・ファクト箇条書き、出典/Source）
"""

import sys
import re
import argparse
from pathlib import Path

# 禁止されるトピックタイトル・体言止めの末尾パターン（日本語）
TOPIC_TITLE_SUFFIXES = [
    r'について$',
    r'の概要$',
    r'の現状$',
    r'の分析$',
    r'の課題$',
    r'の背景$',
    r'の検討$',
    r'の比較$',
    r'の提案$',
    r'の計画$',
    r'のロードマップ$',
    r'のまとめ$',
    r'の選定$',
    r'の進捗$',
    r'の経緯$',
    r'の整理$',
    r'の方針$',
    r'の状況$',
    r'の目的$',
    r'の評価$',
    r'の対策$',
    r'のポイント$',
    r'の全体像$',
]

# 単体のトピックラベル（名詞単語のみ）
TOPIC_LABEL_EXACT = [
    '市場動向', '競合分析', '現状課題', '基本方針', '提案概要',
    'システム構成', '体制図', 'スケジュール', 'コスト試算', 'ロードマップ',
    'アジェンダ', 'まとめ', '会社概要', '目次', '背景', '課題', '施策', '効果'
]

def parse_storyline(markdown_text: str):
    """
    ストーリーラインMarkdownを解析し、スライド情報のリストを返す
    """
    slides = []
    lines = markdown_text.splitlines()
    
    current_slide = None
    has_title_slide = False
    has_exec_summary = False
    
    # スライド見出しの正規表現
    # 例: ### [S01] タイトル, ## Slide 1: タイトル, ### 1. タイトル, ### 【S01】 タイトル
    slide_header_pattern = re.compile(
        r'^(?:###?|##)\s*(?:\[?(?:S|Slide|スライド)?\s*(\d+)\]?[:\.\s\-]+|【(?:S|Slide|スライド)?\s*(\d+)】[:\.\s\-]+)?(.*)$',
        re.IGNORECASE
    )
    
    for line_num, line in enumerate(lines, 1):
        line_clean = line.strip()
        
        # 表紙やエグゼクティブサマリの検出
        if re.search(r'表紙|Title Slide|タイトルスライド', line_clean, re.IGNORECASE):
            has_title_slide = True
        if re.search(r'エグゼクティブサマリー|Executive Summary|全体要約', line_clean, re.IGNORECASE):
            has_exec_summary = True
            
        # レベル1見出しはデッキ全体タイトル
        if line_clean.startswith('# '):
            continue
            
        match = slide_header_pattern.match(line_clean)
        if match and line_clean.startswith(('##', '###')):
            num1, num2, header_text = match.groups()
            raw_num = num1 or num2
            header_text = header_text.strip()
            
            if current_slide:
                slides.append(current_slide)
                
            slide_idx = len(slides) + 1
            if raw_num:
                try:
                    slide_idx = int(raw_num)
                except ValueError:
                    pass
                    
            current_slide = {
                'index': slide_idx,
                'line_num': line_num,
                'header': header_text,
                'action_title': None,
                'archetype': None,
                'evidence': [],
                'source': None,
                'raw_content': []
            }
            continue
            
        if current_slide:
            current_slide['raw_content'].append(line)
            
            # `- アクションタイトル:` または `- タイトル:` の検出
            at_match = re.search(r'^[-\*・]\s*(?:アクションタイトル|Action Title|メインメッセージ|メッセージ|主張|タイトル|Title)[\s:：]+(.*)$', line_clean, re.IGNORECASE)
            if at_match and not current_slide['action_title']:
                current_slide['action_title'] = at_match.group(1).strip()
            
            # 型IDの検出 (例: `型ID: b06`, `Archetype: m01`, `型: b26`, `パーツ: b11` 等)
            arch_match = re.search(r'(?:型ID|Archetype|型|パーツ|Layout)[\s:：]+([a-zA-Z0-9_\-]+)', line_clean, re.IGNORECASE)
            if arch_match:
                current_slide['archetype'] = arch_match.group(1).strip()
                
            # 箇条書き（ファクト・論拠）の検出（アクションタイトルや型ID指定行を除く）
            if line_clean.startswith(('-', '*', '・', '1.', '2.', '3.')):
                if not re.search(r'型ID|Archetype|アクションタイトル|Action Title|出典|Source', line_clean, re.IGNORECASE):
                    bullet_text = re.sub(r'^[\-\*・\d\.]+\s*', '', line_clean)
                    if bullet_text:
                        current_slide['evidence'].append(bullet_text)
                    
            # 出典の検出
            if re.search(r'(?:出典|Source|ソース)[\s:：]+', line_clean, re.IGNORECASE):
                current_slide['source'] = line_clean
                
    if current_slide:
        slides.append(current_slide)
        
    # 各スライドの最終有効タイトルを決定（action_titleがあればそれを採用、なければheader）
    for s in slides:
        if s['action_title']:
            s['title'] = s['action_title']
        else:
            s['title'] = s['header']
            
    return {
        'has_title_slide': has_title_slide,
        'has_exec_summary': has_exec_summary,
        'slides': slides
    }

def validate_slide_title(title: str, is_title_page: bool = False):
    """
    スライドタイトルがアクションタイトルになっているか検証する
    """
    issues = []
    
    # 表紙スライド（Title Page）は名詞タイトルで正常
    if is_title_page:
        if len(title) < 5:
            issues.append({
                'level': 'WARN',
                'msg': f'表紙タイトルが短すぎます（{len(title)}文字）。'
            })
        return issues
        
    # 記号プレフィックス除去
    clean_title = re.sub(r'^[【\[\(].*?[】\]\)]\s*', '', title).strip()
    
    # 1. 完全一致のトピックラベル
    if clean_title in TOPIC_LABEL_EXACT:
        issues.append({
            'level': 'FAIL',
            'msg': f'トピックラベル病: 「{clean_title}」は単なる名詞です。結論・主張（メッセージ）を言い切る文にしてください。'
        })
        return issues
        
    # 2. 禁止サフィックス（体言止め）
    for pattern in TOPIC_TITLE_SUFFIXES:
        if re.search(pattern, clean_title):
            issues.append({
                'level': 'FAIL',
                'msg': f'体言止め・トピックタイトル: 「{clean_title}」は主張が書かれていません。「〜により…である」「〜に向けて…を推進する」などの述語で主張を完結させてください。'
            })
            break
            
    # 3. 文字数チェック
    length = len(clean_title)
    if length < 15:
        issues.append({
            'level': 'WARN',
            'msg': f'タイトルが短すぎます（{length}文字）。コンサルのアクションタイトルとして、具体的な根拠や示唆を含めることを推奨します（推奨20〜55文字）。'
        })
    elif length > 65:
        issues.append({
            'level': 'WARN',
            'msg': f'タイトルが長すぎます（{length}文字）。スライド上部で2行以内に収まるよう簡潔に凝縮してください（推奨20〜55文字）。'
        })
        
    # 4. 疑問形チェック
    if clean_title.endswith(('？', '?', 'か。', 'か')):
        issues.append({
            'level': 'WARN',
            'msg': f'疑問形タイトル: 「{clean_title}」。問いかけではなく、分析から導かれた「答え・結論」をタイトルにしてください。'
        })
        
    return issues

def main():
    parser = argparse.ArgumentParser(description="コンサルティング・スライド骨子（ストーリーライン）検証スクリプト")
    parser.add_argument("file", help="検証対象のストーリーラインMarkdownファイルパス")
    parser.add_argument("--strict", action="store_true", help="警告（WARN）もエラー扱いにする")
    args = parser.parse_args()
    
    path = Path(args.file)
    if not path.exists():
        print(f"Error: ファイルが見つかりません: {path}", file=sys.stderr)
        sys.exit(1)
        
    text = path.read_text(encoding="utf-8")
    parsed = parse_storyline(text)
    
    print("=" * 70)
    print(f" 📊 Consulting Storyline Verification: {path.name}")
    print("=" * 70)
    
    fail_count = 0
    warn_count = 0
    
    # 必須スライドチェック
    if not parsed['has_title_slide']:
        print("  [WARN] 表紙スライド（Title Slide）の定義が見当たりません。")
        warn_count += 1
    if not parsed['has_exec_summary']:
        print("  [WARN] エグゼクティブサマリー（Executive Summary / 全体要約）が見当たりません。")
        warn_count += 1
        
    slides = parsed['slides']
    if not slides:
        print("  [FAIL] スライド見出し（### [S01] など）が1つも検出されませんでした。")
        sys.exit(1)
        
    print(f"\n【検出されたスライド数】: {len(slides)} 枚\n")
    
    # Headline-Flow の表示
    print("-" * 70)
    print(" 📖 Headline-Flow Test（タイトル通読テスト）")
    print(" タイトルだけを上から順に読んでストーリーが一筋に通っているか確認してください:")
    print("-" * 70)
    for s in slides:
        arch_tag = f"[{s['archetype']}] " if s['archetype'] else ""
        print(f" [S{s['index']:02d}] {arch_tag}{s['title']}")
    print("-" * 70 + "\n")
    
    # 各スライドの詳細チェック
    print("【スライド個別検証】")
    for s in slides:
        slide_prefix = f"[S{s['index']:02d} (L.{s['line_num']})]"
        is_title_page = bool(s['archetype'] in ('b01', 'title_page') or s['index'] == 1)
        issues = validate_slide_title(s['title'], is_title_page=is_title_page)
        
        # 型IDチェック
        if not s['archetype']:
            issues.append({
                'level': 'WARN',
                'msg': '型ID（Archetype / 62型カタログ番号: 例 b06, b26, m10 等）が未指定です。スライド化時にレイアウト迷いが生じます。'
            })
            
        # エビデンス箇条書きチェック（表紙以外）
        if not is_title_page and len(s['evidence']) < 2:
            issues.append({
                'level': 'WARN',
                'msg': f'ファクト/論拠の箇条書きが少なすぎます（{len(s["evidence"])}件）。スライドのボディを支える論拠を2〜4点記述してください。'
            })
            
        if not issues:
            print(f"  ✓ {slide_prefix} {s['title']}")
        else:
            print(f"  {slide_prefix} {s['title']}")
            for issue in issues:
                lvl = issue['level']
                if lvl == 'FAIL':
                    fail_count += 1
                    print(f"    ❌ [{lvl}] {issue['msg']}")
                else:
                    warn_count += 1
                    print(f"    ⚠️  [{lvl}] {issue['msg']}")
                    
    print("\n" + "=" * 70)
    print(f" 検証結果サマリ: FAIL: {fail_count} 件, WARN: {warn_count} 件")
    print("=" * 70)
    
    if fail_count > 0:
        print("\n❌ 判定: FAIL - トピックタイトル病や体言止めを修正してください。")
        sys.exit(1)
    elif warn_count > 0 and args.strict:
        print("\n❌ 判定: FAIL (Strict mode) - 警告項目を解消してください。")
        sys.exit(1)
    else:
        print("\n✅ 判定: PASS - ストーリーラインの品質基準を満たしています。")
        sys.exit(0)

if __name__ == "__main__":
    main()
