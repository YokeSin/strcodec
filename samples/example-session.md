# 例: IBM Bob でサンプルストリームを読み、編集して作り直す

`campaign_response.str` に対して実際に行った会話の記録です（IBM Bob 2.1.0 / SPSS Modeler 19.0 / strcodec 0.3.1、2026-09-13）。ワークスペースの絶対パスは `<workspace>` に置き換えてあります。出力は実際のものです。

---

## 1. 概要を聞く

**ユーザー**

```
@samples\campaign_response.str このストリームの概要を教えて
```

**エージェント**（skill `spss-str-decode` → `execute_command`）

```
.bob\strcodec\strcodec.cmd decode "samples\campaign_response.str"
```

`.str` そのものは読まず、hook と skill の案内に従って decode を実行し、`summary.md` を読んで回答しています。返ってきた解説（抜粋）:

> 顧客データを読み込み、特徴量を派生させ、**C5.0 決定木モデル**でキャンペーン応答（`responded`）を予測・評価するストリームです。
>
> ```
> variablefile_node1 "顧客データ"
> └─ derive_node1 "訪問あたり単価"
>    └─ derive_node2 "優良顧客"
>       └─ type_node1 "データ型"
>          ├─ c50_node1 "応答予測" [builder]
>          └─ applyc50_node1 "応答予測" [nugget]
>             ├─ analysis_node1 "精度分析"
>             └─ table_node1 "テーブル"
> ```
>
> | var | 種別 | 表示名 | 役割 |
> |---|---|---|---|
> | `variablefile_node1` | source | 顧客データ | CSV 読み込み（`sample_customers.csv`） |
> | `derive_node1` | process | 訪問あたり単価 | `spend_per_visit = spend / visits` |
> | `derive_node2` | process | 優良顧客 | `heavy_user`（フラグ）を派生 |
> | `type_node1` | process | データ型 | フィールド型定義・目的変数 `responded` を設定 |
> | `c50_node1` | builder | 応答予測 | C5.0 モデルを学習 |
> | `applyc50_node1` | applier | 応答予測 | 学習済みナゲットをデータに適用 |
> | `analysis_node1` | terminal | 精度分析 | モデル精度レポート |
> | `table_node1` | terminal | テーブル | 予測結果の確認 |
>
> - **優良顧客フラグ** — CLEM 式: `'visits' > 12 and 'membership' == "Y"` が真のとき `heavy_user = True`
> - **ナゲットあり**: `applyc50_node1.nod`（C5.0 の学習済みモデル）が同梱されており、再学習不要でスコアリングが可能です。
> - **外部ファイル依存**: 入力 CSV は `C:/Users/Public/strcodec-sample/` に依存。別環境では要パス変更。

---

## 2. 編集して作り直させる

**ユーザー**

```
このストリームを、会員（membership が Y）のレコードだけでモデルを適用するように変えてください。
データ型ノードの手前で絞り込む形でお願いします。
```

**エージェント**（skill `spss-str-rebuild`）

1. `samples/campaign_response.strcode/stream.py` を読む
2. `derive_node2` と `type_node1` の間に条件抽出ノードを挿入し、リンクをつなぎ替える
3. `.bob\strcodec\strcodec.cmd rebuild "samples\campaign_response.str" --out "samples\campaign_response_members.str"`
4. spss-clemb-mcp の `execute_clemb` で生成された Jython を実行
5. `report`（`--allow-issues` なしで一度 exit 1 を確認してから付け直し）と `verify`

`stream.py` に追加されたブロックはこれだけです。

```python
# ---- select_node1 | select | "会員のみ" | @(402, 97) | process
select_node1 = stream.createAt("select", u"会員のみ", 402, 97)
select_node1.setPropertyValue("condition", u"membership == \"Y\"")
select_node1.setPropertyValue("mode", u"Include")
```

末尾のリンク節も 1 行が 2 行に変わりました。

```python
stream.link(derive_node2, select_node1)
stream.link(select_node1, type_node1)
```

---

## 3. 実際の出力

### report

```
# rebuild report: campaign_response
- generated script: <workspace>/samples/campaign_response.strcode/rebuild/campaign_response_rebuild.py (561 lines)
- output stream: <workspace>/samples/campaign_response_members.str
- mode: transplant .nod | validate: True | generated: 2026-09-13 18:10:59

## STATUS: SAVED WITH ISSUES
(OK / OK WITH WARNINGS -> exit 0; SAVED WITH ISSUES / FAILED -> exit 1 unless --allow-issues)
| item | value |
|---|---|
| saved | <workspace>/samples/campaign_response_members.str |
| nodes | 9 (expected 8) |
| links | 8 (expected 7) |
| setter/link failures | 0 (+0 known benign) |
| warnings | 0 |
| validation | 2 ok / 0 failed |
| elapsed (inside clemb) | 1505 ms |

ISSUE: node/link counts differ from the decoded original. Expected only if you added/removed nodes in
stream.py (then re-run with --allow-issues); otherwise check the failures below.

## info
- nugget inserted from nuggets/applyc50_node1.nod: 応答予測
```

ノードを 1 つ足したので件数が期待値と違い、`STATUS: SAVED WITH ISSUES`（exit 1）になります。意図した変更だと確認したうえで `--allow-issues` を付け直す、という流れです。学習済みモデルは `.nod` から移植されているので、**再学習は起きていません**。

### verify

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
    field_metadata[u"membership"]: … [u"N", u"Y"] … | … [u"Y"] …
    （customer_id / spend_per_visit の範囲なども同様に変化）
```

差分は「追加した 1 ノード」と「つなぎ替えた 3 本のリンク」だけです。プロパティ側では、絞り込みの結果として `membership` の値が `["N", "Y"]` から `["Y"]` に変わっており、意図どおりに効いていることが確認できます。

---

## この例で確認できること

- `.str` を直接読ませなくても、エージェントは要約と正規化 Jython だけでストリームを説明できる
- 編集は `stream.py` に数行足すだけで、ノード型やプロパティ名はエージェントが決めている
- ナゲットは `.nod` から移植されるので、モデルは再学習されない
- 件数が変わる編集では `STATUS: SAVED WITH ISSUES`（exit 1）になり、意図した変更かどうかを人が判断してから `--allow-issues` で通す
- `verify` は構造の差分（終了コード）とプロパティ値の差分（情報）を分けて出す
