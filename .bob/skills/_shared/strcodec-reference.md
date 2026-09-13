# strcodec リファレンス（.str ⇄ Jython の技術背景）

`spss-str-decode` / `spss-str-rebuild` の共通資料。ツール本体は `.bob/strcodec/`（CPython 3.10+、標準ライブラリのみ）。
clemb.exe（SPSS Modeler 19.0 バッチ）を直接呼び出す。設定は `.bob/strcodec/config.json`。

## 0. 起動入口と 2 種類の Python

| 区分 | 実体 | 用途 |
|---|---|---|
| ローカル処理 | CPython 3.10 以上（launcher `strcodec.cmd` が選ぶ。Python の追加インストール不要） | CLI、hooks、解析・変換・要約・レポート・verify・テスト |
| Modeler 内部処理 | Modeler の Jython 2.7（`clemb.exe` / GUI） | 抽出（`jython/extract_stream.py`）と再構築スクリプトの実行。`modeler.script`、`JythonGenerator` はここでしか使えない |

launcher の解決順（先に見つかり、かつ「CPython で 3.10 以上、`-I -S -B -X utf8` で起動できる」ものを採用）:
1. 環境変数 `STRCODEC_PYTHON`（python.exe のフルパス）
2. `.bob/strcodec/python.path`（1 行目 = python.exe のパス。`#` 行は無視）
3. `py -3` → 4. PATH の `python`（通常はここで決まる。spss-clemb-mcp と同じ Python）
5. フォールバック: `SPSS_MODELER_CLEMB_PATH`（spss-clemb-mcp の変数）から `<Modeler>\python\python.exe`
6. フォールバック: `<ProgramW6432 | ProgramFiles | ProgramFiles(x86)>\IBM\SPSS\{Modeler,ModelerServer}\<版>\python\python.exe` を新しい版から順に（版番号は固定しない。18.5 以上に同梱。実機検証は 19.0 の CPython 3.10.7）

確認: `.bob\strcodec\strcodec.cmd python-info`（候補と判定）、`status`（使用中の Python・clemb）。IBM 同梱 Python へ `pip install` したり `Program Files` 配下へ書き込んだりはしない。

## 1. 全体像

```
file.str ──decode──▶ file.strcode/{summary.md, stream.py, structure.json, nuggets/*.nod, supernodes/*.nod, meta.json}
                              │ (エージェントが stream.py を読む/編集する)
                              ▼
                     rebuild ──▶ file.strcode/rebuild/file_rebuild.py ──execute_clemb──▶ file_rebuilt.str
                                                                          └─ report / verify
```

- decode: clemb 内で `JythonGenerator.generateStreamFragment()`（Modeler 内部 API）を呼び、ノードを (x, y, id) でソートして決定的な変数名にする。同時に applier / supernode / unknown ノードを `taskrunner.saveNodeToFile()` で `.nod` に保存する。
- normalize: `modeler.script.stream()`→`stream`、`null`→`None`（トークン単位。文字列内は不変）、ノード単位ブロック、ナゲット等をマーカー関数に置換、リンクをトポロジカル順に整列。
- rebuild: `ast` で文を切り出し、setter を `_sp/_skp`（例外を記録して続行）に、4,000 文字超の文を JSON 経由（`_J(u"...")`）に、全体を 40 文ごとの `build_part_NNN()` に分割。ナゲットは通常ノードとリンクの後で `insertNodeFromFile`（既定）または `builder.run()`→`createModelApplierAt()`（`--retrain`）。最後に検証・`saveStreamToFile`・結果 JSON。

## 2. 実機で確認済みの事実（SPSS Modeler 19.0, clemb.exe）

