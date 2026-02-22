"""後方互換性を保つ再エクスポートラッパー。

utility.py は責務ごとに以下のモジュールに分割されました:
  - src.plantuml_service : PlantUMLサーバー通信・エンコード
  - src.file_io          : ファイル入出力・設定管理
  - src.data_helpers     : データ変換・マッピング
  - src.text_helpers     : テキスト処理
  - src.png_import       : PNGファイルへのhjson埋め込み・抽出

新しいコードでは個別モジュールから直接インポートすることを推奨します。
"""
from src.plantuml_service import *  # noqa: F401,F403
from src.file_io import *           # noqa: F401,F403
from src.data_helpers import *      # noqa: F401,F403
from src.text_helpers import *      # noqa: F401,F403
from src.png_import import *        # noqa: F401,F403
