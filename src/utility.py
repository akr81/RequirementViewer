import streamlit as st
import subprocess
import atexit
import zlib
import requests
import hjson
import json
import base64
import os
import shutil
import datetime
import copy
import tempfile
import time
import socket
from urllib.parse import urlparse
from contextlib import contextmanager
from typing import Tuple, List, Dict, Any, Optional


@contextmanager
def log_time(label: str):
    """実行時間のロギングを行うコンテキストマネージャ。"""
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"[{label}] Execution time: {elapsed_time:.4f} seconds")


# PlantUMLサーバをバックグラウンドプロセスとして起動し、キャッシュする
def find_available_port(start_port: int, max_attempts: int = 20) -> int:
    """指定されたポートから開始して、利用可能なポートを見つける。

    Args:
        start_port (int): 探索開始ポート
        max_attempts (int): 最大試行回数

    Returns:
        int: 利用可能なポート番号
    
    Raises:
        RuntimeError: 利用可能なポートが見つからない場合
    """
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            result = sock.connect_ex(("localhost", port))
            if result != 0:  # 0以外なら接続不可＝空いている可能性が高い
                return port
    raise RuntimeError(
        f"利用可能なポートが見つかりませんでした (探索範囲: {start_port}-{start_port + max_attempts - 1})"
    )


@st.cache_resource
def start_plantuml_server(config_data: dict = None) -> str:
    """PlantUMLサーバーをバックグラウンドプロセスとして起動する。
    
    Args:
        config_data (dict): 設定データ。plantumlのURL設定を含む。指定がない場合はデフォルト(8080)を使用。

    Returns:
        str: 起動したPlantUMLサーバーのURL (例: http://localhost:8081)
    """
    # configからポートを取得 (デフォルト 8080)
    start_port = 8080
    base_url = "http://localhost"
    
    if config_data and "plantuml" in config_data:
        try:
            parsed = urlparse(config_data["plantuml"])
            if parsed.port:
                start_port = parsed.port
            if parsed.scheme and parsed.hostname:
                 base_url = f"{parsed.scheme}://{parsed.hostname}"
        except Exception:
            pass  # パースエラー時はデフォルトを使用

    # 空きポートを探す
    try:
        port = find_available_port(start_port)
    except RuntimeError as e:
        st.error(f"PlantUMLサーバの起動に失敗しました: {e}")
        return None

    # plantuml.jarは同一ディレクトリに配置していると仮定
    command = ["java", "-jar", "plantuml.jar", f"-picoweb:{port}"]
    try:
        process = subprocess.Popen(command)
        # プロセス終了時にクリーンアップするため、atexitに登録
        atexit.register(lambda: process.terminate())
        
        runtime_url = f"{base_url}:{port}"
        # 起動直後は接続できない可能性があるため少し待つなどの処理を入れることも検討できるが、
        # Streamlitの起動シーケンス上、リクエストが飛ぶまでには時間があるため現状はそのまま返す
        return runtime_url
    except FileNotFoundError:
        st.error(
            "Javaまたはplantuml.jarが見つかりません。Javaがインストールされているか、plantuml.jarが配置されているか確認してください。"
        )
        return None
    except Exception as e:
        st.error(f"PlantUMLサーバの起動に失敗しました: {e}")
        return None


# PlantUMLサーバ向けのエンコード関数
def encode_plantuml(text: str) -> str:
    """テキストをPlantUMLサーバー用のフォーマットにエンコードする。

    Args:
        text (str): エンコードするテキスト

    Returns:
        str: エンコードされたテキスト
    """
    # UTF-8にエンコードし、zlibでdeflate圧縮
    data = text.encode("utf-8")
    compressed = zlib.compress(data)
    # zlibヘッダー(最初の2バイト)とチェックサム(最後の4バイト)を除去
    compressed = compressed[2:-4]
    return encode64(compressed)


def encode64(data: bytes) -> str:
    """バイトデータをPlantUMLサーバー用のフォーマットにエンコードする。

    Args:
        data (bytes): エンコードするバイトデータ

    Returns:
        str: エンコードされたテキスト
    """
    # PlantUML用のカスタム64エンコードテーブル
    char_map = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
    res = []
    # 3バイトずつ処理し、24ビット整数にまとめる
    for i in range(0, len(data), 3):
        b = data[i : i + 3]
        # 3バイトに満たない場合は0でパディング
        if len(b) < 3:
            b = b + bytes(3 - len(b))
        n = (b[0] << 16) + (b[1] << 8) + b[2]
        # 6ビットごとに分割して、char_mapの文字に変換
        res.append(char_map[(n >> 18) & 0x3F])
        res.append(char_map[(n >> 12) & 0x3F])
        res.append(char_map[(n >> 6) & 0x3F])
        res.append(char_map[n & 0x3F])
    return "".join(res)