| # | 事実 | 影響 |
|---|---|---|
| 1 | clemb の起動オーバーヘッドは約 14 秒。生成自体は 12 ノードで 58 ms | decode/rebuild は 1 回 15〜25 秒。キャッシュ（sha256）で 2 回目以降は即時 |
| 2 | `# -*- coding: utf-8 -*-` があるスクリプトは clemb で `SyntaxError: encoding declaration in Unicode string` | 生成物に宣言を書かない（GUI 用に `--coding-header` あり。clemb 実行時は自動除去） |
| 3 | standalone 実行でも `modeler.script.stream()` は空の DefaultStream を返す | rebuild は `taskrunner.createStream(name, True, True)` で新規作成（GUI と両立） |
| 4 | `saveNodeToFile(applier, "x.nod")` → `insertNodeFromFile("x.nod", stream)` でナゲットを移植でき、リンク後にスコアリングが成功する | ナゲットは再学習不要・データ不要で完全再現。保存先ディレクトリは事前に作る必要がある |
| 5 | `generateStreamFragment` はスーパーノードの中身を出さない（`createAt("process_super", ...)` のみ） | `.nod` 移植で中身ごと再現。内側は `getChildDiagram()` で別途デコード（閲覧用） |
| 6 | `setPropertyValue("custom_name", ...)` は `use_custom_name` を自動で True にする（`model_name`/`use_model_name` も同様） | 元で未設定なら normalize が `use_custom_name=False` を補い、表示名を一致させる |
| 7 | builder を `run()` すると Modeler がナゲットをストリームへ自動挿入する | `--retrain` では実行前後の差分 applier を削除してから `createModelApplierAt()` |
| 8 | Range フィールドの `values=[null, null]` は一部で `InvalidPropertyException` | 失敗は記録して続行（既知・無害）。一律削除・変換はしない |
| 9 | `node.getName()` は引数必須で失敗する | `getLabel()` / `getTypeName()` / `custom_name` を使う |
| 10 | `print(ModelOutput)` は `Cannot create PyString with non-byte value` | 結果オブジェクトは print しない（件数のみ） |
| 11 | 巨大リテラル（例: `metadata_all` 19 フィールドで 9.7KB/行）は増えると単文でも 64KB 制限に当たり得る | 4,000 文字超は `json.loads` 経由 |
| 12 | Modeler 19.0 同梱の CPython 3.10.7（`<Modeler>\python\python.exe`）は `-I -S -B -X utf8` で起動でき、strcodec に必要な標準ライブラリ（ctypes/json/tokenize/ast/dataclasses/subprocess 等）を持つ | PATH に Python が無いときの launcher のフォールバック候補。Jython ではないので `modeler.script` は import できない |
| 13 | CPython 3.10 の `ast.get_source_segment()` は呼ぶたびに全文を 1 文字ずつ走査する（12 ノードで 4,099 回 → 約 90 秒） | `transform.SourceSegmentCache` で行分割と UTF-8 化をビルドごとに 1 回にし、約 1 秒に短縮（出力は byte 単位で同一） |

## 3. stream.py の構造

```python
# ---- variablefile_node1 | variablefile | "BASKETS1n" | @(78, 67) | source
# original id: id1CLJJIEFHV2
variablefile_node1 = stream.createAt("variablefile", u"\"variable\" file", 78, 67)
variablefile_node1.setPropertyValue("full_filename", u"$CLEO_DEMOS/japanese_ja/BASKETS1n")
variablefile_node1.setKeyedPropertyValue("values", u"年収", [None, None])
variablefile_node1.setPropertyValue("use_custom_name", False)  # flag was not set in the original: keep the automatic label

# ---- applyc50_node1 | applyc50 | "beer_beans_pizza" | @(738, 262) | applier
applyc50_node1 = NUGGET("applyc50", u"beer_beans_pizza", 738, 262, nod=u"nuggets/applyc50_node1.nod", builder="c50_node1", input="type_node2")
# internal ids (not restored; Modeler regenerates them): updating_node_id=..., refresh_link_state=..., builder_stream_id=..., builder_node_id=...
applyc50_node1.setPropertyValue("calculate_variable_importance", True)

# ---- links ----
stream.link(variablefile_node1, type_node1)
```

kind: `source` / `process` / `terminal` / `builder`（モデル作成） / `applier`（ナゲット） / `supernode` / `opaque`（未知ノード型: 拡張未導入など） / `connector`（スーパーノード内部の入出力コネクター）。

## 4. CLI

起動は `.bob\strcodec\strcodec.cmd <コマンド>`（Python があれば `python .bob/strcodec/strcodec.py <コマンド>` も可）。

| コマンド | 内容 |
|---|---|
| `--which` | launcher が選ぶ Python を表示（`strcodec.cmd` のみ） |
| `python-info` | 候補の一覧と判定（どれが選ばれ、なぜ他が不採用か） |
| `hook <prompt\|session-start\|guard-read>` | Bob hooks の入口（stdin に JSON） |
| `decode <str> [--force] [--quiet] [--json] [--max-lines N]` | デコードして summary を標準出力。キャッシュ有効なら即時 |
| `rebuild <str\|dir.strcode> [--out X.str] [--retrain] [--map OLD=NEW]... [--no-validate] [--run] [--coding-header] [--allow-stale] [--allow-issues]` | rebuild スクリプト生成（`--run` で clemb 直接実行 + report）。元 `.str` が変わった／ツール版が違う／`.nod` が無いと拒否（`--allow-stale`）。`--run` の exit 0 は STATUS OK / OK WITH WARNINGS のみ（`--allow-issues` で保存済みなら 0）。`--coding-header` は `--run` と併用不可 |
| `report <str\|dir.strcode> [--allow-issues]` | 直近の rebuild 実行結果（`rebuild/<stem>_rebuild_result.json`）から report を生成。exit 0 は STATUS OK / OK WITH WARNINGS のみ |
| `verify <a.str> <b.str> [--force] [--strict]` | 2 つのストリームを（必要ならデコードして）比較。exit 0 = `STRUCTURE_MATCH`（型・ラベル・座標・リンク）。プロパティ値とストリーム設定の差は一覧表示のみ（`--strict` で exit 1）。`STRUCTURE_MATCH` は設定値の一致を保証しない |
| `prewarm [--background] [--max N] [--root DIR]` | ワークスペース内の未デコード `.str` を順にデコード（SessionStart hook が裏で起動） |
| `status [--root DIR]` | 使用中の Python・clemb と、`.str` の一覧・キャッシュ状態 |

