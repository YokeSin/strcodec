# samples — strcodec の動作確認用サンプル

strcodec の decode / rebuild / report / verify を試すための、**完全に架空のデータとストリーム**です。IBM SPSS Modeler 付属のサンプル（`Demos` フォルダ）は含みません。

| ファイル | 内容 |
|---|---|
| `sample_customers.csv` | 架空のオンラインショップの顧客 200 件（`customer_id`, `age`, `region`, `membership`, `visits`, `spend`, `responded`）。乱数で生成した合成データで、実在の個人・企業とは無関係です |
| `campaign_response.str` | 上の CSV を読み、キャンペーン応答（`responded`）を C5.0 で予測するストリーム（8 ノード / 7 リンク、モデルナゲット入り） |
| `example-session.md` | このサンプルを IBM Bob に読ませ、条件抽出ノードを追加して作り直させたときの会話と、その report / verify の実出力 |

## ストリームの構成

```
顧客データ (variablefile)            sample_customers.csv を読む
└─ 訪問あたり単価 (derive)            spend / visits
   └─ 優良顧客 (derive, Flag)         'visits' > 12 and 'membership' == "Y"
      └─ データ型 (type)              responded を目的変数（customer_id は役割なし）
         ├─ 応答予測 (c50)            モデル作成ノード（builder）
         └─ 応答予測 (applyc50)       モデルナゲット（applier）
            ├─ 精度分析 (analysis)
            └─ テーブル (table)
```

ナゲットは学習済みモデルを含むので、**データが無くても** decode / rebuild できます（`.nod` として取り出し、そのまま移植されます）。

## データのパス

`campaign_response.str` の入力ファイルは `C:/Users/Public/strcodec-sample/sample_customers.csv` を指しています（個人のフォルダ名を含めないための共有パスです）。実際にストリームを実行したり、rebuild の検証ステップを通したりする場合は、次のどちらかを行ってください。

1. `sample_customers.csv` を `C:\Users\Public\strcodec-sample\` にコピーする（管理者権限は不要）
2. rebuild 時にパスを置き換える

   ```powershell
   .\.bob\strcodec\strcodec.cmd rebuild samples\campaign_response.str --run --map "C:/Users/Public/strcodec-sample=<このフォルダの絶対パス>"
   ```

どちらもしない場合、decode と rebuild 自体は成功し、レポートに `path not found` の警告と検証（validation）の失敗が出ます。

## 試す

```powershell
# 読む
.\.bob\strcodec\strcodec.cmd decode samples\campaign_response.str

# 作り直す（clemb を直接実行）→ samples\campaign_response_rebuilt.str
.\.bob\strcodec\strcodec.cmd rebuild samples\campaign_response.str --run

# 元と比べる
.\.bob\strcodec\strcodec.cmd verify samples\campaign_response.str samples\campaign_response_rebuilt.str
```

IBM Bob 上なら「`@campaign_response.str` を説明して」と聞くだけで、hook が要約をコンテキストへ入れます。

## 作り方

乱数で生成した CSV を SPSS Modeler 19.0 に読ませ、C5.0 を実際に学習させて作りました。ナゲットにはその学習済みモデルが入っています。IBM 付属のサンプルストリームやサンプルデータは使っていません。
