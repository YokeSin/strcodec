# strcodec 説明書 — SPSS Modeler `.str` ⇄ Jython コーデック（IBM Bob IDE 用 skills + hooks）

- 版: 2026-09-13（初版 2026-09-12）
- 対象環境: Windows 11 / IBM SPSS Modeler 19.0（`clemb.exe`）/ IBM Bob IDE / Python 3.10 以上（検証は 3.12 と Modeler 同梱の 3.10.7）
- 「ワークスペース」= strcodec を配置した、`.str` を扱うプロジェクトのルート
- 関連資料: `README.md`（導入と日常の使い方）、`JythonGenerator調査レポート.md`、`.bob/skills/_shared/strcodec-reference.md`
- ライセンス: MIT（リポジトリ直下の `LICENSE`）。IBM の成果物は含まない（README「ライセンス」参照）

---

## 目次

0. この文書の読み方
1. 背景と目的 — 何を解決するものか
2. 全体像 — 登場人物とデータの流れ
3. ファイル構成と役割一覧
4. デコード処理の詳細（`.str` → `.strcode/`）
5. 再構築処理の詳細（`stream.py` → 再現スクリプト → `.str`）
6. hooks の詳細（Bob との接続）
7. skills / AGENTS.md の詳細
8. 成果物ファイルの仕様
9. 変換ルールとその根拠（実機検証の結果）
10. 検証結果の記録
11. 設定とカスタマイズ
12. 運用手順（人間向け）
13. トラブルシューティング
14. 制約・既知の問題・今後の拡張
15. 用語集
- 付録 A: 生成物の実例（要約・正規化コード・再現スクリプト・レポート）
- 付録 B: Modeler スクリプト API メモ（今回使ったもの）

---

## 0. この文書の読み方

| 読者 | まず読む節 |
|---|---|
| 「何ができるのか」を 5 分で知りたい | 1, 2, 12 |
| エージェント（Bob）の挙動を理解したい | 2, 6, 7 |
| 中身を改修したい | 3, 4, 5, 8, 9 |
| 動かなくなった | 13 |
| インストールしたい | README の「インストール方法」、12.3 |
| 別プロジェクトに持っていきたい | 11, 12 |

本文中の「エージェント」は Bob IDE 上で動くコーディングエージェントを指します。「ツール」は `.bob/strcodec/` 配下の CPython 製プログラム群（strcodec）を指します。

---

## 1. 背景と目的 — 何を解決するものか

### 1.1 問題

SPSS Modeler のストリームファイル（`.str`）はバイナリ（内部は圧縮 XML）なので、コーディングエージェントはそのまま読めません。`read_file` しても意味のないバイト列が返るだけで、エージェントはストリームの構造（ノード・リンク・設定）を把握できません。

### 1.2 手段: JythonGenerator

Modeler には GUI の「ノードをスクリプトへ貼り付け」機能があり、そのバックエンドが `modeler-base.jar` の `com.spss.clementine.scripting.jython.JythonGenerator` です。`public` ですが IBM ドキュメントに記載のない内部 API で、Modeler の Jython 実行環境（`clemb.exe -script` またはストリームスクリプト）の中でだけ使えます。

`generateStreamFragment(List<Node>)` を呼ぶと、渡したノード群を再構築する Jython コード（`createAt` / `setPropertyValue` / `setKeyedPropertyValue` / `link`）が文字列で返ります。

### 1.3 生成物がそのままでは動かない理由（5 点）

| # | 問題 | 内容 |
|---|---|---|
| 1 | `null` リテラル | リスト要素の Java `null` が Python の `None` ではなく `null` として出る（`[null, null]`）→ NameError |
| 2 | JVM の 64KB メソッド制限 | 生成物全体を 1 モジュールとして実行すると `Module or method too large`。12 ノードの sample でも超過 |
| 3 | モデルナゲット | `createAt("applyc50", ...)` では中身（学習済みモデル）の無い空ノードになり、接続すると `NullPointerException` |
| 4 | 内部 ID プロパティ | `builder_node_id` / `builder_stream_id` / `updating_node_id` / `refresh_link_state` は元ストリーム内部の ID。復元してはいけない |
| 5 | データパス | `full_filename` 等は元環境のパス。実行環境で解決できるとは限らない |

### 1.4 制約とアプローチ

- 使う MCP は 2 つ（`spss-clemb-mcp`: clemb 実行、`ibm-docs-mcp`: IBM ドキュメント検索）で、どちらも改造不可。
- したがって実装は **Bob の skills + lifecycle hooks + 同梱スクリプト**で行い、hooks は MCP を呼べないので **clemb.exe を直接実行**します。
- ノード種別ごとのプロパティ辞書を人手で持つのではなく、JythonGenerator の出力を「薄い変換層」で実行可能にする、という方針です。

### 1.5 ゴール（2 つ）

1. `.str` がプロンプトで言及された／ワークスペースに存在するとき、自動でコード化し、**エージェントが扱いやすい形（要約 + 正規化 Jython）でコンテキストへ投入**する。
2. 必要に応じて、正規化 Jython から **元ストリームを再現できる自己完結の Jython スクリプト**を生成し、実行・検証して `.str` を作り直す。

### 1.6 機能の要約

- **decode**: `.str` → `<名前>.strcode/`（`summary.md`、正規化 `stream.py`、`structure.json`、ナゲット `.nod`、`meta.json`）。sha256 キャッシュで 2 回目以降は即時。
- **rebuild**: `stream.py` → 自己完結の Jython（clemb / MCP / Modeler GUI で実行可）→ `<名前>_rebuilt.str`。元ファイルは上書きしない。
- **report / verify**: 実行結果のレポート（STATUS = `OK` / `OK WITH WARNINGS` / `SAVED WITH ISSUES` / `FAILED`、終了コードに直結）と、元との比較（構造 = `STRUCTURE_MATCH` / `STRUCTURE_DIFFERENT` が終了コード、プロパティ値とストリーム設定の差は一覧表示。`--strict` で値差も失敗扱い）。
- **手元の Python をそのまま使う**: Windows 用 launcher `strcodec.cmd` が PATH 上の CPython 3.10 以上（spss-clemb-mcp と同じもの）を自動選択。無い場合だけ SPSS Modeler 18.5 以上の同梱 CPython にフォールバック（管理者権限・PATH 変更・pip 不要）。
- **Bob IDE 統合**: SessionStart（索引 + 裏で事前デコード）、UserPromptSubmit（要約注入）、PreToolUse（`.str`/`.nod` の `read_file` をブロックして誘導）、skills 2 本、`AGENTS.md`。
- **依存が少ない**: CPython 3.10+ の標準ライブラリのみ。Modeler 側は同梱の Jython テンプレート 2 本。
- **検証済み**: 12 ノードと 28 ノードのストリームで往復（decode → rebuild → verify）が構造一致（ノード・ラベル・座標・リンク・ストリーム設定）。プロパティ値はデータ由来のメタデータ（`metadata` / `field_metadata` / `description`）を除き一致。ユニットテスト 70 件（CPython 3.12 と同梱 3.10.7 で合格。prelude の Jython 側は clemb で実測）。

---

## 2. 全体像 — 登場人物とデータの流れ

### 2.1 アーキテクチャ図

```
                     ┌──────────────────────────── IBM Bob IDE ─────────────────────────────┐
  ユーザー            │  hooks (.bob/settings.json)                 skills / rules            │
  「@sample.str を    │   SessionStart      → hook_session_start.py  spss-str-decode           │
   説明して」         │   UserPromptSubmit  → hook_prompt.py         spss-str-rebuild          │
        │            │   PreToolUse(read_file) → hook_guard_read.py                           │
        ▼            │      stdout ⇒ モデルのコンテキストに注入      AGENTS.md                │
   エージェント ◀─────┴───────────────────────────────────────────────────────────────────────┘
        │ execute_command                                   │ use_mcp_tool
        ▼                                                   ▼
  .bob/strcodec/strcodec.py (CPython)              spss-clemb-mcp / ibm-docs-mcp
    decode │ rebuild │ report │ verify │ prewarm │ status          │
        │  clemb.exe を直接起動（-script <tmp.py> -execute -log）  │ clemb.exe を起動
        ▼                                                          ▼
  ┌────────────────── SPSS Modeler バッチ (Jython 2.7) ──────────────────┐
  │ jython/extract_stream.py   … JythonGenerator + saveNodeToFile + 構造JSON │
  │ rebuild/<stem>_rebuild.py  … createStream + createAt + insertNodeFromFile │
  └──────────────────────────────────────────────────────────────────────┘
        │
        ▼
  <stem>.strcode/  summary.md  stream.py  structure.json  nuggets/*.nod  supernodes/  rebuild/  meta.json
```

### 2.2 流れ 1: 「読む」（decode）

```
.str ─(clemb: extract_stream.py)─▶ generated_raw.py + structure.json + nuggets/*.nod
     ─(transform.normalize)──────▶ stream.py           … エージェントが読む/編集する正本
     ─(summarize.build_summary)──▶ summary.md          … hook がコンテキストに注入する要約
     ─(decode.py)────────────────▶ meta.json, README.md … キャッシュ鍵と統計
```

典型的な体験:
1. ユーザーが Bob で「`@campaign_response.str` を説明して」と入力する。
2. `UserPromptSubmit` hook（`hook_prompt.py`）がプロンプト内の `.str` を検出し、`strcodec decode` を実行（初回 15〜25 秒、以降はキャッシュで即時）。`summary.md` を `<spss-stream-context>` で囲んで stdout に出す。
3. Bob がその stdout をモデルのコンテキストに加える。エージェントは要約を見て解説でき、詳細が必要なら `stream.py` の該当ブロックだけ `read_file` する。
4. エージェントが `.str` 自体を `read_file` しようとすると、`PreToolUse` hook（`hook_guard_read.py`）が exit 2 でブロックし、代替手順を案内する。

### 2.3 流れ 2: 「再現する・直す」（rebuild）

```
stream.py ─(strcodec rebuild)─▶ rebuild/<stem>_rebuild.py（自己完結 Jython）
          ─(spss-clemb-mcp execute_clemb / --run / Modeler GUI)─▶ <stem>_rebuilt.str + rebuild/<stem>_rebuild_result.json
          ─(strcodec report)──▶ rebuild/<stem>_rebuild_report.md
          ─(strcodec verify)──▶ 元 .str と再構築 .str の比較（STRUCTURE_MATCH / DIFFERENT + プロパティ値の差）
```

典型的な体験:
1. ユーザーが「派生フィールドの式を直して `.str` を作り直して」と頼む。
2. エージェント（skill `spss-str-rebuild`）が `stream.py` の該当行を編集し、`strcodec rebuild` でスクリプトを生成する。
3. `spss-clemb-mcp` の `execute_clemb(script_file=..., working_directory=..., log_file=...)` で実行し、末尾の `===STRCODEC_REBUILD=== {...}` を確認する。
4. `strcodec report` でレポート、`strcodec verify` で構造比較を行い、生成した `.str` のパスと結果を報告する。

### 2.4 動作イメージ（Bob 上の会話）

