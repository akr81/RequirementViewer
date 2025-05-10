import streamlit as st
import subprocess
import atexit
import zlib
import requests
import hjson
import os
import shutil
import datetime
from typing import Tuple, List, Dict, Tuple, Any, Optional


# PlantUMLサーバをバックグラウンドプロセスとして起動し、キャッシュする
@st.cache_resource
def start_plantuml_server():
    """Launch PlantUML server as a background process."""
    # plantuml.jarは同一ディレクトリに配置していると仮定
    command = ["java", "-jar", "plantuml.jar", "-picoweb"]
    process = subprocess.Popen(command)
    # プロセス終了時にクリーンアップするため、atexitに登録
    atexit.register(lambda: process.terminate())
    return process


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
def get_diagram(plantuml_code: str, plantuml_server: str, *, png_out=False) -> Any:
    """Get SVG diagram from PlantUML code.

    Args:
        plantuml_code (str): PlantUML code
        plantuml_server (str): PlantUML server URL

    Returns:
        Any: SVG diagram as text or PNG image as bytes
    """
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


def load_config() -> Tuple[dict, bool]:
    """Load config from JSON file.

    Returns:
        dict: Config dictionary
    """
    if os.path.exists("setting/config.json"):
        config_file = "setting/config.json"
        demo = False
    else:
        config_file = "setting/default_config.json"
        demo = True
    with open(config_file, "r", encoding="utf-8") as f:
        config = hjson.load(f)
    return config, demo


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
            except:
                st.error("JSONファイルの読み込みに失敗しました。")
                st.stop()
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
    # list内の辞書型データをunique_id順に並び替える
    source_data["nodes"].sort(key=lambda x: x["unique_id"])
    source_data["edges"].sort(key=lambda x: x["source"])
    with open(file_path, "w", encoding="utf-8") as f:
        hjson.dump(source_data, f, ensure_ascii=False, indent=4)

    # for backup
    postfix_file = st.session_state.app_data[st.session_state.app_name]["postfix"]
    os.makedirs("back", exist_ok=True)
    filename = (
        datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{postfix_file}.hjson"
    )
    with open(os.path.join("back", filename), "w", encoding="utf-8") as out:
        hjson.dump(source_data, out, ensure_ascii=False, indent=4)


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
    backup_files.insert(0, "バックアップから選択")
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
