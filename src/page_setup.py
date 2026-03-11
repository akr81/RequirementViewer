import streamlit as st
import os
import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from src.requirement_manager import RequirementManager
from src.requirement_graph import RequirementGraph
from src.utility import (
    load_colors,
    load_config,
    load_app_data,
    load_source_data,
    build_mapping,
    build_sorted_list,
    build_and_list,
    update_source_data,
)
from src.constants import AppName, EdgeType  # 追加
from src.diagram_configs import DEFAULT_ENTITY_GETTERS  # 追加
from src.diagram_column import draw_diagram_column, DiagramContext, DiagramOptions  # 追加


@dataclass
class GraphData:
    requirement_data: Dict[str, Any]
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    requirement_manager: RequirementManager
    graph_data: RequirementGraph
    id_title_dict: Dict[str, str]
    unique_id_dict: Dict[str, str]
    id_title_list: List[str]
    add_list: List[str]


@dataclass
class LoadedData:
    requirement_data: Dict[str, Any]
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    requirement_manager: RequirementManager
    graph_data: RequirementGraph
    id_title_dict: Dict[str, str]
    unique_id_dict: Dict[str, str]
    id_title_list: List[str]
    add_list: List[str]
    selected_unique_id: Optional[str]
    selected_entity: Optional[Dict[str, Any]]
    options: DiagramOptions


