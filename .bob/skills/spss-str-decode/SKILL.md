---
name: spss-str-decode
description: SPSS Modeler のストリームファイル（.str、バイナリ）が与えられた・@メンションされた・パスが示された、または「このストリームは何をしている？」「中身/ノード構成/データフローを説明して」と聞かれたときに使うスキル。.str を read_file で読まず、同梱ツール strcodec（.bob\strcodec\strcodec.cmd decode。Python の追加インストール不要）でデコードした要約 <名前>.strcode/summary.md と正規化 Jython stream.py を読んで解説する。修正・再現・.str の再生成が必要なら spss-str-rebuild に引き継ぐ。
---

# spss-str-decode — .str を読んで解説する

`.str` と `.nod` は **バイナリ**。`read_file` しても意味のあるテキストは得られない（hook がブロックする）。
代わりに strcodec がデコードした成果物を読む。

## 成果物の場所（`.str` と同じフォルダの `<名前>.strcode/`）

| ファイル | 用途 |
|---|---|
| `summary.md` | ノード一覧・データフロー図・入出力パス・モデル・CLEM 式の要約。**まずこれを読む**（hook が自動注入している場合はすでにコンテキストにある） |
| `stream.py` | 正規化した Jython（ノードごとのブロック、末尾に links）。詳細設定はここを**必要なブロックだけ**読む |
| `structure.json` | 機械可読（id / kind / 座標 / 変更済みプロパティ名 / pred・succ） |
| `nuggets/*.nod`, `supernodes/*.nod` | モデルナゲット・スーパーノードの実体（バイナリ。読まない） |
| `supernodes/<var>/stream.py` | スーパーノード内部の正規化コード（閲覧用） |

技術的背景・変換ルール・エラー表は [../_shared/strcodec-reference.md](../_shared/strcodec-reference.md) を参照。

## 手順

<Steps>

<Step>
**1. デコード済みか確認する**

- `<名前>.strcode/summary.md` があり、かつ `.str` より新しければそのまま使う（strcodec は sha256 で鮮度管理するので、迷ったら次のコマンドを実行してよい。キャッシュ済みなら即時に返る）。
- 無い／古い場合は `execute_command` で:

```
.bob\strcodec\strcodec.cmd decode "<path/to/file.str>"
```

launcher（`strcodec.cmd`）が CPython 3.10 以上を自動選択する（通常は PATH の Python = spss-clemb-mcp と同じもの。無ければ SPSS Modeler 18.5 以上に同梱の CPython にフォールバック。`python .bob/strcodec/strcodec.py decode ...` でも同じ）。初回は clemb.exe の起動込みで 15〜25 秒かかる。標準出力に summary.md の内容が出る。失敗時は `.bob/strcodec/logs/strcodec.log` と `<名前>.strcode/_extract.log` を確認し、Python が見つからないと言われたら `.bob\strcodec\strcodec.cmd python-info` で候補を確認する。
</Step>

<Step>
**2. summary.md を読む**

- 先頭行: ノード数 / リンク数 / ナゲット / スーパーノード / パラメータ数
- 「ノード一覧」はデータフロー順。`kind` = source / process / terminal / builder / applier(=ナゲット) / supernode / opaque(未知ノード型)
- 「データフロー」の ASCII ツリーで分岐・合流を把握する
- 「入出力パス」の `NOT FOUND` は、このマシンにデータが無いだけで**ストリームの欠陥ではない**
</Step>

<Step>
**3. 必要なノードだけ stream.py を読む**

`# ---- <var> | <type> | "<label>" | @(x, y) | <kind>` で始まるブロック単位で読む（`grep -n "# ---- " stream.py` で目次が取れる）。
全文ダンプはしない（数百〜数千行になる）。`type` / `variablefile` の `field_metadata` / `values` / `metadata` は 8 要素配列（[型, ロール, 値モード, 値, 追加, ストレージコード, 欠損, 予備]）。
</Step>

<Step>
**4. 未知のノード型・プロパティは ibm-docs-mcp で裏取りする**

`search_ibm_docs(product_id="spss-modeler", keyword="<type> properties")` → `get_ibm_topic(...)`。推測で意味を書かない。裏取りできなければ「公式ドキュメントに該当なし」と明記する。
</Step>

<Step>
**5. CLEM 式を日本語で言い換える**

`*_expr` / `condition` の式は summary の「CLEM 式 / 条件」にまとまっている。`'フィールド' == 'T' and ...` のような式は「〜かつ〜のとき真」と説明する。意味が取れない関数は ibm-docs-mcp で確認する。
</Step>

<Step>
**6. 解説を提示する**

```markdown
# <名前>.str 解説
## 1. 目的（1〜2 文）
## 2. データフロー図（summary の図を再掲・補足）
## 3. ノード一覧（var / 種別 / 表示名 / 役割）
## 4. 主要ノードの詳細（データソースのパス、型定義、派生式、モデルの目的変数と入力、出力先）
## 5. 特記事項（ナゲットの有無と builder、外部パス依存、スーパーノード、裏取りできなかった項目）
```

「ざっくり」→ 1・2・5 のみ。「特定ノードだけ」→ 該当ブロックのみ。
</Step>

</Steps>

## 禁則

1. 🚫 `.str` / `.nod` を `read_file` する（バイナリ。hook がブロックする）
2. 🚫 `generated_raw.py` を実行可能なコードとして扱う（`null` を含み、そのままでは動かない参考物）
3. 🚫 パスの実在や環境変数（`$CLEO_DEMOS` 等）の解決先を推測して断定する
4. 🚫 ナゲットの内部 ID（`builder_node_id` 等）に意味付けする（Modeler が自動採番する内部参照）
5. 🚫 修正や `.str` の再生成をこのスキルで行う → `spss-str-rebuild` に切り替える

**対象バージョン**: SPSS Modeler 19.0 / Jython 2.7 / Bob IDE（hooks: `.bob/settings.json`）
**姉妹スキル**: `spss-str-rebuild`（再現・修正）