```
ユーザー:   @campaign_response.str を説明して
   ↓ UserPromptSubmit hook が .str を検出 → strcodec decode（初回 ~10 秒、以後即時）
コンテキスト: <spss-stream-context file="samples/campaign_response.str" ...>
             # campaign_response.str — SPSS Modeler stream (8 nodes / 7 links)
             | var | type | label | @(x,y) | kind | key settings |
             | variablefile_node1 | variablefile | 顧客データ | (78,97) | source | full_filename=... |
             ...
             variablefile_node1 "顧客データ"
             └─ derive_node1 "訪問あたり単価"
                └─ derive_node2 "優良顧客"
                   └─ type_node1 "データ型"
                      ├─ c50_node1 "応答予測" [builder]
                      └─ applyc50_node1 "応答予測" [nugget]
             </spss-stream-context>
エージェント: （要約と stream.py を読んで解説）

ユーザー:   会員だけに絞る条件抽出ノードを、データ型の手前に追加して
エージェント: stream.py を編集 → strcodec.cmd rebuild → execute_clemb（spss-clemb-mcp）→ report / verify
             → campaign_response_members.str（9 nodes / 8 links, STATUS: SAVED WITH ISSUES = 意図した増加）

実際の会話と出力は `samples/example-session.md` にそのまま残してあります。
```

### 2.5 登場人物のまとめ

| 名前 | 何者か | 役割 |
|---|---|---|
| Bob IDE | コーディングエージェントの実行環境 | hooks を発火し、skills を読み込み、MCP ツールを提供 |
| hooks（3 本） | Bob のライフサイクルフック（`cmd /c python ...`） | 自動デコード・要約注入・索引・読み取りガード |
| skills（2 本）+ `_shared` | Bob が自動選択する手順書 | エージェントに正しい手順（decode / rebuild）を踏ませる |
| launcher（`strcodec.cmd`） | Windows バッチ | CPython 3.10+ を解決（既定は PATH の Python、無ければ Modeler 同梱版）して `strcodec.py` を隔離フラグ付きで起動。hooks と CLI の共通入口 |
| strcodec（CPython） | 本ツール | clemb の起動、テキスト変換、要約、キャッシュ、レポート、比較 |
| Jython テンプレート（2 本） | clemb 内で走るコード | 抽出（extract）と再構築ランタイム（prelude） |
| clemb.exe | Modeler のバッチ実行体 | Jython を Modeler の API とともに実行 |
| spss-clemb-mcp | MCP | エージェントが Jython を実行するための窓口（再構築スクリプトの実行） |
| ibm-docs-mcp | MCP | ノード型・プロパティ・CLEM の裏取り |

---

## 3. ファイル構成と役割一覧

```
ワークスペース/
├── README.md                                  ← 導入と日常の使い方
├── install-strcodec.ps1                       ← インストール／更新スクリプト（§12.3）
├── AGENTS.md                                  ← エージェント向け案内板（.str を見たら skill を使う等）
├── docs/strcodec-manual.md                    ← 本書
├── .gitignore                                 ← *.strcode/、*_rebuilt.str、ログ、個人設定、*.str / *.nod を除外
├── <name>.str                                 ← 扱うストリーム
├── <name>.strcode/                            ← デコード成果物（§8）
├── <name>_rebuilt.str                         ← 再構築結果（既定のサフィックス）
└── .bob/
    ├── settings.json                          ← hooks 定義（§6）
    ├── mcp.json                               ← MCP 設定（環境ごと。spss-clemb-mcp / ibm-docs-mcp の README を参照）
    ├── skills/
    │   ├── spss-str-decode/SKILL.md           ← 読む・説明するスキル
    │   ├── spss-str-rebuild/SKILL.md          ← 再現・修正するスキル
    │   └── _shared/strcodec-reference.md      ← 両スキル共通の技術リファレンス
    └── strcodec/                              ← ツール本体（CPython、標準ライブラリのみ）
        ├── strcodec.cmd       Windows launcher（CPython 3.10+ の解決と隔離起動。hooks と CLI の共通入口）
        ├── strcodec.py        CLI 入口（decode / rebuild / report / verify / prewarm / status / python-info / hook）
        ├── pyfind.py          Python 解決順の Python 側ミラー（診断 python-info と単体テスト用）
        ├── python.path        （任意・gitignore）使う python.exe を 1 行で指定
        ├── common.py          共通ユーティリティ（設定・ログ・ハッシュ・ファイル探索・detached 起動・分離フラグ継承）
        ├── clemb_runner.py    clemb.exe の探索と実行（一時スクリプト、UTF-8、ログ、センチネル解析）
        ├── decode.py          デコード全体の司令塔（キャッシュ・ロック・掃除・抽出・正規化・要約・meta）
        ├── transform.py       テキスト変換（生成物の解析、stream.py 正規化、再構築スクリプト生成）
        ├── summarize.py       summary.md 生成（ノード表・データフロー図・パス・モデル・CLEM）
        ├── rebuild.py         再構築の司令塔（スクリプト生成・実行・結果 JSON・レポート）
        ├── verify.py          2 つの structure.json の構造比較
        ├── config.json        設定（§11）
        ├── .gitignore         logs/ と __pycache__/ を除外
        ├── jython/
        │   ├── extract_stream.py   clemb 内で実行する抽出テンプレート（Jython 2.7）
        │   └── rebuild_prelude.py  再構築スクリプトに埋め込むランタイム（Jython 2.7）
        ├── hooks/
        │   ├── hook_session_start.py  SessionStart: .str 索引 + 裏で prewarm
        │   ├── hook_prompt.py         UserPromptSubmit: .str 検出 → decode → 要約注入
        │   └── hook_guard_read.py     PreToolUse(read_file): .str/.nod をブロック
        ├── tests/
        │   ├── test_transform.py   変換のユニットテスト（clemb 不要）
        │   ├── test_segments.py    SourceSegmentCache と ast.get_source_segment の互換性、「前処理はビルドごとに 1 回」
        │   ├── test_regression.py  固定フィクスチャとの byte 単位の回帰比較
        │   ├── test_pyfind.py      Python 解決順（偽の Modeler 構成・空白入りパス・バージョン判定）
        │   ├── test_launcher.py    strcodec.cmd と 3 つの hook 入口のスモーク（Windows）
        │   ├── test_hooks.py       hooks のユニットテスト（clemb 不要）
        │   ├── fixture_ctx.py / make_fixtures.py   決定的な入力と回帰フィクスチャの再生成
        │   ├── selftest.py         統合テスト（clemb 必要、decode→rebuild→verify）
        │   └── fixtures/           同梱サンプル campaign_response の生成物、structure.json、期待出力
        └── logs/                   strcodec.log, hooks.log（自動生成）
```

### 3.1 モジュールの依存関係

```
strcodec.py ──▶ decode.py ──▶ clemb_runner.py ──▶ (clemb.exe + jython/extract_stream.py)
            │            ├──▶ transform.py（parse_generated / normalize）
            │            └──▶ summarize.py
            ├──▶ rebuild.py ──▶ transform.py（parse_stream_py / build_rebuild）+ jython/rebuild_prelude.py
            │              └──▶ clemb_runner.py（--run 時）
            ├──▶ verify.py
            └──▶ common.py（全モジュール共通）
hooks/*.py ──▶ common.py, decode.py（hook_prompt のみ decode を呼ぶ）
strcodec.cmd ──▶ (python.exe を解決) ──▶ strcodec.py            pyfind.py は同じ解決順の Python 実装（診断・テスト）
```

### 3.2 起動入口（`strcodec.cmd`）と 2 種類の Python

| 区分 | 実体 | 用途 |
|---|---|---|
| ローカル処理 | CPython 3.10 以上（launcher が選ぶ） | CLI、hooks、AST 解析・変換・要約・レポート・verify・テスト |
| Modeler 内部処理 | Modeler の Jython 2.7（`clemb.exe` / GUI） | 抽出テンプレートと再構築スクリプトの実行。`modeler.script` / `JythonGenerator` はここでしか使えない |

hooks と CLI はすべて `strcodec.cmd` を経由し、どの Python で動くかを一か所で決めます。strcodec が依存する spss-clemb-mcp は Python 3.10+ が既にある前提なので、既定はその Python（`py -3` / PATH）です。Modeler 同梱の CPython は、PATH に使える Python が無いときのフォールバックに降格しています（2026-09-13 に順序を反転。理由: MCP と strcodec で使う Python が分かれると混同の元になり、同梱版の利用は IBM のサポート外でもあるため）。解決順（存在し、かつ「CPython で 3.10 以上、`-I -S -B -X utf8` で起動できる」最初の候補を採用）:

1. 環境変数 `STRCODEC_PYTHON`
2. `.bob/strcodec/python.path`（1 行目、`#` 行は無視）
3. `py -3` 4. PATH の `python`
5. フォールバック: `SPSS_MODELER_CLEMB_PATH` → `<Modeler>\python\python.exe`
6. フォールバック: `<ProgramW6432 | ProgramFiles | ProgramFiles(x86)>\IBM\SPSS\{Modeler,ModelerServer}\<版>\python\python.exe`（`dir /o-n` で新しい版から。製品版番号は固定しない。IBM SPSS Modeler 18.5 以上に同梱）

判定は候補自身を `-c "import sys; ..."` で起動して `sys.implementation.name == 'cpython'` と `sys.version_info >= (3, 10)` を確認する（製品版から推測しない）。採用結果は環境変数 `STRCODEC_PYTHON_SELECTED` / `STRCODEC_PYTHON_SOURCE` で CLI に渡され、`status` の先頭行と `python-info` で確認できる。起動フラグ `-I -S -B -X utf8` は隔離モード（環境変数・ユーザー site を無視）、site 無効、`.pyc` 非書き込み、UTF-8 モード。バックグラウンドの prewarm は `sys.executable` と同じフラグ（`common.python_cmd_prefix()`）を引き継ぐ。

安全要件: 管理者権限不要、PATH・レジストリ・システム環境変数を変更しない、`Program Files` 配下に書かない、同梱 Python に `pip` しない、標準ライブラリのみ。隔離フラグのおかげで、PATH の Python に venv や site-packages が何あっても動作は変わらない。実機検証済みは CPython 3.12（PATH）と Modeler 19.0 同梱の CPython 3.10.7（`C:\Program Files\IBM\SPSS\Modeler\19.0\python\python.exe`）。18.5〜18.x の同梱版は「対応想定」。

`pyfind.py` は同じ順序の Python 実装で、`python-info` の候補一覧と単体テスト（一時ディレクトリに偽の `IBM\SPSS\Modeler\<版>\python\python.exe` を作って順序・バージョン判定・空白入りパスを検証）に使う。バッチと Python の 2 か所に同じ順序があるので、変更時は両方を直す。

---

## 4. デコード処理の詳細（`.str` → `.strcode/`）

入口は `strcodec.py decode <file.str>`。hook（`hook_prompt.py`）、`prewarm`、`verify` も内部で同じ `decode.decode_stream()` を呼びます。

### 4.1 手順（`decode.py`）