# PlantUMLコードからSVG画像を取得する関数
@st.cache_data(show_spinner=False)
def get_diagram(plantuml_code: str, plantuml_server: str, *, png_out=False) -> Any:
    """PlantUMLコードからSVG/PNG図を取得する。

    Args:
        plantuml_code (str): PlantUMLコード
        plantuml_server (str): PlantUMLサーバーのURL

    Returns:
        Any: SVG図のテキスト、またはPNG画像のバイトデータ
    """
    plantuml_server = plantuml_server + "/svg/"  # デフォルトはSVG出力
    if png_out:
        # PNG出力の場合はURLを変更
        plantuml_server = plantuml_server.replace("svg", "png")
        plantuml_code = plantuml_code.replace(
            "@startuml", "@startuml\nskinparam dpi 200\n"
        )
    # PlantUMLサーバ用にエンコード
    encoded = encode_plantuml(plantuml_code)
    url = "".join([plantuml_server, encoded])
    response = requests.get(url)
    if response.status_code == 200:
        if png_out:
            return response.content
        else:
            return response.text
    else:
        st.error("PlantUMLサーバから図を取得できませんでした。")
        st.write(response)
        st.write(url)
        return ""


def load_colors() -> list:
    """JSONファイルから色リストを読み込む。

    Returns:
        list: 色のリスト
    """
    with open("setting/colors.json", "r", encoding="utf-8") as f:
        colors = hjson.load(f)
    return list(colors.keys())


def load_config() -> dict:
    """JSONファイルから設定(config)を読み込む。

    Returns:
        dict: 設定項目の辞書
    """
    if os.path.exists("setting/config.hjson"):
        config_file = "setting/config.hjson"
    else:
        config_file = "setting/default_config.hjson"
    with open(config_file, "r", encoding="utf-8") as f:
        config = hjson.load(f)
    return config


def save_config(config_data: dict):
    """設定(config)をJSONファイルに保存する。

    Args:
        config_data (dict): 設定項目の辞書
    """
    config_file_path = "setting/config.hjson"
    try:
        atomic_write_json(config_file_path, config_data)
    except Exception as e:
        st.error(f"設定ファイルの保存に失敗しました: {e}")


def get_default_data_structure() -> Dict:
    """新規データファイル用のデフォルト構造を返す。"""
    return {"nodes": [], "edges": []}


def list_hjson_files(directory: str) -> List[str]:
    """指定されたディレクトリ内の.hjsonファイルをリストアップする。

    Args:
        directory (str): スキャンするディレクトリ

    Returns:
        List[str]: .hjsonファイル名のリスト
    """
    if not os.path.isdir(directory):
        return []
    return [
        f
        for f in os.listdir(directory)
        if f.endswith(".hjson") and os.path.isfile(os.path.join(directory, f))
    ]


def load_app_data() -> dict:
    """JSONファイルからapp_dataを読み込む。

    Returns:
        dict: app_dataの辞書
    """
    with open("setting/app_data.json", "r", encoding="utf-8") as f:
        app_data = hjson.load(f)
    return app_data


def load_source_data(file_path: str) -> Dict:
    """JSON/HJSONファイルからダイアグラムの元データを読み込む。

    Args:
        file_path (str): 読み込むファイルのパス

    Returns:
        Dict: 元データの辞書
    """
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                source_data = hjson.load(f)
            except Exception as e:
                st.error(f"JSONファイルの読み込みに失敗しました: {file_path}\nError: {e}")
                return []
    else:
        # 存在しない場合は空で始める
        source_data = []

    # 古いフォーマットのデータを新しいフォーマットに変換
    if isinstance(source_data, list):
        temp_data = {"nodes": [], "edges": []}
        for item in source_data:
            temp_node = {}
            for key, value in item.items():
                if key == "relations":
                    for relation in value:
                        temp_relation = {"source": item["unique_id"]}
                        temp_relation.update(relation)
                        temp_data["edges"].append(temp_relation)
                else:
                    temp_node[key] = value
            temp_data["nodes"].append(temp_node)
        source_data = temp_data

    # データロード時に一括で改行のエスケープを解除する
    source_data = recursive_unescape(source_data)

    return source_data


