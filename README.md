# strcodec — SPSS Modeler `.str` ⇄ Jython codec for coding agents

IBM SPSS Modeler のストリームファイル（`.str`、バイナリ）を、コーディングエージェントが読める **正規化 Jython + 要約** に変換し、その Jython から **元のストリームを再現できる自己完結スクリプト**を生成するツールセットです。IBM Bob IDE 向けの skills / hooks を同梱していますが、CLI 部分は任意のエージェントや手作業でも使えます。機能は以下の 2 つ。

- **decode**: `.str` → `<名前>.strcode/`（要約 `summary.md`、編集用 `stream.py`、`structure.json`、モデルナゲット `.nod`）。エージェントはこれを読んでストリームを説明できる。
- **rebuild**: `stream.py` → Modeler で実行できる Jython → `<名前>_rebuilt.str`。`stream.py` を編集してから rebuild すれば、ストリームの修正・作り直しができる（元ファイルは上書きしない）。`report` / `verify` で結果を確認する。

詳しい仕組み・成果物の仕様・変換ルールの根拠・検証記録は [docs/strcodec-manual.md](docs/strcodec-manual.md) にまとめています。

---

## 前提環境

| 項目             | 要件                                          | 備考                                                                                                                                                               |
| ---------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| OS               | Windows 10/11                                 | launcher は Windows 用（`cmd`）。他 OS は未検証                                                                                                                  |
| IBM SPSS Modeler | Client 18.5 以上（`clemb.exe`、ライセンス） | 実機検証済みは 19.0。18.5〜18.x は「対応想定」                                                                                                                     |
| Python           | CPython 3.10 以上                             | 無い場合は Modeler 同梱の CPython にフォールバック                                                                                                                 |
| IBM Bob IDE      | 任意                                          | skills / hooks を使う場合。CLI だけなら不要                                                                                                                        |
| MCP サーバー     | 任意（推奨）                                  | [spss-clemb-mcp](https://github.com/hkwd/spss-clemb-mcp)（エージェントが Jython を実行）、[ibm-docs-mcp](https://github.com/hkwd/ibm-docs-mcp)（ノード仕様の裏取り） |

Python は 2 種類が関わります。上の CPython は CLI・hooks・変換などのローカル処理用で、`.str` の抽出と再構築の Jython は Modeler 内部の Jython 2.7（`clemb.exe`）で実行されます。詳細はマニュアル §3.2。

## インストール方法

### 方法 A: インストールスクリプトを使う（推奨）

ストリームを扱うワークスペースのルートで PowerShell を開き、次を実行します。

```powershell
irm https://raw.githubusercontent.com/YokeSin/strcodec/main/install-strcodec.ps1 | iex
```

クローン済みなら、そのクローンから入れることもできます。

```powershell
.\install-strcodec.ps1 -Workspace <your-workspace>
```

スクリプトがやること（再実行すると更新になります）:

1. `.bob/strcodec/` と `.bob/skills/{spss-str-decode,spss-str-rebuild,_shared}` をワークスペースにコピー（既存の `python.path`、`logs/`、`config.json` のユーザー設定は保持）
2. `.bob/settings.json` に 3 つの hook をマージ（既存の hooks は残す。変更前に `settings.json.bak-<日時>` を作成）
3. `AGENTS.md` を作成、既にあれば strcodec の節を末尾に追記（1 回だけ）
4. git リポジトリなら `.gitignore` に成果物の除外パターンを追記
5. spss-clemb-mcp / ibm-docs-mcp が Bob に登録済みか確認し、未登録なら各リポジトリの URL を案内（MCP 自体は別途導入）
6. `strcodec.cmd python-info` と `status` で動作確認

`irm | iex` では引数を渡せないので、対象ワークスペースを変えたいときは環境変数 `STRCODEC_WORKSPACE` を先に設定します。ファイルから実行する場合は `-Workspace` / `-Source <クローン>` / `-NoHooks` / `-NoAgentsMd` が使えます。

### 方法 B: 手動で配置する

1. **配置**: このリポジトリの `.bob/` と `AGENTS.md` を、ストリームを扱うワークスペースのルートにコピーします。既存の `.bob/` がある場合は `strcodec/` と `skills/` を追加し、`settings.json` の `hooks` をマージしてください。

   ```
   <your-workspace>/
   ├── AGENTS.md
   ├── .bob/
   │   ├── settings.json          ← hooks 定義（strcodec.cmd 経由で起動）
   │   ├── strcodec/              ← ツール本体（strcodec.cmd = launcher）
   │   └── skills/spss-str-decode/, spss-str-rebuild/, _shared/
   └── (your *.str files)
   ```
2. **Python の確認**: `.\.bob\strcodec\strcodec.cmd python-info` で、どの python.exe が選ばれるかを確認します。解決順は `STRCODEC_PYTHON` → `.bob\strcodec\python.path` → `py -3` → PATH の `python` → Modeler 同梱版（フォールバック）です。特定の Python を使いたいときは `STRCODEC_PYTHON` か `python.path` で指定します（マニュアル §3.2）。
3. **clemb.exe の場所**: 既定パス（`C:\Program Files\IBM\SPSS\Modeler\<版>\bin\clemb.exe`）にあれば設定不要です。違う場合は `.bob/strcodec/config.json` の `"clemb_path"` か環境変数 `SPSS_MODELER_CLEMB_PATH` で指定します（spss-clemb-mcp の設定ファイルも自動で参照します）。
4. **MCP サーバー（任意・推奨）**: エージェントに再構築スクリプトを実行させる／ノード仕様を調べさせる場合は、次の 2 つを導入して `.bob/mcp.json` に登録します。導入手順と設定例はそれぞれのリポジトリを参照してください。

   - https://github.com/hkwd/spss-clemb-mcp
   - https://github.com/hkwd/ibm-docs-mcp
5. **Bob IDE 側**: hooks は `.bob/settings.json` を置くだけで有効になります。skills は既定で起動前に承認を求めるので、毎回の確認を省くには Bob の設定「Auto-approving actions」で Skills を有効にしてください。
6. **動作確認**:

   ```powershell
   cd <your-workspace>
   .\.bob\strcodec\strcodec.cmd status                       # 使用中の Python / clemb、.str の一覧とキャッシュ状態
   .\.bob\strcodec\strcodec.cmd decode path\to\stream.str    # 要約が標準出力に出る（初回 ~20 秒、以後はキャッシュで即時）
   ```

## 使い方

試すだけなら同梱のサンプル（架空の合成データ + C5.0 ナゲット入りストリーム、8 ノード / 7 リンク）が使えます。詳細は [samples/README.md](samples/README.md)。

```powershell
.\.bob\strcodec\strcodec.cmd decode samples\campaign_response.str
```

### Bob IDE 上で

| やりたいこと                           | 入力例                                                          |
| -------------------------------------- | --------------------------------------------------------------- |
| ストリームを説明させる                 | 「`@~.str` を説明して」                                       |
| 修正して作り直す                       | 「`~.str` の … の式を … に変えて `.str` を作り直して」   |
| 別環境から来たストリーム（パスが違う） | 「`x.str` を `--map "C:/old/dir=C:/new/dir"` で作り直して」 |
| モデルを学習し直す                     | 「`x.str` を `--retrain` で作り直して」（データが必要）     |

プロンプトで `.str` に触れると hook が自動でデコードして要約をコンテキストに注入します。セッション開始時にはワークスペース内の `.str` を索引として出し、未デコード分をバックグラウンドでデコードします。エージェントが `.str` を `read_file` しようとするとブロックして代替手順を案内します。

実際の会話と出力（サンプルの概要説明 → 条件抽出ノードを追加して作り直し → report / verify）は [samples/example-session.md](samples/example-session.md) にそのまま置いてあります。

エージェントの典型的な手順は次の通りです（skill `spss-str-decode` / `spss-str-rebuild` に書いてあります）。

1. `decode` して `summary.md` を読む（hook が注入済みならそのまま）。
2. 必要なノードのブロックだけ `stream.py` を読む（`# ---- <var> | <type> | ...` が見出し）。
3. 変更するなら `stream.py` を編集する（1 文 1 行、`u"..."`、`None`、`NUGGET(...)` マーカーは崩さない）。
4. `rebuild` でスクリプトを生成し、spss-clemb-mcp の `execute_clemb` で実行する。
5. `report` と `verify` で確認し、`.str` のパスと結果を報告する。

### CLI

```
.bob\strcodec\strcodec.cmd <command> ...        （Python があれば python .bob/strcodec/strcodec.py <command> でも可）

decode      <file.str> [--force] [--quiet] [--json] [--max-lines N]
            .str をデコードして <stem>.strcode/ を作り、summary.md を表示（キャッシュ有効なら即時）
rebuild     <file.str | dir.strcode> [--out X.str] [--retrain] [--map OLD=NEW]... [--no-validate] [--run]
            [--coding-header] [--allow-stale] [--allow-issues]
            stream.py から再現スクリプト rebuild/<stem>_rebuild.py を生成（--run で clemb 実行 + レポート）。
            元 .str の変更・ツール版の相違・.nod の欠落があると生成を拒否（--allow-stale で続行）。
            --run の終了コードは STATUS OK / OK WITH WARNINGS のとき 0（--allow-issues で保存済みなら 0）。
            --coding-header は Modeler GUI 用で --run と併用不可。
report      <file.str | dir.strcode> [--allow-issues]
            直近の実行結果（rebuild/<stem>_rebuild_result.json）からレポートを生成（終了コードは --run と同じ規則）
verify      <a.str> <b.str> [--force] [--strict]
            2 つのストリームを比較。構造（型・ラベル・座標・リンク）が exit 0 = STRUCTURE_MATCH。
            ノードごとのプロパティ値とストリーム設定の差は一覧表示（--strict で差があれば exit 1）
prewarm     [--background] [--max N] [--root DIR]
            ワークスペース内の未デコード .str をまとめてデコード
status      [--root DIR]
            使用中の Python / clemb と、.str の一覧・キャッシュ状態
python-info / --which
            launcher が選ぶ python.exe と候補一覧
hook        <prompt | session-start | guard-read>
            Bob hooks の入口（stdin に JSON）
```

再現スクリプトの実行は 3 通りです。

| 方法                           | 使い方                                                                                                                                                                                              |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| エージェント（spss-clemb-mcp） | `execute_clemb(script_file=".../rebuild/<stem>_rebuild.py", working_directory=".../<stem>.strcode", log_file=".../rebuild/<stem>_rebuild.log")` — `rebuild` の出力に引数がそのまま表示されます |
| CLI                            | `strcodec.cmd rebuild <file.str> --run`                                                                                                                                                           |
| Modeler GUI                    | ツール > スタンドアロン・スクリプト で`<stem>_rebuild.py` を開いて実行（`--coding-header` 付きで生成すると日本語が安全）                                                                        |

## 仕組み（概要）

```
file.str ──(clemb: JythonGenerator で抽出)──▶ generated_raw.py + structure.json + nuggets/*.nod
         ──(正規化)───────────────────────▶ stream.py       ← エージェントが読む/編集する正本
         ──(要約)─────────────────────────▶ summary.md      ← hook がコンテキストへ注入

stream.py ──(再構築スクリプト生成)──▶ rebuild/<stem>_rebuild.py
          ──(clemb / MCP / GUI で実行)─▶ <stem>_rebuilt.str + 結果 JSON ──▶ report / verify
```

Modeler の GUI にある「ノードをスクリプトへ貼り付け」機能のバックエンド `JythonGenerator` を `clemb.exe` の中から呼び、ストリームを再構築する Jython を得ます。生成物はそのままでは動かないので、薄い後処理層で実行可能にしています。

| 生成物の問題                                                       | strcodec の対処                                                                              |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| リスト要素の`null` が Python の `None` にならない              | トークン単位で`None` に正規化（文字列内は不変）                                            |
| JVM の 64 KB メソッド制限で丸ごと実行できない                      | 40 文ごとの関数に分割、巨大リテラルは JSON 経由                                              |
| モデルナゲットは`createAt` では空になり `NullPointerException` | `.nod` に保存して学習済みモデルごと移植（再学習不要。`--retrain` で Builder 再実行も可） |
| ナゲットの内部 ID は元ストリーム固有                               | 復元せず Modeler に再採番させる                                                              |
| データパスが実行環境と違う                                         | 存在チェックと`--map OLD=NEW` による接頭辞置換                                             |
| 一部の setter が例外になる                                         | 失敗を記録して続行し、既知の無害なものはレポートで別枠に                                     |

各処理の詳細（抽出テンプレート、正規化ルール、再構築スクリプトの構造とランタイム、hooks と skills の中身、成果物ファイルの仕様、設定項目、変換ルールの根拠と検証記録）はマニュアルの §2〜§11 を参照してください。

## 生成される成果物

`<stem>.strcode/`（`.str` と同じフォルダ）に、`summary.md`（要約）、`stream.py`（編集用 Jython）、`structure.json`（機械可読の構造）、`nuggets/*.nod` などのモデル実体、`rebuild/`（再現スクリプト・ログ・結果 JSON・レポート）、`meta.json`（キャッシュ鍵）が作られます。再構築した `.str` は既定で `<stem>_rebuilt.str` です。各ファイルの仕様はマニュアル §8。

`.strcode/` は派生物なので再生成できます。同梱の `.gitignore` は `*.strcode/`、`*_rebuilt.str`、ログ、個人設定に加えて `*.str` / `*.nod` も既定で除外しています（業務データを含み得るため。共有するものは明示的に追加してください）。

## リポジトリ構成

```
.
├── README.md
├── install-strcodec.ps1           インストール／更新スクリプト（方法 A）
├── AGENTS.md                      エージェント向け常設ルール
├── docs/strcodec-manual.md        詳細説明書
├── samples/                       動作確認用サンプル（合成データ + C5.0 ナゲット入りストリーム）
└── .bob/
    ├── settings.json              hooks（strcodec.cmd hook ... で起動）
    ├── skills/                    spss-str-decode, spss-str-rebuild, _shared/strcodec-reference.md
    └── strcodec/                  ツール本体（CPython 3.10+、標準ライブラリのみ）
        ├── strcodec.cmd           Windows launcher
        ├── strcodec.py            CLI
        ├── jython/                clemb 内で動く抽出テンプレートと再構築ランタイム（Jython 2.7）
        ├── hooks/                 Bob の 3 つの hook
        └── tests/                 ユニットテスト（python -m unittest discover -s .bob/strcodec/tests）
```

モジュールごとの役割はマニュアル §3。設定項目（`.bob/strcodec/config.json`）は §11。

## 制限事項・取り扱い上の注意

- Modeler のバージョンにより存在・挙動が変わる可能性があります（19.0 で検証）。
- launcher は Windows 専用です。他 OS では `python .bob/strcodec/strcodec.py` を直接使ってください（未検証）。
- スーパーノードは `.nod` で丸ごと移植します。内部の編集は未対応です。拡張ノードなど Modeler が `unknown*` として読むノードも `.nod` 移植でのみ再現できます。
- 初回デコードは clemb の起動を含めて 15〜25 秒かかります（以後はキャッシュ）。プロンプト送信時に同期で走るため、その間は待ちになります。
- `.strcode/` にはフィールド名、値の範囲、データパス、CLEM 式、`.nod`（学習済みモデル）が含まれます。機密データを扱うストリームの成果物を共有・コミットする際は内容を確認してください。
- hooks とツールはユーザー権限で clemb.exe を起動します。`.str` は開くだけですが、`rebuild` の検証ステップと `--retrain` はデータソースを実際に読み込みます（`--no-validate` で検証を省略できます）。

既知の問題の全体像と拡張案はマニュアル §14。

## トラブルシューティング

| 症状                                             | 見るところ・対処                                                                                                                                       |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `No usable CPython 3.10+ was found`            | CPython 3.10 以上を入れる（spss-clemb-mcp 用のもので可）か、`strcodec.cmd python-info` で候補を確認して `STRCODEC_PYTHON` / `python.path` で指定 |
| hook が何も注入しない                            | `.bob/strcodec/logs/hooks.log`。`strcodec.cmd status` を手で実行して起動できるか確認                                                               |
| `decode failed: clemb extraction failed`       | `<stem>.strcode/_extract.log` の末尾（ライセンス、パス、壊れた `.str`）                                                                            |
| レポートに`path not found` / validation failed | データがその環境に無い。`--map OLD=NEW` でパスを置換。`.str` 自体は保存済み                                                                        |

その他の症状はマニュアル §13。

## ライセンス

[MIT License](LICENSE) です。本リポジトリのコード（CPython 側のツール、Jython テンプレート、launcher、インストールスクリプト、skills、hooks、ドキュメント）は標準ライブラリだけで書かれており、第三者のコードは含みません。

IBM SPSS Modeler 本体、そのサンプルストリームとサンプルデータ（`Demos` フォルダ）、同梱 Python およびドキュメントは IBM の権利物であり、本リポジトリには含まれません（`.gitignore` で `*.str` / `*.nod` を除外しています）。`samples/` のストリームとデータ、および `tests/fixtures/` は、すべて架空の合成データです（乱数で生成した CSV を SPSS Modeler 19.0 に読ませて作成しました）。

## 免責・商標

- 本プロジェクトは IBM とは無関係の個人プロジェクトであり、IBM のサポート対象ではありません。
- 将来の Modeler で動作しなくなる可能性があります。自己責任でご利用ください。
- IBM、SPSS、IBM SPSS Modeler、IBM Bob は IBM Corporation の商標または登録商標です。

## 謝辞

- [hkwd/spss-clemb-mcp](https://github.com/hkwd/spss-clemb-mcp) — clemb.exe を MCP から実行する仕組み（clemb の呼び出し方の参考にしました）
- [hkwd/ibm-docs-mcp](https://github.com/hkwd/ibm-docs-mcp) — IBM ドキュメントの検索
