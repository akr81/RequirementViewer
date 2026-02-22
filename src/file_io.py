"""ファイル入出力・設定管理。"""
import streamlit as st
import hjson
import os
import shutil
import datetime
import copy
import time
import tempfile
from contextlib import contextmanager
from typing import Dict, List, Any


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
    from src.text_helpers import recursive_unescape

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
    from src.data_helpers import make_hashable

    # --- 最後に使用したページをconfigに保存 ---
    if "app_name" in st.session_state and "config_data" in st.session_state:
        current_app_name = st.session_state.app_name
        # config.hjsonに書き込むキーをapp.pyと合わせる
        LAST_USED_PAGE_KEY = "last_used_page"
        st.session_state.config_data[LAST_USED_PAGE_KEY] = current_app_name
        save_config(st.session_state.config_data)

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