def initialize_page(app_name: str):
    # ページの設定
    st.set_page_config(
        layout="wide",
        page_title=app_name,  # st.session_state.app_name の代わりに app_name を直接使用
        initial_sidebar_state="collapsed",  # サイドバーを閉じた状態で表示
    )

    # ボタンのフォントサイズとパディングを縮小し、横長レイアウトを維持する
    st.markdown(
        """
        <style>
        .stButton > button {
            font-size: 0.8rem;
            padding: 0.2rem 0.5rem;
            min-height: 0;
        }
        /* ヘッダーとコンテンツの隙間を詰める */
        .stMainBlockContainer {
            padding-top: 3.0rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 色のリストを読み込む
    color_list = load_colors()

    # アプリ名を設定 (set_page_config の後でも問題ない)
    st.session_state.app_name = app_name
    if "save_png" not in st.session_state:
        st.session_state["save_png"] = False

    # configファイルを読み込む
    config_data = load_config()
    # 動的に決定されたPlantUMLサーバーのURLがあれば上書きする
    if "runtime_plantuml_url" in st.session_state:
        config_data["plantuml"] = st.session_state["runtime_plantuml_url"]

    st.session_state.config_data = config_data
    app_data = load_app_data()
    st.session_state.app_data = app_data

    return color_list, config_data, app_data


@st.cache_data
def load_graph_data(file_path: str, mtime: float, app_name: str) -> GraphData:
    """データの読み込みとグラフ構築をキャッシュ付きで実行する。

    Args:
        file_path (str): HJSONファイルパス
        mtime (float): ファイル更新時刻（キャッシュ無効化用）
        app_name (str): アプリケーション名

    Returns:
        GraphData: 構築済みのグラフデータ
    """
    requirement_data = load_source_data(file_path)
    nodes = requirement_data["nodes"]
    edges = requirement_data["edges"]

    # アプリごとの表示対象キーと後方互換性の設定
    if app_name in (AppName.CURRENT_REALITY, AppName.EVAPORATING_CLOUD):
        display_key = "text"
    elif app_name in (AppName.PROCESS_FLOW, AppName.CCPM):
        display_key = "title"
    else:
        display_key = "id"

    # [重要] Graph構築の前にキーのコピー（後方互換性対応）を行う
    for node in nodes:
        # 後方互換性: 古いキーの内容を新しいキーへコピーする
        if app_name == AppName.CURRENT_REALITY:
            if "id" in node and not node.get("text"):
                node["text"] = node["id"]
        elif app_name == AppName.EVAPORATING_CLOUD:
            if "title" in node and not node.get("text"):
                node["text"] = node["title"]
        elif app_name == AppName.PROCESS_FLOW:
            if "id" in node and not node.get("title"):
                node["title"] = node["id"]
        elif app_name == AppName.REQUIREMENT:
            # PlantUMLコンバーターは title を class 名として使用するため、
            # title が空の場合は id からフォールバックする
            if not node.get("title") and node.get("id"):
                node["title"] = node["id"]
            if not node.get("id") and node.get("title"):
                node["id"] = node["title"]
                
        # 表示対象キーが未定義の場合は空文字にする
        if display_key not in node:
            node[display_key] = ""
        
    # 各ノードの表示キーの出現回数をカウント（フォールバック後）
    display_key_counts = {}
    for node in nodes:
        key_val = node[display_key]
        display_key_counts[key_val] = display_key_counts.get(key_val, 0) + 1

    for node in nodes:
        key_val = node[display_key]
        # UI表示用の一意なラベル（[_display_label]）を作成（コンボボックスでの同名競合防止）
        if display_key_counts.get(key_val, 0) > 1:
            # 同名が存在する場合はハッシュの先頭5文字を付与して区別
            node["_display_label"] = f"{key_val} ({node['unique_id'][:5]})"
        else:
            node["_display_label"] = key_val

    requirement_manager = RequirementManager(requirement_data)
    graph_data = RequirementGraph(requirement_data, app_name)
    
    # 変数名は既存との互換性のため id_title_dict としているが、実際は _display_label を用いている
    id_title_dict = build_mapping(nodes, "_display_label", "unique_id", add_empty=True)
    unique_id_dict = build_mapping(nodes, "unique_id", "_display_label", add_empty=True)
    id_title_list = build_sorted_list(nodes, "_display_label", prepend=["None"])
    add_list = build_and_list(edges, prepend=["None", "New"])

    return GraphData(
        requirement_data=requirement_data,
        nodes=nodes,
        edges=edges,
        requirement_manager=requirement_manager,
        graph_data=graph_data,
        id_title_dict=id_title_dict,
        unique_id_dict=unique_id_dict,
        id_title_list=id_title_list,
        add_list=add_list,
    )


def load_and_prepare_data(file_path, app_name):
    # ファイルの更新時刻を取得（キャッシュキーとして使用）
    try:
        mtime = os.path.getmtime(file_path)
    except OSError:
        mtime = 0.0

    # キャッシュされたデータをロード
    # キャッシュ済みオブジェクトを直接変更すると他のレンダリングに影響するため、
    # ディープコピーしてから使用する
    gd = copy.deepcopy(load_graph_data(file_path, mtime, app_name))

    # キャッシュから展開
    requirement_data = gd.requirement_data
    nodes = gd.nodes
    edges = gd.edges
    requirement_manager = gd.requirement_manager
    graph_data = gd.graph_data
    id_title_dict = gd.id_title_dict
    unique_id_dict = gd.unique_id_dict
    id_title_list = gd.id_title_list
    add_list = gd.add_list

    # URL のクエリからパラメタを取得
    scale = float(st.query_params.get("scale", 1.0))
    # 未選択時は None に統一。st.query_params.get は未設定時に None を返す
    selected_unique_id = st.query_params.get("selected") or None
    upstream_distance = int(st.query_params.get("upstream_distance", -1))
    downstream_distance = int(st.query_params.get("downstream_distance", -1))
    landscape = st.query_params.get("landscape", False)
    # URLパラメタから取得すると文字列なのでboolに変換
    landscape = True if landscape == "True" else False

    title = st.query_params.get("title", False)
    # URLパラメタから取得すると文字列なのでboolに変換
    title = True if title == "True" else False

    detail = st.query_params.get("detail", False)
    # URLパラメタから取得すると文字列なのでboolに変換
    detail = True if detail == "True" else False

    show_temp_id = st.query_params.get("show_temp_id", "True")
    show_temp_id = True if show_temp_id == "True" else False

    # 接続モード時、requirement_dataのエッジのみを直接更新する
    link_mode = st.query_params.get("link_mode", "False")
    link_mode = True if link_mode == "True" else False
    previous_selected = st.query_params.get("previous_selected", "None")

    # --- ステート制御: 接続モード（link_mode）の自動切り替え ---
    # ユーザーが図上の同じノードを2回連続でクリックした場合、直感的な操作として
    # 「そのノードからのエッジを繋ぐ（接続）モード」のON/OFFをトグルする仕様。
    if (previous_selected == selected_unique_id):
        # 連続クリックされた場合、現在の接続モード状態を反転させる
        if not link_mode:
            link_mode = True
            st.toast(f"接続モードON: 接続先ノードを選択")
        else:
            link_mode = False
            st.toast(f"接続モードOFF")
    else:
        # 別のノードが選択された場合の処理
        if link_mode:
            # 接続モードがONの状態で別のノードが選ばれた場合、
            # previous_selected(接続元) から selected_unique_id(接続先) へエッジを引く。
            # アプリケーションごとに必須の属性を定義
            edge_defaults = {"type": EdgeType.ARROW} # 共通のデフォルト

            if app_name == AppName.CURRENT_REALITY:
                edge_defaults["and"] = "None"
            elif app_name == AppName.PROCESS_FLOW:
                edge_defaults["comment"] = ""
            elif app_name == AppName.REQUIREMENT:
                edge_defaults["type"] = EdgeType.DERIVE_KEY
                # 必要に応じて 'note': {} なども追加

            # 両端が実在するノードIDである場合のみエッジを生成する
            # "default" や "None" 等のセンチネル値がIDとして混入するのを防ぐ
            _SENTINEL = ("None", "default", "")
            _can_create_edge = (
                isinstance(previous_selected, str)
                and isinstance(selected_unique_id, str)
                and previous_selected not in _SENTINEL
                and selected_unique_id not in _SENTINEL
                and previous_selected in unique_id_dict
                and selected_unique_id in unique_id_dict
            )
            if _can_create_edge:
                requirement_manager.update_edge(previous_selected, selected_unique_id, edge_defaults)
                update_source_data(file_path, requirement_manager.requirements)
                print("update file")
            st.query_params["link_mode"] = "False"
            st.rerun()
        link_mode = False
    st.query_params["link_mode"] = str(link_mode)

    # "default" 等の無効なIDは "None" に正規化して次フレームへ引き渡す
    # これにより接続モード中に不正なIDがエッジのsource/destinationに混入するのを防ぐ
    _SENTINEL = ("None", "default", "")
    if (
        isinstance(selected_unique_id, str)
        and selected_unique_id not in _SENTINEL
        and selected_unique_id in unique_id_dict
    ):
        previous_selected = selected_unique_id
    else:
        previous_selected = "None"

    # 選択されたエンティティを取得
    selected_entity = None
    if selected_unique_id is None:
        # エンティティが選択されていない場合はデフォルトのエンティティを選択してリロード
        st.query_params.setdefault("selected", "default")
        st.query_params.setdefault("detail", "True")
        st.query_params.setdefault("title", "True")
        st.rerun()
    else:
        if selected_unique_id == "default":
            # デフォルトの場合は何もしない
            pass
        else:
            if selected_unique_id not in unique_id_dict:
                # 存在しないユニークIDが指定された場合は何もしない
                pass
            else:
                selected_entity = [
                    d for d in nodes if d["unique_id"] == selected_unique_id
                ][0]

    return LoadedData(
        requirement_data=requirement_data,
        nodes=nodes,
        edges=edges,
        requirement_manager=requirement_manager,
        graph_data=graph_data,
        id_title_dict=id_title_dict,
        unique_id_dict=unique_id_dict,
        id_title_list=id_title_list,
        add_list=add_list,
        selected_unique_id=selected_unique_id,
        selected_entity=selected_entity,
        options=DiagramOptions(
            upstream_distance=upstream_distance,
            downstream_distance=downstream_distance,
            scale=scale,
            graph_data=graph_data,
            landscape=landscape,
            title=title,
            detail=detail,
            show_temp_id=show_temp_id,
            link_mode=link_mode,
            previous_selected=previous_selected,
        ),
    )


def setup_page_layout_and_data(
    app_name: str, default_entity_creation_args: dict = None,
    skip_diagram: bool = False,
) -> dict:
    """
    ページの基本的なデータ読み込み、レイアウト設定、図の初期描画を行う共通関数。
    """
    color_list, config_data, app_data = initialize_page(app_name)

    # データファイル設定のチェックと読み込み
    # アプリケーション名から、config.hjson内のデータファイルパスを指すキー名を取得
    data_file_key_in_config = app_data[app_name]["data"]
    if data_file_key_in_config not in config_data:
        st.error(
            f"""設定ファイル ('config.hjson') に '{data_file_key_in_config}' の設定がありません。
            settingページからデータファイルを設定してください。"""
        )
        st.stop()
    file_path = config_data[data_file_key_in_config]
    st.session_state["file_path"] = file_path

    # データの読み込みと準備
    loaded_data = load_and_prepare_data(file_path, app_name)
    
    # Extract data for easier access
    nodes = loaded_data.nodes
    unique_id_dict = loaded_data.unique_id_dict
    selected_unique_id = loaded_data.selected_unique_id
    selected_entity = loaded_data.selected_entity
    options = loaded_data.options

    # 未選択の場合はデフォルトエンティティを設定
    if not selected_entity:
        getter_func = DEFAULT_ENTITY_GETTERS[app_name]
        if default_entity_creation_args:
            selected_entity = getter_func(**default_entity_creation_args)
        else:
            selected_entity = getter_func()

    # selected_unique_idが"default"の時に実際のIDを割り当てる（全アプリ共通）
    if selected_unique_id == "default":
        if selected_entity:  # selected_entityがNoneでないことを確認
            selected_unique_id = selected_entity["unique_id"]

    # 図表示とデータ編集のレイアウトを設定
    diagram_column, edit_column = st.columns([4, 1])

    context = DiagramContext(
        app_name=app_name,
        unique_id_dict=unique_id_dict,
        id_title_dict=loaded_data.id_title_dict,
        id_title_list=loaded_data.id_title_list,
        config_data=config_data,
        requirements=loaded_data.requirement_data,
    )
    
    # options is already created in load_and_prepare_data

    if skip_diagram:
        # ダイアグラム描画をスキップ（呼び出し側でタブ内に描画する）
        plantuml_code = ""
    else:
        plantuml_code = draw_diagram_column(
            diagram_column,
            context=context,
            options=options,
        )

    return {
        "color_list": color_list,
        "config_data": config_data,
        "app_data": app_data,
        "file_path": file_path,
        "requirement_data": loaded_data.requirement_data,
        "nodes": nodes,
        "edges": loaded_data.edges,
        "requirement_manager": loaded_data.requirement_manager,
        "graph_data": loaded_data.graph_data,
        "id_title_dict": loaded_data.id_title_dict,
        "unique_id_dict": unique_id_dict,
        "id_title_list": loaded_data.id_title_list,
        "add_list": loaded_data.add_list,  # current_reality_tree で必要
        "scale": options.scale,
        "selected_unique_id": selected_unique_id,
        "upstream_distance": options.upstream_distance,
        "downstream_distance": options.downstream_distance,
        "selected_entity": selected_entity,
        "landscape": options.landscape,
        "title": options.title,
        "edit_column": edit_column,  # データ編集UIを配置するカラム
        "diagram_column": diagram_column,  # 図表示カラム（CCPM分析等で再利用）
        "diagram_context": context,  # DiagramContext（タブ内描画用）
        "diagram_options": options,  # DiagramOptions（タブ内描画用）
        "plantuml_code": plantuml_code,
    }