def update_source_data(file_path: str, source_data: Dict):
    """元データをファイルに更新・保存する。

    Args:
        file_path (str): 保存先ファイルのパス
        source_data (Dict): 保存する元データ
    """
    # --- 最後に使用したページをconfigに保存 ---
    if "app_name" in st.session_state and "config_data" in st.session_state:
        current_app_name = st.session_state.app_name
        # config.hjsonに書き込むキーをapp.pyと合わせる
        LAST_USED_PAGE_KEY = "last_used_page"
        st.session_state.config_data[LAST_USED_PAGE_KEY] = current_app_name
        save_config(st.session_state.config_data)
        # デバッグ用にコンソールに出力
        # print(f"最後に使用したページとして '{current_app_name}' を保存しました。")

    # list内の辞書型データをunique_id順に並び替える
    source_data["nodes"].sort(key=lambda x: x["unique_id"])
    source_data["edges"].sort(key=lambda x: x["source"])

    # Remove duplicated edges
    seen_edges = set()
    temp_edges = copy.deepcopy(source_data["edges"])
    filtered_edges = []
    for temp_edge in temp_edges:
        # Convert edge dict to hashable tuple
        edge_tuple = make_hashable(temp_edge)

        if edge_tuple not in seen_edges:
            seen_edges.add(edge_tuple)
            filtered_edges.append(temp_edge)

    source_data["edges"] = filtered_edges

    atomic_write_json(file_path, source_data)

    # for backup
    postfix_file = st.session_state.app_data[st.session_state.app_name]["postfix"]
    os.makedirs("back", exist_ok=True)
    filename = (
        datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{postfix_file}.hjson"
    )
    atomic_write_json(os.path.join("back", filename), source_data)

    # 変更に合わせてPNG画像を保存
    st.session_state["save_png"] = True


def build_mapping(
    items: List[Dict[str, Any]],
    key_field: str,
    value_field: str,
    *,
    add_empty: bool = False,
    empty_key: str = "None",
    empty_value: str = "None",
) -> Dict[str, str]:
    """
    items の各 dict から key_field→value_field マッピングを作成。
    add_empty=True なら空要素を追加。
    """
    mapping = {item[key_field]: item[value_field] for item in items}

    if add_empty:
        mapping[empty_key] = empty_value
    return mapping


def build_sorted_list(
    items: List[Dict[str, Any]], field: str, *, prepend: Optional[List[str]] = None
) -> List[str]:
    """
    items の各 dict から field を取り出してソートしたリストを返す。
    prepend が渡されれば、先頭に順番に挿入。
    """
    lst = sorted(item[field] for item in items)
    if prepend:
        for x in reversed(prepend):
            lst.insert(0, x)
    return lst



def build_and_list(
    items: List[Dict[str, Any]], *, prepend: Optional[List[str]] = None
) -> List[str]:
    """
    全 edges の and をユニークに集めてソートしたリスト。
    prepend（例: ["None","New"]）を先頭に挿入可能。
    """
    vals = []
    for item in items:
        if item.get("and", "None") not in (None, "", "None"):
            vals.append(str(item["and"]))
    sorted_vals = sorted(list(set(vals)), key=lambda v: (not v.isdigit(), v))
    if prepend:
        for x in reversed(prepend):
            sorted_vals.insert(0, x)
    return sorted_vals


def get_next_and_number(existing: List[str], candidate: str) -> str:
    """
    candidate=="New" → 1〜99 の空き番号を返す。
    candidate=="" → "None"
    それ以外はそのまま返す。
    """
    if candidate == "New":
        for i in range(1, 100):
            s = str(i)
            if s not in existing:
                return s
        return "None"
    if not candidate:
        return "None"
    return candidate


def get_backup_files_for_current_data():
    """現在のデータに対するバックアップファイルの一覧を取得する。

    Returns:
        list: バックアップファイルのリスト
    """
    # copy_fileによるファイルコピー後のページ全体再描画をここで処理する
    # （fragment内の通常レンダリングパスなのでst.rerunが正常動作する）
    if st.session_state.pop("need_full_rerun", False):
        st.rerun(scope="app")

    # バックアップファイルのリストを取得
    backup_files = [
        f
        for f in os.listdir("back")
        if os.path.isfile(os.path.join("back", f))
        and f.endswith(".hjson")
        and st.session_state.app_data[st.session_state.app_name]["postfix"] in f
    ]
    backup_files.sort(reverse=True)
    backup_files.insert(0, "バックアップから読込")
    return backup_files


