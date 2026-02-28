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
    default_config.hjsonをベースとし、ユーザー設定に不足しているキーは補完して保存する。

    Returns:
        dict: 設定項目の辞書
    """
    default_config_file = "setting/default_config.hjson"
    user_config_file = "setting/config.hjson"

    # まずデフォルト設定を読み込む
    with open(default_config_file, "r", encoding="utf-8") as f:
        config = hjson.load(f)

    # ユーザー設定が存在する場合は統合する
    if os.path.exists(user_config_file):
        with open(user_config_file, "r", encoding="utf-8") as f:
            user_config = hjson.load(f)
            
        needs_save = False
        # デフォルトにあるがユーザー設定にないキーを補完
        for key, value in config.items():
            if key not in user_config:
                user_config[key] = value
                needs_save = True

        # ユーザー設定でデフォルトをパッチする
        for key, value in user_config.items():
            config[key] = value

        # 補完が発生した場合は保存し直す
        if needs_save:
            save_config(config)

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


def _find_closest_backup_png(hjson_filename: str) -> str:
    """hjsonバックアップに対応する最も近いタイムスタンプのPNGを探す。

    hjsonとpngは別々のタイミングで保存されるため、秒がずれることがある。
    同じpostfixを持つPNGの中からタイムスタンプ差が5秒以内のものを返す。

    Args:
        hjson_filename: バックアップのhjsonファイル名（例: "20260228_180000_ccpm.hjson"）

    Returns:
        PNGファイルのパス。見つからない場合は空文字列。
    """
    # postfix部分を抽出（例: "_ccpm" を取得）
    base = hjson_filename.replace(".hjson", "")
    # タイムスタンプ部分を抽出（先頭15文字: YYYYMMDD_HHMMSS）
    if len(base) < 15:
        return ""
    ts_str = base[:15]
    postfix = base[15:]  # 例: "_ccpm"

    try:
        hjson_time = datetime.datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
    except ValueError:
        return ""

    # 同じpostfixのPNGファイルを検索
    best_path = ""
    best_diff = datetime.timedelta(seconds=6)  # 5秒超は不採用
    back_dir = "back"
    if not os.path.isdir(back_dir):
        return ""

    for f in os.listdir(back_dir):
        if not f.endswith(f"{postfix}.png"):
            continue
        f_ts_str = f[:15]
        try:
            f_time = datetime.datetime.strptime(f_ts_str, "%Y%m%d_%H%M%S")
        except ValueError:
            continue
        diff = abs(f_time - hjson_time)
        if diff < best_diff:
            best_diff = diff
            best_path = os.path.join(back_dir, f)

    return best_path


def show_backup_diff_preview(current_data: Dict):
    """選択中のバックアップと現在のデータの差分サマリを表示し、復元ボタンを提供する。

    バックアップが選択されていない場合は何も表示しない。
    復元ボタンが押されると、バックアップを現在のファイルにコピーしてページをリロードする。
    """
    selected = st.session_state.get("selected_backup_file", "バックアップから読込")
    if selected == "バックアップから読込":
        return

    backup_path = os.path.join("back", selected)
    if not os.path.exists(backup_path):
        return

    try:
        backup_data = load_source_data(backup_path)
    except Exception:
        return

    if not isinstance(backup_data, dict) or not isinstance(current_data, dict):
        return

    # ノード名の取得（title > text > id > unique_id の優先順でラベルを取得）
    def _node_label(node: Dict) -> str:
        return (
            node.get("title")
            or node.get("text")
            or node.get("id")
            or node.get("unique_id", "?")
        )

    cur_nodes = {n.get("unique_id"): n for n in current_data.get("nodes", [])}
    bak_nodes = {n.get("unique_id"): n for n in backup_data.get("nodes", [])}
    cur_edges = current_data.get("edges", [])
    bak_edges = backup_data.get("edges", [])

    added_ids = set(bak_nodes) - set(cur_nodes)
    removed_ids = set(cur_nodes) - set(bak_nodes)
    edge_diff = len(bak_edges) - len(cur_edges)

    # 差分サマリの構築
    if not added_ids and not removed_ids and edge_diff == 0:
        summary = "📋 現在のデータと同一です"
    else:
        parts = []
        if added_ids:
            names = ", ".join(_node_label(bak_nodes[uid]) for uid in sorted(added_ids))
            parts.append(f"＋ノード {len(added_ids)}件: {names}")
        if removed_ids:
            names = ", ".join(_node_label(cur_nodes[uid]) for uid in sorted(removed_ids))
            parts.append(f"－ノード {len(removed_ids)}件: {names}")
        if edge_diff > 0:
            parts.append(f"＋エッジ {edge_diff}件")
        elif edge_diff < 0:
            parts.append(f"－エッジ {abs(edge_diff)}件")
        summary = "📋 " + " / ".join(parts)

    st.caption(summary)

    # 対応するPNG画像があればサムネイルを表示
    # hjsonとpngの保存タイミングが異なり秒がずれる場合があるため、
    # 完全一致で見つからなければ近いタイムスタンプのPNGを探す
    png_path = backup_path.replace(".hjson", ".png")
    if not os.path.exists(png_path):
        png_path = _find_closest_backup_png(selected)
    if png_path:
        st.image(png_path, caption="バックアップ時の図", width="stretch")
        with st.expander("🔍 フルサイズで表示"):
            st.image(png_path, width="content")

    # 復元ボタン
    if st.button("📥 このバックアップを復元", key="restore_backup_btn"):
        copy_file()
        st.rerun(scope="app")


