# RequirementViewer

## 概要

- 要求図
- S&Tツリー
- 現状ツリー

ライクなダイアグラムの表示・編集をすることができます。

## 環境構築

## Pythonライブラリのインストール

`requirements.txt`を使ってインストールします。

```
pip install -r requirements.txt
```

### configファイルの作成

`setting`フォルダにある`default_config.json`を`config.json`として同フォルダ内にコピーします。  
その後、`config.json`の各項目を設定します。

- `plantuml``
  - svg画像を取得できるように設定します。
  - デフォルトでは、PlantUMLの公式サーバで処理を行います。
  - 機密情報を扱う場合には、ローカルサーバを利用するようにしてください。
- `viewer_height`
  - 画像表示部の高さを設定します。
  - ご利用の画面サイズに合わせて設定してください。
- `upstream_filter_max`, `downstream_filter_max`
  - フィルタ機能において、あるエンティティから上流・下流にいくつのエンティティを表示するかの最大値を設定します。
- `requiremnt_data`
  - 要求図のデータパスを設定します。
- `strategy_and_tactics_data`
  - S&Tツリーのデータパスを設定します。
- `current_reality_tree_data`
  - 現状ツリーのデータパスを設定します。

### PlantUMLをローカル実行する場合 (optional)

#### `Java`のセットアップ

画像のプロットにPlantUMLを使用しています。  
ローカルでPlantUMLを実行する場合は`Java`のインストールが必要です。

#### PlantUMLの配置

PlantUMLの公式サイトから`jar`ファイルを取得し、RequirementViewerフォルダ直下に`plantuml.jar`として配置します。

## 実行

### 要求図ビューア

```
streamlit run app.py
```

### S&Tツリービューア

```
streamlit run strategy_and_tactics.py
```

### 現状ツリービューア

```
streamlit run current_reality_tree.py
```

