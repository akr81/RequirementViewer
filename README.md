# RequirementViewer

## 概要

本ツールでは、以下の思考ツールライクなダイアグラムの表示・編集をすることができます。

- 要求図 (Requirement Diagram)
- プロセスフロー図 (Process Flow Diagram)
- 現状ツリー (Current Reality Tree)
- クラウド (Evaporating Cloud)
- S&Tツリー (Strategy and Tactics Tree)

## 環境構築

### Pythonライブラリのインストール

`uv`パッケージマネージャーを使用してインストールします。

```bash
uv sync
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

```bash
uv run streamlit run app.py
```

---

## その他の機能

本ツールには以下の機能も実装されています。

### 1. 接続モード

ダイアグラム上のノードを **2回連続でクリック** すると「接続モード」に切り替わります。
この状態で別のノードをクリックすると、ノード間にエッジ（関係）を追加（既存の場合は削除）することができます。

### 2. UI上でのファイル操作

`data/` または `sample/` にある既存ファイルを選択するほか、画面上のUIから新しいファイル（.hjson）を作成し、編集対象のデータを切り替えることができます。

### 3. データ埋め込みPNGの保存とインポート

現在表示されている図のデータ（.hjson）を埋め込んだPNG画像を保存できます。
また、そのPNG画像をツールにインポートすることで、元のデータを復元できます。

### 4. PlantUMLローカルサーバの自動起動設定

ローカル環境でPlantUMLを実行する場合、`config.hjson` の `plantuml` にローカルのURL（例: `http://localhost:8080`）を設定すると、空きポートを探してバックグラウンドでローカルサーバが起動します。
