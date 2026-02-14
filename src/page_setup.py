import streamlit as st
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
from src.diagram_configs import DEFAULT_ENTITY_GETTERS  # 追加
from src.diagram_column import draw_diagram_column, DiagramContext, DiagramOptions  # 追加


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
    selected_unique_id: Union[str, List[None], None]
    selected_entity: Optional[Dict[str, Any]]
    options: DiagramOptions


def initialize_page(app_name: str):
    # ページの設定
    st.set_page_config(
        layout="wide",
        page_title=app_name,  # st.session_state.app_name の代わりに app_name を直接使用
        initial_sidebar_state="collapsed",  # サイドバーを閉じた状態で表示
    )

    # 色のリストを読み込む
    color_list = load_colors()

    # アプリ名を設定 (set_page_config の後でも問題ない)
    st.session_state.app_name = app_name
    if "save_png" not in st.session_state:
        st.session_state["save_png"] = False

    # configファイルを読み込む
    config_data = load_config()
    st.session_state.config_data = config_data
    app_data = load_app_data()
    st.session_state.app_data = app_data

    return color_list, config_data, app_data


def load_and_prepare_data(file_path, app_name):
    # JSONからノードとエッジ情報を取得
    requirement_data = load_source_data(file_path)
    nodes = requirement_data["nodes"]
    edges = requirement_data["edges"]

    # requirement情報とgraphを取得
    requirement_manager = RequirementManager(requirement_data)
    graph_data = RequirementGraph(requirement_data, app_name)

    # ノードとエッジからなる辞書・リストを取得
    id_title_dict = build_mapping(nodes, "id", "unique_id", add_empty=True)
    unique_id_dict = build_mapping(nodes, "unique_id", "id", add_empty=True)
    id_title_list = build_sorted_list(nodes, "id", prepend=["None"])
    add_list = build_and_list(edges, prepend=["None", "New"])

    # URL のクエリからパラメタを取得
    scale = float(st.query_params.get("scale", 1.0))
    selected_unique_id = st.query_params.get("selected", [None])
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

    # 接続モード時、requirement_dataのエッジのみを直接更新する
    link_mode = st.query_params.get("link_mode", "False")
    link_mode = True if link_mode == "True" else False
    previous_selected = st.query_params.get("previous_selected", "None")

    # 2回連続で同じノードを選択したら接続モードにする
    if (previous_selected == selected_unique_id):
        if not link_mode:
            link_mode = True
            st.toast(f"接続モードON: 接続先ノードを選択")
        else:
            link_mode = False
            st.toast(f"接続モードOFF")
    else:
        if link_mode:
            # アプリケーションごとに必須の属性を定義
            edge_defaults = {"type": "arrow"} # 共通のデフォルト

            if app_name == "Current Reality Tree Viewer":
                edge_defaults["and"] = "None"
            elif app_name == "Process Flow Diagram Viewer":
                edge_defaults["comment"] = ""
            elif app_name == "Requirement Diagram Viewer":
                edge_defaults["type"] = "deriveReqt"
                # 必要に応じて 'note': {} なども追加

            # エッジを更新
            requirement_manager.update_edge(previous_selected, selected_unique_id, edge_defaults)
            update_source_data(file_path, requirement_manager.requirements)
            print("update file")
            st.query_params["link_mode"] = "False"
            st.rerun()
        link_mode = False
    st.query_params["link_mode"] = str(link_mode)

    previous_selected = selected_unique_id

    # 選択されたエンティティを取得
    selected_entity = None
    if selected_unique_id == [None]:
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
            link_mode=link_mode,
            previous_selected=previous_selected,
        ),
    )


def setup_page_layout_and_data(
    app_name: str, default_entity_creation_args: dict = None
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

    # Requirement Diagram Viewer の場合、selected_unique_idが"default"の時に実際のIDを割り当てる
    if app_name == "Requirement Diagram Viewer" and selected_unique_id == "default":
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
        "plantuml_code": plantuml_code,
    }