def copy_file():
    """バックアップから現在のデータへファイルをコピー（復元）する。

    Note:
        この関数はコピー元ファイルが "back" ディレクトリに存在することを前提とする。
        コピー先のファイルパスはst.session_stateから取得される。
    """

    src = st.session_state["selected_backup_file"]
    # プレースホルダー（「バックアップから読込」）が選択された場合はスキップ
    if src == "バックアップから読込":
        return
    dst = st.session_state["file_path"]
    src = os.path.join("back", src)
    if os.path.exists(src):
        shutil.copy(src, dst)
        # @st.fragment 内からの呼び出しでもページ全体を再描画するためフラグを設定
        st.session_state["need_full_rerun"] = True


def make_hashable(data):
    """
    入れ子になった辞書やリストを含むデータを、ハッシュ可能で順序不変な形に変換する。
    """
    if isinstance(data, dict):
        # 辞書の場合: キーでソートし、値も再帰的に変換したタプルのタプルにする
        return tuple(sorted((key, make_hashable(value)) for key, value in data.items()))
    elif isinstance(data, list):
        # リストの場合: 各要素を再帰的に変換したタプルにする
        return tuple(make_hashable(element) for element in data)
    elif isinstance(data, set):
        # セットの場合: frozensetに変換し、要素も再帰的に変換
        return frozenset(make_hashable(element) for element in data)
    # 他のハッシュ可能な型 (int, str, tuple, frozensetなど) はそのまま返す
    # 注意: float型は完全一致の問題があるため、用途によっては丸め処理などが必要
    return data


def atomic_write_json(file_path: str, data: Any):
    """データをJSONファイルにアトミックに書き込む。

    Args:
        file_path (str): 保存先ファイルのパス
        data (Any): 書き込むデータ
    """
    dir_name = os.path.dirname(file_path) or "."
    # 同じディレクトリに一時ファイルを作成
    with tempfile.NamedTemporaryFile(
        mode="w", dir=dir_name, delete=False, encoding="utf-8"
    ) as tf:
        temp_path = tf.name
        try:
            hjson.dump(data, tf, ensure_ascii=False, indent=4)
            tf.flush()
            os.fsync(tf.fileno())
        except Exception:
            # 書き込み失敗時は一時ファイルを削除して例外を再送出
            tf.close()
            os.remove(temp_path)
            raise

    # 正常に書き込めた場合のみリネーム（アトミック操作）
    try:
        os.replace(temp_path, file_path)
    except OSError:
        os.remove(temp_path)
        raise


def calculate_text_area_height(text: str, min_height: int = 100, line_height: int = 25) -> int:
    """行数に基づいてテキストエリアの高さを計算する。

    Args:
        text (str): 入力テキスト
        min_height (int): 最小の高さ（ピクセル）
        line_height (int): 1行あたりの高さ（ピクセル）

    Returns:
        int: 計算された高さ
    """
    if not text:
        return min_height
    
    # 行数をカウント（改行の数 + 1 + 末尾の空行分1）
    lines = text.count('\n') + 2
    
    # なぜか1行でも高くなりすぎることがあるので、少し調整
    # base height (padding etc.) + lines * line_height
    calculated_height = 30 + (lines * line_height)
    
    return max(min_height, calculated_height)


def unescape_newline(text: str) -> str:
    """テキスト内のエスケープされた改行文字を元に戻す。
    
    Args:
        text (str): 入力テキスト
        
    Returns:
        str: 改行文字がデコードされたテキスト
    """
    if not isinstance(text, str):
        return text
    
    # hjsonで保存された際にエスケープされた改行文字を戻す
    return text.replace("\\n", "\n")


def recursive_unescape(data: Any) -> Any:
    """データ内のエスケープされた改行文字を再帰的に元に戻す。

    Args:
        data (Any): 入力データ (dict, list, str など)

    Returns:
        Any: 改行文字がデコードされたデータ
    """
    if isinstance(data, str):
        return unescape_newline(data)
    elif isinstance(data, list):
        return [recursive_unescape(item) for item in data]
    elif isinstance(data, dict):
        return {key: recursive_unescape(value) for key, value in data.items()}
    else:
        return data


