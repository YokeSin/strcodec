---
name: spss-str-rebuild
description: デコード済みの SPSS Modeler ストリーム（<名前>.strcode/stream.py）から、元ストリームを再現する自己完結 Jython スクリプトを生成し、spss-clemb-mcp（execute_clemb）で実行して .str を作り直すスキル。「ストリームを再現/復元/作り直して」「stream.py を修正して .str に反映して」「再現用の Jython スクリプトが欲しい」「ノードを追加/変更/削除して保存して」に使う。モデルナゲットは .nod 移植（既定）または --retrain で再学習し、report / verify で構造を検証する。
---

# spss-str-rebuild — stream.py から .str を再現する

JythonGenerator の生出力はそのままでは動かない（`null`、JVM 64KB メソッド制限、ナゲット非再現、内部 ID、データパス）。
strcodec の `rebuild` がそれらを吸収した **自己完結の Jython スクリプト**を生成するので、エージェントは
**stream.py の編集 → rebuild → MCP で実行 → report/verify** だけを行う。変換ルールの根拠は
[../_shared/strcodec-reference.md](../_shared/strcodec-reference.md)。

## stream.py の編集規約（守らないと rebuild が失敗する）

- 1 文 1 行。文字列は `u"..."`。`None` を使う（`null` 禁止）。エンコーディング宣言を書かない。
- `stream` は rebuild スクリプトが新規作成して束縛する変数。`modeler.script.stream()` を書かない。
- ノード追加: `v = stream.createAt("<type>", u"<label>", X, Y)` + `v.setPropertyValue(...)`、末尾の `# ---- links ----` に `stream.link(a, v)` を追加する。
- ノード削除: そのブロックと、そのノードが関わる `stream.link(...)` をすべて消す。
- ナゲット行 `var = NUGGET("applyxxx", u"label", x, y, nod=u"nuggets/var.nod", builder="c50_node1", input="type_node2")` は**マーカー**。消さない・createAt に書き換えない。引数（座標・label）だけ編集可。
  - ナゲットの**上流や builder の設定を変えた**場合は、そのモデルは古くなるので `--retrain` で再学習する。
- `SUPERNODE(...)` / `OPAQUE(...)` も同様のマーカー（.nod から丸ごと移植。内部編集は本バージョン非対応）。
- `# internal ids (not restored)` のコメントは復元しない（Modeler が自動採番する）。
- `use_custom_name=False` のような補助行は「元ストリームで表示名が自動生成だった」印。消すと表示名が変わる。
- 新しいノード型・プロパティ名・値は ibm-docs-mcp で裏取りしてから書く。

## 手順

<Steps>

<Step>
**1. デコード済みを確認する**

`<名前>.strcode/stream.py` が無ければ `.bob\strcodec\strcodec.cmd decode "<file.str>"`（spss-str-decode 参照。launcher が Modeler 同梱の CPython を自動選択するので Python の追加インストールは不要）。
編集前に summary.md で構成を把握する。
</Step>

<Step>
**2. 必要なら stream.py を編集する**

上記規約に従い `apply_diff` 等で編集。再現のみが目的なら編集不要。
</Step>

<Step>
**3. rebuild スクリプトを生成する**

```
.bob\strcodec\strcodec.cmd rebuild "<file.str>" [--out "<new.str>"] [--retrain] [--map "OLD=NEW"] [--no-validate]
```

- 出力先の既定は `<名前>_rebuilt.str`（元ファイルは絶対に上書きしない）
- `--map OLD=NEW`: データパスの接頭辞置換（環境が変わったとき）。summary の「入出力パス」に `NOT FOUND` があれば検討する
- `--retrain`: ナゲットを builder の再実行で作り直す（データが実環境に必要）
- `--coding-header`: Modeler GUI から実行する場合のみ（clemb では自動で除去される）

生成物: `<名前>.strcode/rebuild/<名前>_rebuild.py`。コマンドの出力に **execute_clemb に渡す引数**が表示される。
</Step>

<Step>
**4. spss-clemb-mcp で実行する**

```
execute_clemb(
  script_file       = "<abs>/<名前>.strcode/rebuild/<名前>_rebuild.py",
  working_directory = "<abs>/<名前>.strcode",
  log_file          = "<abs>/<名前>.strcode/rebuild/<名前>_rebuild.log"
)
```

成功すると出力末尾に `===STRCODEC_REBUILD=== {"saved": true, "nodes": N, "links": M, "fails": F, ...}` が出る。
`saved: true` が無ければ失敗。ログ末尾の例外を読む（対処表はリファレンス §エラー）。
</Step>

<Step>
**5. レポートと構造比較で検証する**

```
.bob\strcodec\strcodec.cmd report "<file.str>"
.bob\strcodec\strcodec.cmd verify "<file.str>" "<name>_rebuilt.str"
```

- report: ノード/リンク数（期待値との差）、setter 失敗（既知の無害な `values=[None,None]` 拒否は別枠）、パス警告、検証（各データソースと各ナゲットに一時 table を接続して実行）
- report の `STATUS` が `OK` / `OK WITH WARNINGS` 以外なら未完了（exit 1）。件数不一致が意図した追加/削除によるものなら `--allow-issues`
- verify: `RESULT: STRUCTURE_MATCH` は構造（型・ラベル・座標・リンク）の一致だけを意味する。続く `properties:` 行でプロパティ値とストリーム設定の差を確認し、意図した変更以外の差（`metadata` 系のデータ由来の値を除く）が無いことを確認する
- 「保存はされたが validation が失敗」は、多くの場合データファイルがこのマシンに無いことが原因（`--map` か、データ配置で解決）
</Step>

<Step>
**6. 納品する**

- 生成した `.str` のパス、rebuild スクリプトのパス（GUI でも実行可能: ツール > スタンドアロン・スクリプト）、report の要点、verify の結果
- ナゲットが移植か再学習か、パス置換の有無、既知の無害な失敗の件数
</Step>

</Steps>

## 禁則

1. 🚫 元の `.str` を上書きする（`--out` に元パスを指定しない）
2. 🚫 rebuild スクリプト（生成物）を手で直す → stream.py を直して再生成する
3. 🚫 `NUGGET(...)` を `stream.createAt("applyxxx", ...)` に書き換える（空のナゲットになり実行時に NullPointerException）
4. 🚫 内部 ID（builder_node_id 等）を setPropertyValue で復元する
5. 🚫 `saved: true` と report を確認せずに完了扱いにする
6. 🚫 生成した Jython に `# -*- coding` を足す（clemb で SyntaxError）

**対象バージョン**: SPSS Modeler 19.0 / Jython 2.7
**姉妹スキル**: `spss-str-decode`