| 手順 | 関数 | 内容 |
|---|---|---|
| 1 | `decode_stream()` | パスを絶対化し `.str` であることを確認。成果物ディレクトリ = `<stem>.strcode`（`common.strcode_dir_for`） |
| 2 | `is_cache_valid()` | `meta.json` の `sha256` と `tool_version` が現在の `.str` と一致し、`summary.md` / `stream.py` / `structure.json` と、`structure.json` が参照する全 `.nod` が存在すればキャッシュ利用（clemb を起動しない） |
| 3 | `DirLock` | `.strcode/.lock` を `O_EXCL` で作成。既に存在する場合、15 分以上古いか、ロック内の PID が生存していなければ stale として削除。生きていれば最大 `lock_wait_sec`（120 秒）待つ。ロック取得後にもう一度キャッシュ判定（prewarm と hook の競合対策） |
| 4 | `_backup_edited_stream_py()` | 既存 `stream.py` の sha256 が前回 `meta.json` の値と違えば（＝エージェントやユーザーが編集済み）`stream.py.bak-<日時>` に退避 |
| 5 | `_clean()` | `nuggets/` `supernodes/` `opaque/` と `generated_raw.py` `structure.json` `_extract.log` を削除（`rebuild/` と退避ファイルは残す） |
| 6 | `clemb_runner.run_jython()` | `jython/extract_stream.py` の先頭に `STR_PATH = u"..."` `OUT_DIR = u"..."` `TOOL_VERSION = u"..."` を前置した一時ファイルを `.strcode/` に書き、`clemb.exe -script <tmp> -execute -log _extract.log` を実行。標準出力/ログから `===STRCODEC_RESULT=== {json}` を探す |
| 7 | `transform.parse_generated()` → `transform.normalize()` | `generated_raw.py` と `structure.json` から `stream.py` を生成 |
| 8 | `_normalize_children()` | スーパーノード内側の生成物を `supernodes/<var>/stream.py`（読み取り専用ヘッダ付き）に正規化（再帰） |
| 9 | `summarize.build_summary()` | `summary.md` を生成 |
| 10 | `meta.json`, `README.md` | キャッシュ鍵・統計・成果物の説明を書く |

戻り値は `{"dir", "cached", "summary_path", "stream_py", "meta", "backup"}`。

### 4.2 clemb の起動（`clemb_runner.py`）

- **clemb.exe の探索順**（`find_clemb`）: `config.json` の `clemb_path` → 環境変数 `SPSS_MODELER_CLEMB_PATH` → `~/.spss-modeler-clemb/config.json` → `~/.mcp-servers/spss-clemb-mcp/config.json`（MCP と同じ設定を再利用）→ 既定 `C:\Program Files\IBM\SPSS\Modeler\19.0\bin\clemb.exe`。
- **環境変数**: `JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8 -Dclient.encoding.override=UTF-8 -Dsun.jnu.encoding=UTF-8`、`PYTHONIOENCODING=utf-8`（spss-clemb-mcp と同一）。これで日本語パス・日本語ラベルを含むスクリプトが UTF-8 のまま通ります。
- **パラメータ受け渡し**: `-P` は standalone スクリプトには効かないため、`NAME = u"値"` の行を前置（JSON エスケープで `\` と `"` を安全化）。
- **エンコーディング宣言の除去**: 先頭 2 行の `# -*- coding: ... -*-` は自動でコメントに置換（clemb はスクリプトを unicode 文字列としてコンパイルするため、宣言があると `SyntaxError: encoding declaration in Unicode string` になる）。
- **コンソール非表示**: `CREATE_NO_WINDOW` で起動（hook や裏の prewarm でウィンドウが出ない）。
- **戻り値** `RunResult`: `returncode` / `stdout` / `stderr` / `log_text` / `elapsed` / `script_path`。`combined` と `tail(n)` はエラー表示用。
- **`run_script_file()`**: 既存のスクリプトファイル（再構築スクリプト）をそのまま実行する版。
- **`parse_sentinel(text, marker)`**: 出力中の最後の `===MARKER=== {json}` 行を辞書にする。

### 4.3 抽出テンプレート（`jython/extract_stream.py`、Jython 2.7）

clemb の中で動くため Python 2 文法（`except E, e:`、`unicode`、`print(...)` は 1 引数）で書かれており、**エンコーディング宣言を書いてはいけません**（テンプレート先頭のコメント参照）。

1. `session = modeler.script.session()`（batch では `ComponentEnvironment` そのもの）、`_TR = session.getTaskRunner()`。
2. `session.openProcessorStream(FileInputStream(File(STR_PATH)), True)` でストリームを開く（`.str` を実行はしない）。
3. `_sorted_nodes()`: ノードを `(x, y, id)` でソート。`stream.iterator()` の順序は非決定的なので、変数名（`derive_node1` 等）を毎回同じにするための処置。おおむね「キャンバスの左から右」の順になります。
4. `_gen()`: `JythonGenerator(session).generateStreamFragment(ArrayList)` を呼び、生成コードを `generated_raw.py` に UTF-8 で書く。
5. `_varmap()`: 生成コード中の `# var = modeler.script.stream().findByID("id...")` コメントから **ノード ID → 変数名** の対応表を作る（構造 JSON とコードを結ぶ鍵）。
6. `_node_info()`: 各ノードについて id / var / type / class / label（`getLabel()`）/ custom_name / x / y / kind / annotation / tooltip / modified_props（`getModifiedSlotProperties()` の名前）/ pred_ids / succ_ids（`predecessorAt` / `successorAt`）を集める。applier なら内部 ID 4 種と `getLocalizedAlgorithmName()` も記録。
   - `_kind()` の判定順: 入出力コネクター → `apply*`（applier）→ `*_super` / `getChildDiagram` を持つ（supernode）→ `unknown*`（opaque）→ クラス名 `Build*`（builder）→ `isInitialNode()`（source）→ `isTerminalNode()`（terminal）→ それ以外（process）。
7. `.nod` 保存: applier → `nuggets/<var>.nod`、supernode → `supernodes/<var>.nod`、opaque → `opaque/<var>.nod`。`taskrunner.saveNodeToFile(node, path)` は**保存先ディレクトリを事前に作らないと失敗**するため `mkdirs()` してから呼びます。失敗は `nod_error` として記録し処理は続行。
8. スーパーノード: `getChildDiagram()` の内側ノードに対して同じ抽出を再帰（深さ 3 まで）。内側の生成コードは `supernodes/<var>/generated_raw.py`。
9. `_stream_info()`: ストリーム名 / ID / 変更済みプロパティ（`getModifiedSlotProperties()` の名前と値）/ `execute_method` / `script` / `encoding` / 日付・時刻書式 / パラメータ（`getParameterNames()`）/ 注釈 / コメント数。
10. `structure.json` を書き、`===STRCODEC_RESULT=== {"nodes": N, "links": M, "elapsed_ms": ...}` を print。例外時は `===STRCODEC_ERROR=== ...` と traceback を出して非ゼロ終了。

Java オブジェクトは `_jsonable()` で JSON 化可能な型（Map → dict、List → list、それ以外は文字列）に落とします。`_modeler_version()` は `getServerVersionInfo()` から `ServerVersionMajor=19 ...` のような文字列を組み立てます。

### 4.4 正規化（`transform.parse_generated` / `transform.normalize`）

**parse_generated**（生成コードの行単位解析）:

| 行の形 | 扱い |
|---|---|
| `var = modeler.script.stream().createAt("type", u"label", x, y)` | `Block` を開始（var / type / label リテラル / 座標） |
| `# var = ...findByID("id")` | その Block の `node_id` |
| `# var = ...findByType(...)` | 捨てる |
| `modeler.script.stream().link(a, b)` | リンク一覧へ |
| `var.setPropertyValue(...)` / `setKeyedPropertyValue(...)` | `modeler.script.stream()` → `stream` に置換し、`replace_null()` で `null` → `None` にしてから Block の setters へ |
| それ以外のコメント | 直前の Block に保持（Generator が未知プロパティを `# var.setPropertyValue("x", ???)` とコメント化する場合の可視化） |
| それ以外の文 | `other` へ |

`replace_null()` は `tokenize` で **NAME トークンの `null` だけ**を置換します。文字列リテラル内の `null`（CLEM 式など）は変わりません。

**normalize**（`stream.py` の組み立て）:

1. `structure.json` のノード情報を `node_id`（無ければ var）で Block に対応付け、`kind` を決める。
2. `topo_order()`: リンクからトポロジカル順（Kahn 法、同順位は座標 → 名前）を作り、ソース → 下流の順に Block を並べる。
3. ヘッダ（元パス・sha256・日時・ツール版・Modeler 版・規約の説明）を `#` コメントで出す。
4. Block ごとに `# ---- var | type | "label" | @(x, y) | kind` と `# original id: ...` を出し、kind に応じて:
   - applier → `var = NUGGET("applyxxx", u"label", x, y, nod=u"nuggets/var.nod", builder="<builder の var>", input="<上流の var>")`。`builder` は `builder_node_id` を ID 対応表で解決（同じストリームに無ければ `None` + 注記）。内部 ID 4 種の setter は `# internal ids (not restored; ...)` というコメント 1 行に畳む。
   - supernode / opaque → `SUPERNODE(...)` / `OPAQUE(...)`（`nod=` のみ）。
   - それ以外 → `var = stream.createAt(...)`。
   - 続けて setter を出し、最後に `flag_fixups()`: `custom_name` を設定しているのに `use_custom_name` が元で未変更なら `var.setPropertyValue("use_custom_name", False)` を追記（`model_name` / `use_model_name` も同様）。Modeler は `custom_name` を設定すると `use_custom_name` を勝手に ON にして表示名を変えてしまうため、元と同じ見た目に戻す処置です。
5. `other` があれば `# ---- other statements ----` に出す。
6. `# ---- links ----` にトポロジカル順で `stream.link(a, b)`。

出力は決定的（同じ入力から常に同じテキスト）で、Python 3 の `ast.parse` で解析できる文法に収まっています（テストで担保）。

### 4.5 要約（`summarize.py`）

`summary.md` は hook がコンテキストへ注入する本体なので、**短く・データフロー順・判断材料が揃う**ことを優先しています。

| 節 | 内容 | 情報源 |
|---|---|---|
| 見出し・メタ行 | ファイル名、ノード/リンク数、sha256 先頭、デコード日時、Modeler 版、成果物パス、ナゲット/スーパーノード一覧、ストリーム名・`execute_method`・パラメータ数 | meta / structure |
| ノード一覧 | var / type / label / 座標 / kind / key settings（`custom_name`, `full_filename`, `*_expr`, `model_name`, `target=`（`direction`/`role` が Target の項目）, `typed_fields=`（`type` キー付き設定の数）など上位項目を 1 行に圧縮） | stream.py の setter |
| データフロー | ソースからの ASCII ツリー（分岐・合流。合流は `(inputs: ...)`、再登場は `(see above)`、ナゲットは `[nugget]`、スーパーノードは `[super]`、ビルダーは `[builder]`） | structure の links |
| 入出力パス | `full_filename` 系の値と存在チェック（`exists` / `NOT FOUND` / `$` 始まりは「Modeler 変数、未確認」/ `.` 始まりは「ストリーム相対、未確認」） | setter |
| モデル | builder（model_name）と nugget（builder の var、`.nod` の有無、アルゴリズム名） | structure |
| CLEM 式 / 条件 | `*_expr` / `condition` の一覧 | setter |
| パラメータ / スクリプト | あれば | structure.stream |
| 注意 | `.nod` 保存失敗、スーパーノード内部の閲覧先、未知ノード型、注釈 | structure |
| 使い方 | エージェント向け 3 行（直読み禁止 / rebuild の呼び方 / 裏取り） | 固定 |

### 4.6 実行例と所要時間

```
> .bob\strcodec\strcodec.cmd decode samples\campaign_response.str
（summary.md の内容が標準出力に出る。同梱サンプル 8 ノードで初回 約 10 秒、2 回目以降 0.1 秒）
```

内訳: clemb 起動が大半（8〜9 秒）、抽出処理 1 秒程度、Python 側の正規化・要約 0.1 秒程度。ノード数より
clemb の起動時間が支配的なので、12〜28 ノードのストリームでも 15〜25 秒に収まります。

---

## 5. 再構築処理の詳細（`stream.py` → 再現スクリプト → `.str`）

