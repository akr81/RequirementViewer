import streamlit as st
import subprocess
import atexit
import zlib
import requests
import hjson
import os
import shutil
import datetime
import copy
import tempfile
import time
from contextlib import contextmanager
from typing import Tuple, List, Dict, Tuple, Any, Optional


@contextmanager
def log_time(label: str):
    """Execution time logging context manager."""
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"[{label}] Execution time: {elapsed_time:.4f} seconds")


# PlantUMLサーバをバックグラウンドプロセスとして起動し、キャッシュする
@st.cache_resource
def start_plantuml_server():
    """Launch PlantUML server as a background process."""
    # plantuml.jarは同一ディレクトリに配置していると仮定
    command = ["java", "-jar", "plantuml.jar", "-picoweb"]
    try:
        process = subprocess.Popen(command)
        # プロセス終了時にクリーンアップするため、atexitに登録
        atexit.register(lambda: process.terminate())
        return process
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
    """Encode text to PlantUML server format.

    Args:
        text (str): Text to encode

    Returns:
        str: Encoded text
    """
    # UTF-8にエンコードし、zlibでdeflate圧縮
    data = text.encode("utf-8")
    compressed = zlib.compress(data)
    # zlibヘッダー(最初の2バイト)とチェックサム(最後の4バイト)を除去
    compressed = compressed[2:-4]
    return encode64(compressed)


def encode64(data: bytes) -> str:
    """Encode bytes to PlantUML server format.

    Args:
        data (bytes): Data to encode

    Returns:
        str: Encoded text
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
    """Get SVG diagram from PlantUML code.

    Args:
        plantuml_code (str): PlantUML code
        plantuml_server (str): PlantUML server URL

    Returns:
        Any: SVG diagram as text or PNG image as bytes
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
    """Load colors from JSON file.

    Returns:
        list: List of colors
    """
    with open("setting/colors.json", "r", encoding="utf-8") as f:
        colors = hjson.load(f)
    return list(colors.keys())


def load_config() -> dict:
    """Load config from JSON file.

    Returns:
        dict: Config dictionary
    """
    if os.path.exists("setting/config.hjson"):
        config_file = "setting/config.hjson"
    else:
        config_file = "setting/default_config.hjson"
    with open(config_file, "r", encoding="utf-8") as f:
        config = hjson.load(f)
    return config


def save_config(config_data: dict):
    """Save config to JSON file.

    Args:
        config_data (dict): Config dictionary
    """
    config_file_path = "setting/config.hjson"
    try:
        atomic_write_json(config_file_path, config_data)
    except Exception as e:
        st.error(f"設定ファイルの保存に失敗しました: {e}")


def get_default_data_structure() -> Dict:
    """Returns the default structure for a new data file."""
    return {"nodes": [], "edges": []}


def list_hjson_files(directory: str) -> List[str]:
    """Lists .hjson files in the specified directory.

    Args:
        directory (str): The directory to scan.

    Returns:
        List[str]: A list of .hjson file names.
    """
    if not os.path.isdir(directory):
        return []
    return [
        f
        for f in os.listdir(directory)
        if f.endswith(".hjson") and os.path.isfile(os.path.join(directory, f))
    ]


def load_app_data() -> dict:
    """Load app_data from JSON file.

    Returns:
        dict: Config dictionary
    """
    with open("setting/app_data.json", "r", encoding="utf-8") as f:
        app_data = hjson.load(f)
    return app_data


def load_source_data(file_path: str) -> Dict:
    """Load diagram source data from JSON file.

    Args:
        file_path (str): Path to JSON file

    Returns:
        Dict: Dictionary of source data
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

    return source_data


def update_source_data(file_path: str, source_data: Dict):
    """Update source to JSON file.

    Args:
        file_path (str): Path to JSON file
        source_data (Dict): Source data
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


def extract_and_list(
    items: List[Dict[str, Any]], *, prepend: Optional[List[str]] = None
) -> List[str]:
    """
    全 requirements の relations[].and をユニークに集めてソートしたリスト。
    prepend（例: ["None","New"]）を先頭に挿入可能。
    """
    vals = {
        str(rel["and"])
        for item in items
        for rel in item.get("relations", [])
        if rel.get("and") not in (None, "", "None")
    }
    sorted_vals = sorted(vals, key=lambda v: (not v.isdigit(), v))
    if prepend:
        for x in reversed(prepend):
            sorted_vals.insert(0, x)
    return sorted_vals


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
    """Get backup files for current data.

    Returns:
        list: List of backup files
    """
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
    """Copy file from backup to current data.

    Note:
        This function assumes that the source file exists in the "back" directory.
        The destination file is specified in the session state.
    """

    src = st.session_state["selected_backup_file"]
    dst = st.session_state["file_path"]
    """Copy file from src to dst."""
    src = os.path.join("back", src)
    if os.path.exists(src):
        shutil.copy(src, dst)


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
    """Write data to JSON file atomically.

    Args:
        file_path (str): Path to JSON file
        data (Any): Data to write
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
