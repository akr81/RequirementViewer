# RequirementViewer

## 概要

本ツールでは、以下の思考ツールライクなダイアグラムの表示・編集をすることができます。

- 要求図 (Requirement Diagram)
- プロセスフロー図 (Process Flow Diagram)
- 現状ツリー (Current Reality Tree)
- クラウド (Evaporating Cloud)
- S&Tツリー (Strategy and Tactics Tree)

## 環境構築

## Pythonライブラリのインストール

`requirements.txt`を使ってインストールします。

```
pip install -r requirements.txt
```

### configファイルの作成

`setting`フォルダにある`default_config.hjson`を`config.hjson`として同フォルダ内にコピーします。  
その後、`config.hjson`の各項目を設定します。

- `plantuml`
  - デフォルトでは、PlantUMLの公式サーバで処理を行います。
  - 機密情報を扱う場合には、ローカルサーバを利用するようにしてください。
- `viewer_height`
  - 画像表示部の高さを設定します。
  - ご利用の画面サイズに合わせて設定してください。
- `upstream_filter_max`, `downstream_filter_max`
  - フィルタ機能において、あるエンティティから上流・下流にいくつのエンティティを表示するかの最大値を設定します。

以下の項目はデフォルトのままで問題ありません。

- `requirement_data`
  - 要求図のデータパスを設定します。
- `current_reality_tree_data`
  - 現状ツリーのデータパスを設定します。
- `process_flow_diagram_data`
  - プロセスフロー図のデータパスを設定します。
- `evaporating_cloud_data`
  - クラウドのデータパスを設定します。
- `strategy_and_tactics_data`
  - S&Tツリーのデータパスを設定します。

### PlantUMLをローカル実行する場合 (optional)

初期の状態では、PlantUMLの公式サーバで処理を行います。  
重要な情報を扱う際には、ローカルサーバを利用するようにしてください。

#### `Java`のセットアップ

画像のプロットにPlantUMLを使用しています。  
ローカルでPlantUMLを実行する場合は`Java`のインストールが必要です。

#### PlantUMLの配置

PlantUMLの公式サイトから`jar`ファイルを取得し、RequirementViewerフォルダ直下に`plantuml.jar`として配置します。

## 実行

コマンドプロンプト/ターミナルで以下のコマンドを実行してください。

```
streamlit run app.py
```