入口は `strcodec.py rebuild <file.str | dir.strcode>`。既定では**スクリプトを生成するだけ**で、実行はエージェントが `spss-clemb-mcp` で行います（`--run` を付けると clemb を直接実行してレポートまで出します）。

### 5.1 準備（`rebuild.prepare`）

1. 入力を `.strcode` ディレクトリに解決（`.str` なら隣の `<stem>.strcode`。未デコードなら `not decoded yet` エラー）。
2. `stream.py` / `structure.json` / `meta.json` の存在確認。
3. 出力 `.str` の既定は `<元の場所>/<stem>_rebuilt.str`（`config.output_suffix`）。`--out` で変更可。**元ファイルと同じパスは拒否**します。
4. `RebuildContext` を組み立て（元パス、`.strcode` 絶対パス、出力パス、結果 JSON パス、`--retrain`、検証有無、`--map` の対、期待ノード/リンク数、ソースノードの var 一覧、分割サイズ、大リテラル閾値、prelude 本文）。
5. `transform.build_rebuild()` でスクリプト本文を生成し `rebuild/<stem>_rebuild.py` に書く。古い結果 JSON は削除。

### 5.2 スクリプト生成（`transform.parse_stream_py` / `transform.build_rebuild`）

**parse_stream_py**: `ast.parse` で `stream.py` をトップレベル文に分割し、各文を分類します（エージェントが複数行に編集しても解析できる）。

| 分類 | 判定 | 例 |
|---|---|---|
| `create` | `var = stream.createAt(...)` | 通常ノード。引数は `_create("var", ...)` に包まれる |
| `marker` | `var = NUGGET(...)` / `SUPERNODE(...)` / `OPAQUE(...)` | 引数・キーワード引数を `ast.literal_eval` で取り出す |
| `sp` / `skp` | `var.setPropertyValue(...)` / `var.setKeyedPropertyValue(...)` | |
| `link` | `stream.link(a, b)`（両引数が名前） | |
| `other` | それ以外 | そのまま build_part に入る |

`ast.unparse` は使いません（`u"..."` 接頭辞が失われ Jython 2 で日本語が壊れるため）。書き換えはソース断片に対するテキスト操作です。断片の切り出しは `SourceSegmentCache`（ビルド単位。ソースをパーサと同じ規則で行に分割し UTF-8 バイト列にするのを 1 回だけ行い、ノードの行番号・バイト列オフセットでスライスする）で行います。`ast.get_source_segment()` と同じ意味論（`\r\n` / `\r` / `\n`、フォームフィードは行区切りにしない、`padded`）を持ち、テストで全ノードについて一致を確認しています。CPython 3.10 の `ast.get_source_segment()` は呼ぶたびに全文を 1 文字ずつ走査するため、12 ノードの stream.py（約 8 万文字、4,099 回の切り出し）で約 90 秒かかっていましたが、キャッシュ化で約 1 秒になり、生成物は byte 単位で同一です。

**build_rebuild** の変換規則:

| 元の文 | 生成される文 | 目的 |
|---|---|---|
| `var = stream.createAt(t, l, x, y)` | `var = _create("var", t, l, x, y)` | 未知の型などで失敗しても `None` を返して記録し、同じチャンクの残りの文が実行される |
| `stream.setPropertyValue(a, v)` | `_sp(stream, a, v)` | ストリーム設定（先頭セクション） |
| `var.setPropertyValue(a, v)` | `_sp(var, a, v)` | 例外を記録して続行（既知の `[None, None]` 拒否など） |
| `var.setKeyedPropertyValue(a, k, v)` | `_skp(var, a, k, v)` | 同上 |
| 4,000 文字（`big_literal_chars`）超の setter | 値を `ast.literal_eval` → JSON 化し `_sp(var, a, _J(u"...json..."))` | 巨大リストリテラルの 64KB 制限回避（`json.loads` はコンパイルされない） |
| 通常ノードの文（create / sp / skp / other） | 40 文または 20KB ごとに `def build_part_NNN(): global <全変数>` へ分割 | JVM の 64KB メソッド制限回避 |
| `stream.link(a, b)`（両端が通常ノード） | `_link_v("a", "b")` | 変数未定義でも落ちずに記録 |
| `stream.link(a, b)`（片方がマーカー） | `_pend("a", "b")`（保留リンク） | ナゲット等の生成後に接続 |
| `var = NUGGET(...)` 等 | 文をそのまま（prelude が同名関数を定義）。続けてそのノードの setter、`_link_pending()` | ナゲットは通常ノードとリンクの後で生成 |

生成スクリプトの骨格:

```
# ==== strcodec rebuild script ...（エンコーディング宣言なし）
import os, json, traceback, modeler.script ; from java.io import ... ; from java.lang import Throwable, System
BASE_DIR / OUT_STR / RESULT_JSON / STREAM_NAME / RETRAIN / VALIDATE / PATH_MAP / EXPECTED_NODES / EXPECTED_LINKS / SOURCE_VARS / NUGGET_VARS
<jython/rebuild_prelude.py の全文>
stream = _new_stream(STREAM_NAME)
def build_part_001(): global ...; <文 ×40>
...
_run_parts([build_part_001, ...])
# ---- links (ordinary nodes) ----      _link_v("a", "b") ...
# ---- links involving nuggets ... ---- _pend("a", "b") ...
# ---- nuggets / supernodes / opaque nodes ----
applyc50_node1 = NUGGET("applyc50", u"...", 738, 262, nod=u"nuggets/applyc50_node1.nod", builder="c50_node1", input="type_node2")
_sp(applyc50_node1, "custom_name", u"...")
_link_pending()
...
_link_pending(True)
_validate(SOURCE_VARS, NUGGET_VARS)
_finish(EXPECTED_NODES, EXPECTED_LINKS)
```

`--coding-header` を付けると先頭に `# -*- coding: utf-8 -*-` を入れます（Modeler GUI から実行する場合専用。clemb はこの宣言を SyntaxError にするため `--run` とは併用できず、CLI が拒否します）。

### 5.3 実行時ランタイム（`jython/rebuild_prelude.py`）

| 関数 | 役割 |
|---|---|
| `null = None` | エージェントが `null` を書いてしまった場合の保険 |
| `_new_stream(name)` | `taskrunner.createStream(name, True, True)` で**新しい空ストリーム**を作る（GUI では現在のストリームを汚さない。batch でも default ストリームを使わない） |
| `_abs(p)` | `.strcode` 相対パスを絶対化（`$` / ドライブ文字 / 先頭 `/` はそのまま） |
| `_path(v)` | `PATH_MAP` の接頭辞置換 → `$`・`.` 始まり以外で存在しなければ `path not found` を警告。値・OLD・NEW とも `\` を `/` に正規化し、Windows では大文字小文字を無視、接頭辞はパス区切り境界でのみ一致（`C:/old` は `C:/older/...` に一致しない） |
| `_create(var, type, label, x, y)` | `stream.createAt`。失敗は `{kind: create, var, type, label, error}` として記録し `None` を返す（後続の `_sp(None, ...)` も失敗として記録される） |
| `_sp` / `_skp` | setter を実行。`full_filename` 系（`*_filename` / `*file_name`）は両方とも `_path` を通す。失敗は `_FAILS` に `{kind, node, prop, key, error}` を積んで続行 |
| `PARAM(name, value=, storage=, label=)` | ストリームパラメータ。`setParameterStorage`（Integer/Real/String/Boolean/Date/Time/Timestamp）→ `setParameterValue` → `setParameterLabel` |
| `_J(s)` | `json.loads` |
| `_link_v(a, b)` | `globals()` から変数を引いて `stream.link`。無ければ失敗を記録 |
| `_pend` / `_link_pending(final)` | 保留リンク。両端が存在した時点で接続。`final=True` で残りを失敗として記録 |
| `_run_parts(fns)` | `build_part_NNN` を順に実行。パート単位で例外を捕捉（`_create` / `_sp` は自前で捕捉するので、ここに来るのはエージェントが書いた生の文の例外だけ） |
| `_insert_nod(nod, label, x, y, what)` | `taskrunner.insertNodeFromFile(絶対パス, stream)` で `.nod` を移植。座標が違えば `setXYPosition` |
| `NUGGET(...)` | `RETRAIN` でなければ `.nod` を移植。無い／失敗なら **失敗として記録**（黙って再学習しない: 再学習はデータを読み、別のモデルになる）。`--retrain` なら: 実行前のノード ID 集合を控え → `builder.run(results)` → **実行で自動挿入された applier を削除** → `stream.createModelApplierAt(results[0], label, x, y)` |
| `SUPERNODE(...)` | `.nod` から移植。無ければ失敗として記録（空のスーパーノードは中身の消失を隠すので作らない） |
| `OPAQUE(...)` | `.nod` から移植。無ければ失敗として記録 |
| `_validate(sources, nuggets)` | 各データソースと各ナゲットに一時 `table`（座標 2000,2000）を接続して `run()` し、成功/失敗を `_VALID` に記録してから削除。`--no-validate` で省略 |
| `_finish(expected_nodes, expected_links)` | ノード数・リンク数を数え、出力ディレクトリを作って `saveStreamToFile`、結果 JSON（`fails` / `warnings` / `infos` / `validation` / `node_types` / `elapsed_ms` など）を書き、`===STRCODEC_REBUILD=== {...}` を print、失敗と警告をログ出力 |

実行順序（重要）: 通常ノード生成と setter → 通常ノード間リンク → ナゲット/スーパーノード生成（各生成直後に保留リンクを接続）→ 残り保留リンク → 検証 → 保存。**ビルダーを再実行する場合、入力リンクが完成してから `run()` される**ことがこの順序で保証されます。

### 5.4 実行方法（3 通り）

| 方法 | コマンド | 用途 |
|---|---|---|
| エージェント（推奨） | `use_mcp_tool spss-clemb-mcp execute_clemb {"script_file": ".../rebuild/<stem>_rebuild.py", "working_directory": ".../<stem>.strcode", "log_file": ".../rebuild/<stem>_rebuild.log"}` | `rebuild` の出力に引数がそのまま表示される |
| CLI | `python .bob\strcodec\strcodec.py rebuild <str> --run` | 人間の確認・テスト。実行後に report まで生成 |
| Modeler GUI | ツール > スタンドアロン・スクリプト で `<stem>_rebuild.py` を開いて実行 | 生成されたストリームがストリームマネージャに現れる（`--coding-header` 推奨） |

### 5.5 レポート（`rebuild.render_report` / `strcodec.py report`）

結果 JSON（`rebuild/<stem>_rebuild_result.json`）から Markdown を生成します。

- `STATUS: OK` … 保存済み、実質的な失敗なし、検証失敗なし、ノード/リンク数が期待どおり、警告なし → exit 0
- `STATUS: OK WITH WARNINGS` … 上記のうち警告（`path not found` 等）だけがある → exit 0
- `STATUS: SAVED WITH ISSUES` … 保存はされたが setter/リンク/生成失敗、検証失敗、またはノード/リンク数の不一致あり → exit 1
- `STATUS: FAILED` … 保存されていない（`save_error`）→ exit 1
- `STATUS: NO RESULT` … `_finish` まで到達していない（ログ末尾を併記）→ exit 1

判定は `rebuild.classify()` に集約され、`rebuild --run` と `report` の終了コードはこれに従います。意図的にノードを追加・削除して件数が変わる場合は `--allow-issues` を付けると保存済みなら exit 0 になります。`is_benign()` により、Range フィールドの `values=[None, None]` 拒否（`InvalidPropertyException ... '[null, null]'`）は「既知・無害」として別枠に表示し、STATUS 判定から除外します。

`report` 単独実行時の生成側の警告や出力先は、`rebuild` が書く `rebuild/<stem>_rebuild_prep.json` から復元します。

### 5.6 構造比較（`verify.py`）

2 つのストリームを（必要ならデコードして）`structure.json` と `stream.py` で比べます。

- 構造（終了コードを決める）: ノード `(type, label, x, y)` の多重集合の差、リンク（同キーの組）の多重集合の差
- プロパティ値（情報提供。`--strict` で終了コードにも反映）: 同じキーのノード同士で `stream.py` の setter を比較し、値が違う／片側だけにあるプロパティを列挙（内部 ID 4 種は除外）
- ストリーム設定: `stream.modified_props` の値を比較（`parameters` / `parameters_table` / `min_canvas_*` / `use_max_set_size` はキャンバス状態なので除外）

`RESULT: STRUCTURE_MATCH` で exit 0、`STRUCTURE_DIFFERENT` で exit 1。プロパティ値の差は `properties: N node(s) with different values, M stream setting(s) differ` として表示し、差が無ければ `PROPERTIES_MATCH` を付けます。往復では `type` ノードの `metadata` / `metadata_all` / `field_metadata` / `description` のようにデータから再導出される値が変わることがあり、これは設定の消失ではありません。**`STRUCTURE_MATCH` は設定値の同一性を保証しません**。設定の変更を確認するときはプロパティ差の一覧を読んでください。

### 5.7 `--retrain` と `--map`

- `--retrain`: `RETRAIN = True`。すべてのナゲットを builder の再実行で作り直す（データが実行環境に必要）。Modeler は builder 実行時にナゲットをストリームへ自動挿入するため、prelude が差分ノードを削除してから `createModelApplierAt` します（削除しないとノード数が増える: 検証で 14/13 → 対策後 12/11）。
- `--map OLD=NEW`（複数可）: `full_filename` 系（`*_filename` / `*file_name`、`setKeyedPropertyValue` も対象）の値の接頭辞置換。値と OLD/NEW の `\` を `/` に正規化し、Windows では大文字小文字を無視して、パス区切り境界で接頭辞一致したものを置換します。summary の「入出力パス」に `NOT FOUND` があるときに使います。

### 5.8 実行例

```
> .bob\strcodec\strcodec.cmd rebuild samples\campaign_response.str --run
# rebuild report: campaign_response
- generated script: .../campaign_response.strcode/rebuild/campaign_response_rebuild.py (557 lines)
- output stream: .../campaign_response_rebuilt.str
## STATUS: OK
| nodes | 8 (expected 8) |   | links | 7 (expected 7) |
| setter/link failures | 0 (+0 known benign) |   | validation | 2 ok / 0 failed |
| elapsed (inside clemb) | 1746 ms |
## info
- nugget inserted from nuggets/applyc50_node1.nod: 応答予測