# --- PNGインポート機能用ユーティリティ ---

# hjsonデータ埋め込み用のマーカー
_HJSON_DATA_BEGIN = "HJSON_DATA_BEGIN"
_HJSON_DATA_END = "HJSON_DATA_END"


def embed_hjson_in_puml(plantuml_code: str, hjson_data: Dict) -> str:
    """hjsonデータをPlantUMLコメントとして埋め込む。

    PlantUMLコード内の @startuml 直後にhjsonデータをbase64エンコードして
    コメントブロックとして挿入する。PNG生成時にメタデータとして保存され、
    後からextract_hjson_from_pngで復元できる。

    Args:
        plantuml_code (str): 元のPlantUMLコード
        hjson_data (Dict): 埋め込むhjsonデータ

    Returns:
        str: hjsonデータが埋め込まれたPlantUMLコード
    """
    # hjsonデータをJSON文字列にシリアライズしてbase64エンコード
    json_str = json.dumps(hjson_data, ensure_ascii=False)
    encoded = base64.b64encode(json_str.encode("utf-8")).decode("ascii")

    # base64文字列を76文字ごとに分割してコメント行にする
    comment_lines = [f"' {_HJSON_DATA_BEGIN}"]
    for i in range(0, len(encoded), 76):
        comment_lines.append(f"' {encoded[i:i+76]}")
    comment_lines.append(f"' {_HJSON_DATA_END}")
    comment_block = "\n".join(comment_lines)

    # @startuml の直後に埋め込む
    return plantuml_code.replace("@startuml", f"@startuml\n{comment_block}", 1)


def extract_hjson_from_png(png_path: str) -> Dict:
    """PNGファイルのメタデータからhjsonデータを抽出・復元する。

    plantuml.jar -metadata を使ってPNGに埋め込まれたPlantUMLソースコードを
    取得し、HJSON_DATA_BEGIN/END マーカー間のbase64データをデコードして
    hjsonデータを復元する。

    Args:
        png_path (str): PNGファイルのパス

    Returns:
        Dict: 復元されたhjsonデータ

    Raises:
        FileNotFoundError: PNGファイルが見つからない場合
        ValueError: メタデータにhjsonデータが含まれていない場合
        RuntimeError: plantuml.jarの実行に失敗した場合
    """
    if not os.path.exists(png_path):
        raise FileNotFoundError(f"PNGファイルが見つかりません: {png_path}")

    # plantuml.jar -metadata でメタデータを抽出
    try:
        result = subprocess.run(
            ["java", "-jar", "plantuml.jar", "-metadata", png_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("plantuml.jarのメタデータ抽出がタイムアウトしました。")
    except FileNotFoundError:
        raise RuntimeError(
            "Javaまたはplantuml.jarが見つかりません。"
            "Javaがインストールされているか確認してください。"
        )

    if result.returncode != 0:
        raise RuntimeError(
            f"plantuml.jar の実行に失敗しました (code {result.returncode}): "
            f"{result.stderr}"
        )

    metadata_output = result.stdout

    # HJSON_DATA_BEGIN ~ HJSON_DATA_END 間のbase64データを抽出
    in_data_block = False
    base64_parts = []

    for line in metadata_output.splitlines():
        stripped = line.strip()
        # コメントプレフィックス "' " を除去
        if stripped.startswith("'"):
            content = stripped[1:].strip()
        else:
            content = stripped

        if content == _HJSON_DATA_BEGIN:
            in_data_block = True
            continue
        elif content == _HJSON_DATA_END:
            in_data_block = False
            continue

        if in_data_block:
            base64_parts.append(content)

    if not base64_parts:
        raise ValueError(
            "このPNGファイルにはhjsonデータが埋め込まれていません。\n"
            "hjsonデータ埋め込み機能が有効になった後に保存されたPNGファイルを使用してください。"
        )

    # base64デコード → JSONパース
    encoded_data = "".join(base64_parts)
    try:
        decoded_bytes = base64.b64decode(encoded_data)
        json_str = decoded_bytes.decode("utf-8")
        hjson_data = json.loads(json_str)
    except Exception as e:
        raise ValueError(f"hjsonデータのデコードに失敗しました: {e}")

    return hjson_data