rebuild 実行後の出力末尾: `===STRCODEC_REBUILD=== {"saved": true, "nodes": 12, "links": 11, "fails": 3, "warnings": 0, "validation_failed": 0, ...}`

## 5. hooks（`.bob/settings.json`）

| イベント | コマンド（`settings.json`）→ スクリプト | 動作 |
|---|---|---|
| SessionStart | `.bob\strcodec\strcodec.cmd hook session-start` → `hooks/hook_session_start.py` | `.str` の索引をコンテキストに出し、未デコード分を裏で `prewarm`（起動した Python と同じフラグを継承） |
| UserPromptSubmit | `.bob\strcodec\strcodec.cmd hook prompt` → `hooks/hook_prompt.py` | プロンプト内の `.str`（`@/path`、絶対/相対、ファイル名のみ）を検出 → decode（キャッシュ）→ `<spss-stream-context>` で summary を注入。失敗してもプロンプトは止めない |
| PreToolUse `^read_file$` | `.bob\strcodec\strcodec.cmd hook guard-read` → `hooks/hook_guard_read.py` | `.str`/`.nod` の read_file を exit 2 でブロックし、decode への誘導を stderr に出す（`config.guard_read=false` で無効） |

## 6. エラー対処

| 症状 | 原因 | 対処 |
|---|---|---|
| `[strcodec] No usable CPython 3.10+ was found. Tried: ...` | PATH の Python が無いか 3.10 未満で、Modeler 同梱 Python も既定の場所に無い | `.bob\strcodec\strcodec.cmd python-info` で候補を確認し、`STRCODEC_PYTHON` 環境変数か `.bob/strcodec/python.path` に使う python.exe を指定 |
| hook が動かない（Bob 上で何も起きない） | `settings.json` のコマンドが `strcodec.cmd` 経由になっていない、または上記の Python 未検出 | `.bob\strcodec\strcodec.cmd status` を手で実行して確認。`logs/hooks.log` を見る |
| `SyntaxError: encoding declaration in Unicode string` | `# -*- coding` が残っている | 宣言を消す（strcodec の実行経路では自動除去） |
| `AEQMJ0161E 名前 'null' は定義されていません` | 生の generator 出力を実行した | `stream.py`（`None` 化済み）→ rebuild を使う。prelude は `null = None` も定義 |
| `Module or method too large` | 生成コードを 1 関数/モジュールで実行 | rebuild の分割（`chunk_statements` を下げる） |
| `NullPointerException`（applier 接続後） | `createAt("applyxxx")` した空ナゲット | `NUGGET(...)` マーカーを使う（.nod 移植 or `--retrain`） |
| `InvalidPropertyException 値 '[null, null]' は ... 'values'` | Range フィールドの値域未設定 | 既知・無害（report の benign 欄）。無視してよい |
| `getName(): expected 1 args; got 0` | Node.getName() | `getLabel()` を使う |
| `Cannot create PyString with non-byte value` | Java オブジェクトを print | 件数だけ print |
| `insertNodeFromFile failed` / `.nod could not be saved` | `.nod` が無い・壊れている・ディレクトリ未作成 | `decode --force` で再生成。無ければ `--retrain` |
| report の `path not found: ...` | データ/出力パスがこの環境に無い | `--map OLD=NEW` で置換、または `$CLEO_DEMOS` 等の変数はそのまま（Modeler が解決） |
| validation failed だが saved=true | 上流データが無い／ナゲットの入力フィールド不足 | `.str` 自体は保存済み。データを配置するか `--map`、ナゲットは `--retrain` を検討 |
| `stream.py is not parseable` | 編集で Python 3 で解析できない構文 | 1 文 1 行・括弧の対応・`u""` を確認 |

## 7. 制約・注意

- `JythonGenerator` は IBM 非公開 API（Modeler 19.0 の `modeler-base.jar`）。バージョン更新で変わり得る。
- `.strcode/` は再デコードで全て作り直される派生物。stream.py を編集していた場合は `stream.py.bak-<日時>` に退避される。
- スーパーノード内部の編集は非対応（丸ごと移植のみ）。`unknown*` ノードは `.nod` 移植でのみ再現可能。
- 元 `.str` は上書きしない。出力既定 `<名前>_rebuilt.str`。