> .bob\strcodec\strcodec.cmd verify samples\campaign_response.str samples\campaign_response_rebuilt.str
RESULT: STRUCTURE_MATCH
nodes: campaign_response.str=8, campaign_response_rebuilt.str=8
links: campaign_response.str=7, campaign_response_rebuilt.str=7
properties: 1 node(s) with different values, 0 stream setting(s) differ
  type "データ型" @(462,97):
    only set in campaign_response_rebuilt.str: description[u"age"], field_missing_metadata[u"age"], ...
    （データから再導出されるメタデータ。設定の消失ではない）
```

---

## 6. hooks の詳細（Bob との接続）

### 6.1 Bob の hook 仕様（公式ドキュメントより）

| 項目 | 内容 |
|---|---|
| イベント | `SessionStart`（初回ターン前）、`UserPromptSubmit`（モデル送信前）、`PreToolUse`（ツール実行前）、`PostToolUse`、`Stop` |
| 定義場所 | ワークスペース `.bob/settings.json`（グローバルは `~/.bob/settings/settings.json`） |
| 種類 | `command` のみ。Windows では `cmd /c <command>`、cwd はワークスペース |
| 入力 | stdin に JSON。`UserPromptSubmit` は `prompt`、`PreToolUse` は `tool` と `input` |
| 出力 | `SessionStart` / `UserPromptSubmit` の stdout は**モデルのコンテキストへ**。`PreToolUse` の stdout は無視 |
| 終了コード | `2` = ブロック（`UserPromptSubmit` / `PreToolUse` のみ有効）。その他の非ゼロは記録のみ |
| timeout | 既定 10 秒。`0` で無効 |
| 制限 | 入力（プロンプト/ツール引数）の書き換え不可、スケジュール実行不可、サンドボックスなし |

### 6.2 `.bob/settings.json`

```json
{
  "hooks": {
    "SessionStart":     [{ "hooks": [{ "type": "command", "command": ".bob\\strcodec\\strcodec.cmd hook session-start", "timeout": 60 }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": ".bob\\strcodec\\strcodec.cmd hook prompt",        "timeout": 0  }] }],
    "PreToolUse":       [{ "matcher": "^read_file$", "hooks": [{ "type": "command", "command": ".bob\\strcodec\\strcodec.cmd hook guard-read", "timeout": 10 }] }]
  }
}
```

3 つとも launcher 経由なので PATH に `python` は不要（§3.2）。`strcodec.py hook <name>` が対応する `hooks/hook_<name>.py` の `main()` を呼び、stdin/stdout/終了コードはそのまま通る。`UserPromptSubmit` の timeout を `0` にしているのは、初回デコードが 15〜25 秒かかるため（既定 10 秒だと打ち切られる）。

### 6.3 各 hook の処理

**`hook_session_start.py`（SessionStart）**
1. cwd（ワークスペース）配下の `.str` を `find_str_files` で探索（`.git` / `node_modules` / `.bob` / `.claude` / `*.strcode` / ドットで始まるディレクトリを除外。深さ 8、最大 500 件）。
2. 各ファイルのキャッシュ状態（`is_cache_valid`）を付けて `<spss-stream-index>` ブロックを stdout に出す（→ コンテキスト）。「`.str` は直読みしない、skill を使う」の 1 行も添える。
3. 未デコードがあり `config.prewarm` が真なら、`strcodec.py prewarm --root <cwd> --max N` を **detached プロセス**として起動して即終了する。`common.spawn_detached()` は `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW | CREATE_BREAKAWAY_FROM_JOB` で起動し、hook の終了（親プロセスツリーの終了）に巻き込まれないようにしています（breakaway が許可されていない環境ではフラグなしで再試行）。

**`hook_prompt.py`（UserPromptSubmit）**
1. stdin の JSON から `prompt` を取る（JSON が壊れていれば生テキストを対象にする）。`.str` を含まなければ何もしない。
2. `candidates()` で候補ファイルを集める:
   - 正規表現 `@?((?:[A-Za-z]:)?[^\s"'<>|*?`]+\.str)(?![\w.])` にマッチしたトークン（`@/path/x.str`、絶対/相対パス）。先頭の `@` と `/` を外した形でも試す。
   - 加えて、ワークスペース内の全 `.str` について**ファイル名がプロンプトに含まれるか**（スペースや日本語を含むパスの取りこぼし対策）。
   - 実在するファイルのみ、重複除去、最大 `max_prompt_files`（3）件。
3. 各ファイルを `decode_stream()`（キャッシュ有効なら即時。prewarm 中ならロック解放を待つ）し、`summary.md` を最大 `summary_max_lines`（300）行に切って
   `<spss-stream-context file="..." decoded_dir="..." cached="true|false"> ... </spss-stream-context>` として stdout に出す。
4. 失敗しても短い通知を出して **exit 0**（プロンプトは絶対に止めない）。動作は `logs/hooks.log` に記録。

**`hook_guard_read.py`（PreToolUse, matcher `^read_file$`）**
1. `tool` が `read_file` で、`input` 内の文字列に `.str` / `.nod` で終わるものがあれば、stderr に代替手順（`decode` コマンド、`summary.md` / `stream.py` の場所、skill 名）を出して **exit 2**（ブロック）。
2. それ以外は exit 0。`config.guard_read=false` で無効化できます。

### 6.4 未確認事項

シェルから stdin JSON を流す形での動作は確認済みですが、**Bob 本体の中での**次の点は未確認です。
- `UserPromptSubmit` の stdout がどのような形でモデルに見えるか（システム情報として付くか、ユーザーメッセージ内か）。
- `PreToolUse` でブロックしたとき、stderr の案内文がモデルに渡るか（ユーザー向けエラー表示のみの可能性）。渡らなくても skill と summary 注入で運用できます。
- @メンション時に hook が受け取る `prompt` が `@/path` の生テキストか展開後か（両方に対応する検出にしてあります）。

---

## 7. skills / AGENTS.md の詳細

### 7.1 Bob の skill 仕様

- 置き場所: `<project>/.bob/skills/<name>/SKILL.md`（グローバルは `~/.bob/skills/`）。frontmatter の `name` と `description` が必須で、**`description` を見て Bob が自動的に起動を判断**します（無いスキルは無視される）。1 会話で 1 回読み込まれ、既定では起動前に許可を求めます（設定で自動承認可）。
- 付随ファイル（チェックリスト、リファレンス、scripts/）を同じフォルダに置けます。

### 7.2 `spss-str-decode`

- トリガー（description）: `.str` が与えられた／@メンションされた／パスが示された、または「このストリームは何をしている？」「中身/ノード構成/データフローを説明して」。
- 手順: デコード済み確認（無ければ `decode` を `execute_command`）→ `summary.md` を読む → 必要ブロックだけ `stream.py` を読む → 未知の型/プロパティは `ibm-docs-mcp` で裏取り → CLEM 式を言い換え → 定型で解説。
- 禁則: `.str` / `.nod` の `read_file`、`generated_raw.py` の実行、パス実在の推測、内部 ID の意味付け、修正の実施（`spss-str-rebuild` へ）。

### 7.3 `spss-str-rebuild`

- トリガー: 「再現/復元/作り直して」「stream.py を修正して .str に反映」「再現用 Jython が欲しい」「ノードを追加/変更/削除して保存」。
- `stream.py` 編集規約: 1 文 1 行、`u"..."`、`None`、エンコーディング宣言なし、`modeler.script.stream()` を書かない、`NUGGET(...)` 等のマーカーを崩さない、上流を変えたら `--retrain`、内部 ID を復元しない、`use_custom_name=False` の補助行を消さない、新規プロパティは裏取り。
- 手順: デコード確認 → 編集 → `rebuild` 生成 → `execute_clemb` で実行 → `report` と `verify` → 納品（`.str` パス、スクリプトパス、report 要点、verify 結果、移植か再学習か）。
- 禁則: 元 `.str` の上書き、生成スクリプトの手修正、`NUGGET` を `createAt` に書き換える、内部 ID の復元、`saved: true` 未確認での完了、`# -*- coding` の追加。

### 7.4 `_shared/strcodec-reference.md`

両スキルから参照する技術背景: 全体像、実機で確認済みの事実 11 項目、`stream.py` の構造、CLI、hooks、エラー対処表、制約。

### 7.5 AGENTS.md（ワークスペース直下）

エージェント常設ルール: `.str`/`.nod` は直読みしない、読むなら `spss-str-decode`、作り直すなら `spss-str-rebuild`、実行は `spss-clemb-mcp`、裏取りは `ibm-docs-mcp`、成果物の置き場所、clemb 向け Jython の書式（宣言なし・`u""`・`None`・`except E, e:`・Java オブジェクトを print しない）。

---

## 8. 成果物ファイルの仕様

### 8.1 `<stem>.strcode/` の一覧

| ファイル | 生成元 | 役割 | 再デコードで |
|---|---|---|---|
| `summary.md` | summarize.py | コンテキスト注入用の要約 | 上書き |
| `stream.py` | transform.normalize | 正規化した編集用 Jython | 上書き（編集済みなら `stream.py.bak-<日時>` に退避） |
| `structure.json` | extract_stream.py | 機械可読の構造 | 上書き |
| `generated_raw.py` | JythonGenerator | 生出力（`null` を含む参考物） | 上書き |
| `nuggets/<var>.nod` | saveNodeToFile | ナゲット実体 | 削除して再作成 |
| `supernodes/<var>.nod`, `supernodes/<var>/generated_raw.py`, `supernodes/<var>/stream.py` | 同上 + 再帰抽出 | スーパーノード実体と内側コード（閲覧用） | 削除して再作成 |
| `opaque/<var>.nod` | saveNodeToFile | 未知ノード型の実体 | 削除して再作成 |
| `meta.json` | decode.py | キャッシュ鍵（`sha256`, `tool_version`）と統計 | 上書き |
| `README.md` | decode.py | 成果物の説明 | 上書き |
| `_extract.log` | clemb `-log` | 抽出時の clemb ログ | 上書き |
| `.lock` | decode.py | 実行中のみ存在（PID 入り） | — |
| `rebuild/<stem>_rebuild.py` | rebuild.py | 再現スクリプト | 残る |
| `rebuild/<stem>_rebuild_result.json` | prelude `_finish` | 実行結果 | 残る（rebuild 生成時に削除） |
| `rebuild/<stem>_rebuild.log` | clemb `-log` | 実行ログ | 残る |
| `rebuild/<stem>_rebuild_report.md` | rebuild.py | レポート | 残る |

### 8.2 `stream.py` の文法規約

- Python 3 の `ast.parse` で解析でき、かつ Jython 2.7 で動く共通部分集合（文字列は `u"..."`、`None`、`True/False`、リスト/辞書リテラル、関数呼び出し文）。
- `stream` は再構築スクリプトが定義する変数。ノードは `var = stream.createAt("type", u"label", x, y)`。
- setter は `var.setPropertyValue("prop", value)` / `var.setKeyedPropertyValue("prop", u"key", value)`。
- マーカー: `NUGGET(type, label, x, y, nod=, builder=, input=)`, `SUPERNODE(type, label, x, y, nod=)`, `OPAQUE(type, label, x, y, nod=)`。`builder` / `input` は変数名の文字列（後方参照を許すため）。
- リンクは末尾の `stream.link(a, b)`。
- `# ---- var | type | "label" | @(x, y) | kind` がブロック見出し（`grep -n "# ---- "` で目次）。
- 1 文が複数行になっても解析できますが、規約としては 1 文 1 行。

### 8.3 `structure.json` のスキーマ

```
{
  "tool_version": "0.1.0", "source": "<絶対パス>", "modeler_version": "ServerVersionMajor=19 ...",
  "stream": { "name", "id", "modified_props": {名前: 値}, "execute_method", "script", "encoding",
              "date_format", "time_format", "decimal_separator",
              "parameters": [ {"name", "value", "type", "label"} ], "annotation", "comment_count" },
  "code_file": "generated_raw.py",
  "nodes": [ { "id", "var", "type", "class", "label", "custom_name", "x", "y", "kind",
               "annotation", "tooltip", "modified_props": [名前], "pred_ids": [], "succ_ids": [],
               // applier のみ
               "builder_node_id", "builder_stream_id", "updating_node_id", "refresh_link_state", "algorithm",
               // .nod 保存対象のみ
               "nod": "nuggets/<var>.nod" | null, "nod_error": "...",
               // supernode のみ
               "children": { "code_file", "nodes": [...], "links": [...], "node_count", "link_count" } } ],
  "links": [ {"from": "<id>", "to": "<id>"} ],
  "elapsed_ms": 123
}
```

### 8.4 `meta.json` の項目

`tool_version`, `source_path`, `source_name`, `sha256`, `size`, `source_mtime`, `decoded_at`, `modeler_version`, `nodes`, `links`, `node_types`, `nuggets`, `supernodes`, `stream_py_sha256`, `stream_py_lines`, `generated_raw_lines`, `extract_elapsed_ms`, `clemb_elapsed_sec`, `backup_of_edited_stream_py`。

キャッシュ判定は `sha256` と `tool_version` の一致、および `structure.json` と参照 `.nod` の存在で行うため、`.str` が更新されたり、ツールの版を上げたり、`.nod` が消えたりすると自動で再デコードされます。`rebuild` も同じ条件（元 `.str` の sha256、ツール版、`stream.py` のマーカーが参照する `.nod`）を `rebuild.check_ready()` で検査し、問題があれば生成を拒否します（`--allow-stale` で続行。その場合は警告としてレポートに残ります）。

### 8.5 再構築結果 JSON（`rebuild/<stem>_rebuild_result.json`）

`saved`, `save_error`, `out_str`, `nodes`, `links`, `expected_nodes`, `expected_links`, `node_types`, `fails[{kind: set|link|part|nugget|supernode|opaque, node, prop, key, error, ...}]`, `warnings[]`, `infos[]`, `validation[{var, ok, error}]`, `retrain`, `elapsed_ms`。

---

## 9. 変換ルールとその根拠（実機検証の結果）

### 9.1 当初整理した 15 項目との対応

| 当初の項目 | strcodec での実装 |
|---|---|
| 1 Jython 2 互換化（`null = None`、50 行ずつ分割） | `null`→`None` はトークン単位で正規化、prelude にも `null = None`。40 文/20KB ごとの `build_part_NNN` |
| 2 通常ノードは `createAt` | そのまま |
| 3 setter は基本そのまま | `_sp` / `_skp` で包み、失敗を記録して続行 |
| 4 一部の `[null, null]` は例外 | 失敗を「既知・無害」として分類（一律削除しない） |
| 5 入力パスの補正 | `--map OLD=NEW` + 存在チェック警告（`$` 変数は Modeler に委ねる） |
| 6 通常リンクは `link()` | `_link_v` |
| 7 ナゲットを `createAt` しない | `NUGGET` マーカー（生成物から自動判定） |
| 8 Builder 実行 → `createModelApplierAt` | `--retrain` 経路。**既定は `.nod` 移植**（§9.2） |
| 9 内部 ID を復元しない | normalize がコメント化 |
| 10 semantic プロパティは再設定 | ナゲット生成後に `_sp` で再適用 |
| 11 入力リンク完成後に `run()` | 実行順序で保証 |
| 12 結果オブジェクトを print しない | 件数のみ print |
| 13 実行検証 | `_validate`（一時 table） |
| 14 構造検証 | `_finish` の件数 + `verify` |
| 15 `.str` 保存 | `saveStreamToFile` |

### 9.2 検証で新たに分かったこと（設計を変えた点）

| 事実 | 影響 |
|---|---|
| `taskrunner.saveNodeToFile(applier, path)` → `insertNodeFromFile(path, stream)` でナゲットが**学習済みモデルごと**移植でき、リンク後にスコアリングが成功する | ナゲットの既定を「再学習」から「移植」に変更。データ不要・決定的・高速。スーパーノードや通常ノードも同じ方法で移植可能 |
| `saveNodeToFile` は保存先ディレクトリが無いと `SessionException`（指定されたパスが見つかりません） | 保存前に `mkdirs()` |
| builder を `run()` すると Modeler がナゲットを自動挿入する | `--retrain` で差分 applier を削除してから `createModelApplierAt`（しないと 14/13） |
| `setPropertyValue("custom_name", ...)` が `use_custom_name` を ON にする（`model_name` も同様） | `flag_fixups` で元が未設定なら `False` を追記（これで verify が完全一致） |
| `# -*- coding: utf-8 -*-` は clemb で `SyntaxError` | 生成物に書かない。`clemb_runner` が自動除去 |
| standalone でも `modeler.script.stream()` は空の DefaultStream | それでも `createStream` で新規作成する方が GUI と両立して安全 |
| `generateStreamFragment` はスーパーノードの中身を出さない | `.nod` 移植 + 内側の閲覧用デコード |
| `Node.getName()` は引数必須 | `getLabel()` を使う |
| JythonGenerator の生成順は非決定的 | `(x, y, id)` でソートして変数名を固定 |
| 12 ノードで 45KB / 491 行、28 ノードで 68KB / 495 行、最長行 9.7KB（`metadata_all`） | 分割と大リテラルの JSON 化の閾値の根拠 |

---

## 10. 検証結果の記録

同梱サンプル（`samples/campaign_response.str`）での記録です。配布物だけで再現できます。

### 10.0 同梱サンプルでの往復（2026-09-13, v0.3.1）

| 操作 | 結果 |
|---|---|
| decode | 8 ノード / 7 リンク、10 秒（うち clemb 8.8 秒）。`stream.py` 142 行、`.nod` 1 件保存 |
| rebuild `--run` → verify | `STATUS: OK`、8/7、setter 失敗 0、検証 2/2 OK、`RESULT: STRUCTURE_MATCH`。プロパティ差は `type` ノードのデータ由来メタデータのみ |
| Bob 上で編集（条件抽出ノードを追加）→ rebuild → verify | 9/8 で `STATUS: SAVED WITH ISSUES`（意図した増加、`--allow-issues` で受理）、`RESULT: STRUCTURE_DIFFERENT` の差分は追加 1 ノードとつなぎ替え 3 リンクのみ。`values[membership]` が `["N","Y"]` → `["Y"]`（`samples/example-session.md`） |
| ユニットテスト | 72 件合格（CPython 3.12 で約 3 秒） |
| prelude（Jython 側） | clemb で `rebuild_prelude.py` を exec し 18 項目を検査。`_path`（バックスラッシュ・大文字小文字・接頭辞境界・UNC）、`_create` の失敗記録、`_skp` のパス置換、`.nod` 欠落時の NUGGET/SUPERNODE 失敗記録、`PARAM` と `date_format` の保存後の永続化 — 全件 PASS |
| hooks | stdin JSON を流して実行。prompt 注入 OK、read_file ガード exit 2 / 非対象 exit 0、SessionStart 索引 + detached prewarm が hook 終了後も完走 |

所要時間の目安: decode・rebuild `--run` とも 10〜15 秒程度。大半は clemb（JVM）の起動時間で、clemb 内部の処理は
1.5〜6 秒です。ノード数が数倍になっても全体の所要時間は大きくは変わりません。

### 10.1 2026-09-13 追記: 同梱 CPython 対応と rebuild 生成の高速化

| 項目 | 変更前 | 変更後 |
|---|---|---|
| `rebuild` 生成（12 ノードのストリーム、Modeler 同梱 CPython 3.10.7、launcher 経由の壁時計） | 89.5 秒 | 2.1〜3.6 秒（3 回計測。in-process の `build_rebuild()` は 0.9 秒） |
| 同（CPython 3.12.10） | 9.5 秒 | 約 0.5 秒（in-process 0.43 秒） |
| 生成物の同一性 | — | 変更前に固定した回帰フィクスチャと byte 単位で一致。実ストリーム 5 件の SHA-256 が 3.10.7 / 3.12 とも変更前と一致 |
| ユニットテスト | 22 件 | 49 件。CPython 3.12: 41 秒で全件合格。同梱 3.10.7（`-I -S -B -X utf8`）: 全件合格（所要時間は §10.2） |
| launcher | — | `--which` が同梱 3.10.7 を選択（source=modeler_Modeler_19.0）、`STRCODEC_PYTHON` 指定・不正指定時のフォールバック・`python-info`・`status` を確認 |
| 同梱 CPython だけの経路 | — | `strcodec.cmd decode --force` → `rebuild --run`（12/11、検証 3/3）→ `verify` = MATCH |

### 10.2 同梱 CPython 3.10.7 でのユニットテスト所要時間

`test_segments` の大きなフィクスチャ比較は参照実装 `ast.get_source_segment()`（3.10 では非常に遅い）を呼ぶため、ノードを 120 件にサンプリングして比較する。全件比較した初回計測は 406 秒だった（合格）。サンプリング後の計測: **同梱 CPython 3.10.7 で 49 件 14.4 秒、CPython 3.12.10 で 9.4 秒**（いずれも全件合格）。

```powershell
& "C:\Program Files\IBM\SPSS\Modeler\19.0\python\python.exe" -I -S -B -X utf8 -m unittest discover -s .bob\strcodec\tests
```

---

## 11. 設定とカスタマイズ

### 11.1 `.bob/strcodec/config.json`

| キー | 既定 | 意味 |
|---|---|---|
| `tool_version` | `"0.3.1"` | キャッシュ鍵の一部。変換ロジックを変えたら上げると全件再デコードされる |
| `chunk_statements` / `chunk_max_chars` | 40 / 20000 | `build_part_NNN` の分割単位 |
| `big_literal_chars` | 4000 | これを超える setter 文は JSON 経由にする |
| `summary_max_lines` | 300 | hook が注入する summary の上限行数 |
| `prewarm` / `prewarm_max_files` | true / 10 | SessionStart での裏デコードの有無と上限 |
| `guard_read` | true | read_file ガードの有効/無効 |
| `max_prompt_files` | 3 | 1 プロンプトで注入する `.str` の最大数 |
| `clemb_timeout_sec` | 600 | clemb 1 回のタイムアウト |
| `clemb_path` | null | clemb.exe の明示指定（§4.2 の探索順の最優先） |
| `ignore_dirs` / `max_scan_files` / `max_scan_depth` | 既定リスト / 500 / 8 | `.str` 探索の除外と上限 |
| `output_suffix` | `"_rebuilt"` | 再構築 `.str` の既定サフィックス |
| `lock_wait_sec` | 120 | 他プロセスのデコード完了を待つ上限 |

### 11.2 環境変数と Python の指定

- `STRCODEC_PYTHON`: 使う python.exe のフルパス（最優先）。`.bob/strcodec/python.path` に 1 行書く方法でも同じ（gitignore 済み）。どちらも無ければ `py -3` → PATH → Modeler 同梱版の順（§3.2）。
- `SPSS_MODELER_CLEMB_PATH`: clemb.exe のパス（MCP と共通）。launcher はここから `<Modeler>\python\python.exe` も推定する。
- `STRCODEC_PYTHON_SELECTED` / `STRCODEC_PYTHON_SOURCE`: launcher が CLI に渡す診断用（手で設定する必要はない）。
- hook は `cmd /c .bob\strcodec\strcodec.cmd hook ...` で起動されるため、PATH に `python` は不要。

### 11.3 ログ

- `.bob/strcodec/logs/strcodec.log`: decode / rebuild / clemb 実行の記録。
- `.bob/strcodec/logs/hooks.log`: hook の動作（注入・ブロック・prewarm 起動・失敗）。
- `<stem>.strcode/_extract.log`, `rebuild/<stem>_rebuild.log`: clemb 自身のログ。

---

## 12. 運用手順（人間向け）

### 12.1 初期確認

```
cd <ワークスペース>
.\.bob\strcodec\strcodec.cmd --which                # 選ばれる python.exe（通常 source=py_launcher か PATH。同梱版へのフォールバックなら modeler_Modeler_<版>）
.\.bob\strcodec\strcodec.cmd python-info            # 候補と判定
.\.bob\strcodec\strcodec.cmd status                 # 使用中の Python / clemb、.str の一覧とキャッシュ状態
.\.bob\strcodec\strcodec.cmd decode samples\campaign_response.str   # 同梱サンプル（samples/README.md）
python -m unittest discover -s .bob\strcodec\tests   # 70 件（PATH の Python。同梱版で確認するなら "<Modeler>\python\python.exe" -I -S -B -X utf8 -m unittest ...）
python .bob\strcodec\tests\selftest.py samples\campaign_response.str --retrain   # 統合（一時フォルダで decode→rebuild→verify）
# `python .bob\strcodec\strcodec.py ...` は Python が PATH にある環境でのみ使える別経路
```

### 12.2 日常の使い方（Bob 上）

- ストリームを説明させる: 「`@campaign_response.str` を説明して」。
- 変更して作り直す: 「`campaign_response.str` の優良顧客の式を … に変えて `.str` を作り直して」。
- 別環境から持ってきたストリーム: summary の「入出力パス」で `NOT FOUND` を確認し、「`--map "C:/old/dir=C:/new/dir"` で作り直して」と指示する。
- モデルを学習し直したい: 「`--retrain` で作り直して」（データが必要）。

（スラッシュコマンド `/str-decode` `/str-rebuild` は Bob 2.1.0 で使われなくなったため廃止した。skill が description で自動起動する。）

### 12.3 別プロジェクトへの導入

推奨はリポジトリ直下の `install-strcodec.ps1`（ワークスペースのルートで `irm https://raw.githubusercontent.com/YokeSin/strcodec/main/install-strcodec.ps1 | iex`、またはクローンから `.\install-strcodec.ps1 -Workspace <dir>`）。ツールと skills のコピー、`settings.json` への hooks のマージ（既存 hooks 保持、バックアップ作成）、`AGENTS.md` の作成または追記、`.gitignore` の追記、MCP 登録の確認、`python-info` / `status` による動作確認を行い、再実行で更新になる。手動で行う場合:

1. `.bob/strcodec/`、`.bob/skills/spss-str-decode/`、`.bob/skills/spss-str-rebuild/`、`.bob/skills/_shared/strcodec-reference.md`、`.bob/settings.json`（hooks 部分）、`AGENTS.md` の該当節をコピー。
2. `spss-clemb-mcp` / `ibm-docs-mcp` を導入して `.bob/mcp.json` に設定する（手順は各リポジトリ https://github.com/hkwd/spss-clemb-mcp / https://github.com/hkwd/ibm-docs-mcp を参照）。
3. `.\.bob\strcodec\strcodec.cmd python-info` と `status` で Python と clemb の解決を確認（Python の追加インストールは不要）。
4. グローバル化する場合は `~/.bob/skills/`、`~/.bob/settings/settings.json` に置き、hook の `command` を絶対パス（`%USERPROFILE%\.bob\strcodec\strcodec.cmd hook ...`）にする。

### 12.4 バージョン管理の指針

- `.strcode/` は派生物なので、`.nod` を含めて再生成できます。コミットする場合は `stream.py` と `summary.md` が差分レビューに向いています（`generated_raw.py` は変数名が安定していますが冗長）。
- 再構築した `.str` は `_rebuilt` サフィックスで元と区別されます。
- 同梱の `.gitignore` は次を除外します。`*.str` / `*.nod` は業務データを含み得るため既定で除外しており、共有するものは明示的に追加します（`!path/to/x.str`）。

  ```
  *.strcode/            デコード成果物（ナゲット .nod を含む）
  *_rebuilt.str         再構築出力
  .bob/strcodec/logs/
  .bob/strcodec/python.path
  __pycache__/
  *.str / *.nod         業務データを含み得るため既定で除外
  !.bob/strcodec/tests/fixtures/**
  ```

- `.bob/mcp.json` には MCP サーバーの絶対パス（個人環境）が入ります。公開時は各自の環境に合わせて書き換えるか、テンプレート化してください。

---

## 13. トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `[strcodec] No usable CPython 3.10+ was found. Tried: ...` | PATH の Python が無いか 3.10 未満で、Modeler 同梱 Python も既定の場所に無い（別ドライブ・別バージョン） | CPython 3.10 以上を入れる（spss-clemb-mcp 用のもので可）か、`strcodec.cmd python-info` で候補と判定を見て `STRCODEC_PYTHON` / `.bob/strcodec/python.path` に python.exe を指定 |
| hook が何も注入しない | プロンプトに実在する `.str` のパス/ファイル名が無い、launcher が Python を解決できない、timeout | `logs/hooks.log` を見る。`.bob\strcodec\strcodec.cmd status` を手で実行して起動確認 |
| `decode failed: clemb extraction failed (rc=...)` | clemb 起動失敗、ライセンス、`.str` が壊れている | `<stem>.strcode/_extract.log` と `logs/strcodec.log` の末尾。`===STRCODEC_ERROR===` 行に例外 |
| `timed out waiting for another decode` | 同じファイルを別プロセス（prewarm）がデコード中 | 待って再実行。`.strcode/.lock` が残っていれば削除 |
| `SyntaxError: encoding declaration in Unicode string` | 手で `# -*- coding` を足した | 消す（strcodec 経由なら自動除去） |
| `Module or method too large` | 分割が足りない巨大ストリーム | `config.json` の `chunk_statements` / `chunk_max_chars` / `big_literal_chars` を下げる |
| `NullPointerException`（ナゲット接続後） | `NUGGET` を `createAt("applyxxx")` に書き換えた | マーカーに戻す |
| report に `path not found` | データ/出力パスがこの環境に無い | `--map`。`$CLEO_DEMOS` 等は無視してよい |
| validation failed だが saved=true | データが無い、ナゲットの入力フィールド不足 | `.str` は保存済み。データ配置か `--map`、必要なら `--retrain` |
| `stream.py is not parseable` | 編集で構文が壊れた | 行番号を見て括弧・引用符・`u""` を確認 |
| verify が DIFFERENT | 意図した変更（追加/削除）か、setter 失敗 | report の failures と verify の差分行を突き合わせる |
| `.nod could not be saved` | 保存先の権限、特殊ノード | `decode --force`。ナゲットは `--retrain` で代替 |
| コンソール窓が一瞬出る | 旧版 | `CREATE_NO_WINDOW` 対応済み。`config.json` は変更不要 |

---

## 14. 制約・既知の問題・今後の拡張

- `JythonGenerator` は IBM 非公開 API。Modeler のバージョン更新で挙動が変わる可能性があります（`meta.json` に Modeler 版を記録）。
- フォールバックで Modeler 同梱 CPython を外部ツールに使うことは IBM のサポート範囲外です。そのため既定は PATH の Python とし、同梱版は固定パスに依存せず（バージョンをグロブ列挙）、明示指定（`STRCODEC_PYTHON` / `python.path`）と診断（`python-info`）を用意しています。同梱版の実機検証済みは 19.0（CPython 3.10.7）のみで、18.5〜18.x は対応想定。launcher は Windows 専用です。
- スーパーノードは丸ごと移植のみ（内部の編集は非対応）。拡張案: `getChildDiagram()` に対する `createAt` と `linkFromInputConnector` / `linkToOutputConnector` で内部を再構築する。
- `unknownprocess` / `unknownterminal`（拡張未導入のノード）は `.nod` 移植でのみ再現できます。
- ストリーム単位の設定（日付/時刻形式、ストリームスクリプト、パラメータ、`script_language`、注釈）は `stream.py` 先頭の「stream settings」セクションから復元します（0.3.0 で対応）。キャンバス状態（`min_canvas_*` 等）は対象外です。
- hook の同期デコードは初回 15〜25 秒のブロッキングを伴います。prewarm が先に走っていればキャッシュで即時です。
- Bob 本体での hook 出力の見え方・ブロック理由の可視性は未確認（§6.4）。
- 拡張案: 他エージェント（Claude Code 等、hook 機構を持つもの）向けの設定例。`hook prompt` / `hook guard-read` は stdin JSON の形式が合えばそのまま使えます。

---

## 15. 用語集

| 用語 | 意味 |
|---|---|
| `.str` | SPSS Modeler ストリームファイル（バイナリ） |
| `.nod` | `saveNodeToFile` で保存したノード単体のファイル。ナゲットの実体を運ぶ |
| ナゲット / applier | 学習済みモデルを適用するノード（`applyc50` 等）。Modeler スクリプト API では ModelApplier |
| builder | モデル作成ノード（`c50`, `apriori` 等）。ModelBuilder |
| スーパーノード | ノード群を 1 つに畳んだノード（`process_super` 等）。中に SuperNodeDiagram を持つ |
| JythonGenerator | GUI「スクリプトへ貼り付け」の実装。`generateStreamFragment` で再構築コードを返す |
| clemb.exe | Modeler のバッチ実行体。`-script x.py -execute` で standalone スクリプトを実行 |
| 正規化（normalize） | Generator 出力を決定的で編集しやすい `stream.py` に整える処理 |
| マーカー | `NUGGET` / `SUPERNODE` / `OPAQUE`。`stream.py` 内で特殊ノードを表す関数呼び出し |
| センチネル | `===STRCODEC_RESULT===` / `===STRCODEC_REBUILD===`。clemb 出力から結果を機械的に拾うための行 |
| prewarm | 事前デコード。SessionStart 時に裏で走らせる |
| launcher | `.bob/strcodec/strcodec.cmd`。CPython 3.10+（既定は PATH の Python、無ければ Modeler 同梱版）を解決して隔離フラグ付きで CLI/hook を起動する Windows バッチ |
| SourceSegmentCache | `transform.py` のビルド単位キャッシュ。`ast.get_source_segment()` と同じ意味論でソース断片を返す（3.10 での 90 秒 → 1 秒） |
| benign（無害な失敗） | Range フィールドの `values=[None,None]` 拒否のような、実行に影響しない setter 失敗 |

---

## 付録 A: 生成物の実例

### A.1 summary.md（同梱サンプル campaign_response、抜粋）

```
# campaign_response.str — SPSS Modeler stream (8 nodes / 7 links)
source: <workspace>/samples/campaign_response.str | sha256: 3948012b4cc5 | decoded: 2026-09-13 18:05:09 | Modeler: ServerVersionMajor=19 ...
decoded: samples/campaign_response.strcode/stream.py (142 lines, canonical editable Jython) | .../structure.json | .../summary.md
nuggets: applyc50_node1 | supernodes: none | stream name: campaign_response | execute_method: Normal | parameters: 0

## ノード一覧 (data-flow order)
| var | type | label | @(x,y) | kind | key settings |
| variablefile_node1 | variablefile | 顧客データ | (78,97) | source | custom_name=u"顧客データ"; full_filename=u"C:/Users/Public/strcodec-sample/sample_custom… |
| derive_node1 | derive | 訪問あたり単価 | (210,97) | process | custom_name=u"訪問あたり単価"; new_name=u"spend_per_visit"; formula_expr=u"spend / visits" |
| derive_node2 | derive | 優良顧客 | (342,97) | process | custom_name=u"優良顧客"; new_name=u"heavy_user"; result_type=u"Flag"; flag_expr=u"'visits' > 12 and 'membership' == \"Y\"" |
| type_node1 | type | データ型 | (462,97) | process | target=responded; typed_fields=8 |
| c50_node1 | c50 | 応答予測 | (462,217) | builder | model_name=u"応答予測" |
| applyc50_node1 | applyc50 | 応答予測 | (594,97) | applier | custom_name=u"応答予測" |
| analysis_node1 | analysis | 精度分析 | (714,37) | terminal |  |
| table_node1 | table | テーブル | (714,157) | terminal |  |

## データフロー
variablefile_node1 "顧客データ"
└─ derive_node1 "訪問あたり単価"
   └─ derive_node2 "優良顧客"
      └─ type_node1 "データ型"
         ├─ c50_node1 "応答予測" [builder]
         └─ applyc50_node1 "応答予測" [nugget]
            ├─ analysis_node1 "精度分析"
            └─ table_node1 "テーブル"
## 入出力パス
- variablefile_node1.full_filename = C:/Users/Public/strcodec-sample/sample_customers.csv  (exists)
## モデル
- builder c50_node1 (c50) "応答予測" model_name=応答予測
- nugget applyc50_node1 (applyc50) "応答予測" builder=c50_node1 nod=nuggets/applyc50_node1.nod algorithm=C5
## CLEM 式 / 条件
- derive_node1.formula_expr = spend / visits
- derive_node2.flag_expr = 'visits' > 12 and 'membership' == "Y"
```

### A.2 stream.py（抜粋）

```python
# ---- stream settings | name: campaign_response ----
stream.setPropertyValue("script_language", u"Python")

# ---- variablefile_node1 | variablefile | "顧客データ" | @(78, 97) | source
# original id: id5DR11JXTLNY4
variablefile_node1 = stream.createAt("variablefile", u"顧客データ", 78, 97)
variablefile_node1.setPropertyValue("use_custom_name", True)
variablefile_node1.setPropertyValue("full_filename", u"C:/Users/Public/strcodec-sample/sample_customers.csv")
variablefile_node1.setPropertyValue("custom_name", u"顧客データ")

# ---- derive_node2 | derive | "優良顧客" | @(342, 97) | process
derive_node2 = stream.createAt("derive", u"優良顧客", 342, 97)
derive_node2.setPropertyValue("result_type", u"Flag")
derive_node2.setPropertyValue("flag_expr", u"'visits' > 12 and 'membership' == \"Y\"")
derive_node2.setPropertyValue("new_name", u"heavy_user")

# ---- applyc50_node1 | applyc50 | "応答予測" | @(594, 97) | applier
# original id: id0X61ZFDGZ32L
applyc50_node1 = NUGGET("applyc50", u"応答予測", 594, 97, nod=u"nuggets/applyc50_node1.nod", builder="c50_node1", input="type_node1")
# internal ids (not restored; Modeler regenerates them): updating_node_id=u"id8JH1ZEKMQZPR", refresh_link_state=u"TurnOn", ...
applyc50_node1.setPropertyValue("use_custom_name", True)
applyc50_node1.setPropertyValue("custom_name", u"応答予測")

# ---- links ----
stream.link(variablefile_node1, derive_node1)
stream.link(derive_node1, derive_node2)
stream.link(derive_node2, type_node1)
stream.link(type_node1, c50_node1)
stream.link(type_node1, applyc50_node1)
stream.link(applyc50_node1, analysis_node1)
stream.link(applyc50_node1, table_node1)
```

このサンプルは `use_custom_name` を明示的に立てているので補助行は出ませんが、元のストリームで
`custom_name` だけが設定されていた場合は `flag_fixups` が
`… .setPropertyValue("use_custom_name", False)  # flag was not set in the original: keep the automatic label`
を追記します（§9.2）。

### A.3 再構築スクリプトの実行ログ末尾

`samples/example-session.md` の編集（条件抽出ノードの追加）を実行したときの記録です。

```
[strcodec] created new stream: campaign_response
[strcodec] nugget inserted from nuggets/applyc50_node1.nod: 応答予測
[strcodec] VALIDATE {'var': 'variablefile_node1', 'ok': True}
[strcodec] VALIDATE {'var': 'applyc50_node1', 'ok': True}
===STRCODEC_REBUILD=== {"saved": true, "nodes": 9, "links": 8, "expected_nodes": 8, "expected_links": 7, "fails": 0, "warnings": 0, "validation_failed": 0, "elapsed_ms": 1505}
[strcodec] saved: <workspace>/samples/campaign_response_members.str
```

clemb 側のログ（`rebuild/<stem>_rebuild.log`）には検証実行の様子が残ります。絞り込みが効いて
レコードが 200 件から 92 件になっていることが確認できます。

```
警告: 「画面に出力」を実行すると、ノード _strcodec_validate_applyc50_node1 (11 フィールド、92 レコード) 内の…
警告: フィールド 'membership' には値が 1 つしかありません。
情報: ストリーム実行の成功
```

### A.4 verify の出力（意図的に変更した場合の例）

```
RESULT: STRUCTURE_DIFFERENT
nodes: campaign_response.str=8, campaign_response_members.str=9
  only in campaign_response_members.str: select "会員のみ" @(402,97) x1
links: campaign_response.str=7, campaign_response_members.str=8
  only in campaign_response.str: derive "優良顧客" @(342,97) -> type "データ型" @(462,97) x1
  only in campaign_response_members.str: derive "優良顧客" @(342,97) -> select "会員のみ" @(402,97) x1
  only in campaign_response_members.str: select "会員のみ" @(402,97) -> type "データ型" @(462,97) x1
properties: 1 node(s) with different values, 0 stream setting(s) differ
  type "データ型" @(462,97):
    values[u"membership"]: campaign_response.str=[u"N", u"Y"] | campaign_response_members.str=[u"Y"]
    values[u"spend"]: campaign_response.str=[11.45, 476.28] | campaign_response_members.str=[20.42, 476.28]
```
→ 追加した 1 ノードとつなぎ替えた 3 本のリンクだけが差分。`membership` の値域が絞り込みで
`["N","Y"]` から `["Y"]` に変わっており、意図どおりに効いていることも読み取れる。

なお開発初期には、`custom_name` を設定すると `use_custom_name` が副作用で ON になるために
ラベルが `健康的` と `healthy` で食い違う差分が出たことがあり、`flag_fixups`（§9.2）を
追加して解消しています。

---

## 付録 B: Modeler スクリプト API メモ（今回使ったもの）

| API | 用途 | 備考 |
|---|---|---|
| `modeler.script.session()` | セッション（batch では ComponentEnvironment） | `JythonGenerator(session)` の引数 |
| `session.openProcessorStream(FileInputStream(File(p)), True)` | `.str` を開く | `taskrunner.openStreamFromFile(p, True)` でも可 |
| `session.getTaskRunner()` | TaskRunner | `createStream`, `saveStreamToFile`, `saveNodeToFile`, `insertNodeFromFile`, `openModelFromFile`, `saveModelToFile`, `exportModelToFile` 等 |
| `JythonGenerator.generateStreamFragment(List<Node>)` | 再構築コード生成 | 非公開 API。リンクは両端がリストにある場合のみ出力 |
| `stream.iterator()`, `predecessorAt/Count`, `successorAt/Count` | ノードとリンクの列挙 | 順序は非決定的 → ソート |
| `node.getID/getTypeName/getLabel/getXPosition/getYPosition/getAnnotation/getToolTipText/getModifiedSlotProperties` | ノード情報 | `getName()` は引数必須で使えない |
| `node.getChildDiagram()` | スーパーノード内部 | `SuperNodeDiagram`（`getInputConnector`, `linkFromInputConnector`, `linkToOutputConnector`） |
| `stream.createAt(type, label, x, y)`, `stream.link(a, b)`, `stream.delete(node)` | 構築 | |
| `builder.run(results)`, `stream.createModelApplierAt(results[0], label, x, y)` | 再学習経路 | `run()` はナゲットを自動挿入する |
| `node.setXYPosition(x, y)` | 位置変更 | 移植後の座標合わせ |
| `stream.getParameterNames()`, `getPropertyValue("execute_method"/"script"/"encoding")` | ストリーム情報 | |
