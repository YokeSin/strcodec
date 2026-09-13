# このワークスペースの AI エージェント向けルール

## SPSS Modeler ストリーム（.str）の扱い

- `.str` と `.nod` は **バイナリ**。`read_file` で読まない（hook がブロックし、代替手順を案内する）。
- `.str` の中身を知りたい／説明したい → skill **`spss-str-decode`**（`.bob\strcodec\strcodec.cmd decode "<file.str>"` → `<名前>.strcode/summary.md`, `stream.py`）。プロンプトで `.str` に触れると hook が summary を自動注入する。
- `.str` を再現・修正・作り直したい → skill **`spss-str-rebuild`**（stream.py を編集 → `strcodec.cmd rebuild` → spss-clemb-mcp で実行 → `report` / `verify`）。
- Jython の実行は **spss-clemb-mcp**（`execute_clemb`）、ノード型・プロパティ・CLEM の裏取りは **ibm-docs-mcp**。推測で API を書かない。
- 技術背景・変換ルール・エラー対処: `.bob/skills/_shared/strcodec-reference.md`。全体の説明書（人間向け）: `docs/strcodec-manual.md`。

## strcodec の起動方法（Python の追加インストール不要）

- CLI は必ず launcher `.bob\strcodec\strcodec.cmd <command>` で起動する。launcher が CPython 3.10 以上を自動選択する（優先順: `STRCODEC_PYTHON` 環境変数 → `.bob/strcodec/python.path` → `py -3` → PATH の `python` → フォールバックとして SPSS Modeler 18.5+ 同梱の `<Modeler>\python\python.exe`（最新版優先））。spss-clemb-mcp と同じ Python が使われるのが通常。
- ローカル処理（CLI・hooks・変換・要約）はこの CPython、Modeler 内部処理（抽出・再構築の Jython）は `clemb.exe` の Jython 2.7。両者を混同しない。`modeler.script` や `JythonGenerator` は CPython 側から import できない。
- IBM 同梱 Python に `pip install` しない。`C:\Program Files\IBM\...` 配下に書き込まない。strcodec は標準ライブラリだけで動く。
- どの Python が使われているかは `.bob\strcodec\strcodec.cmd status` / `python-info` で確認できる。

## 生成物の置き場所

- デコード成果物は `.str` と同じフォルダの `<名前>.strcode/`（再デコードで作り直される派生物）。
- 再構築した `.str` は既定で `<名前>_rebuilt.str`。元ファイルは上書きしない。

## clemb で走らせる Jython の書式

- エンコーディング宣言（`# -*- coding: utf-8 -*-`）を書かない（clemb で SyntaxError）。
- 日本語文字列は `u"..."`、`null` ではなく `None`、`except E, e:` 形式、Java オブジェクト（ModelOutput 等）を print しない。
