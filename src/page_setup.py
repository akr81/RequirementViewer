import streamlit as st
from src.requirement_manager import RequirementManager
from src.requirement_graph import RequirementGraph
from src.utility import (
    load_colors,
    load_config,
    load_app_data,
    start_plantuml_server,
    load_source_data,
    build_mapping,
    build_sorted_list,
    build_and_list,
)


def initialize_page(app_name: str):
    # 色のリストを読み込む
    color_list = load_colors()

    # アプリ名を設定
    st.session_state.app_name = app_name

    # ページの設定
    st.set_page_config(
        layout="wide",
        page_title=st.session_state.app_name,
        initial_sidebar_state="collapsed",  # サイドバーを閉じた状態で表示
    )

    # configファイルを読み込む
    config_data, demo = load_config()
    st.session_state.config_data = config_data
    app_data = load_app_data()
    st.session_state.app_data = app_data

    # PlantUMLサーバを起動（キャッシュされるので再度起動されません）
    if not ("www.plantuml.com" in config_data["plantuml"]):
        plantuml_process = start_plantuml_server()

    return color_list, config_data, demo, app_data, plantuml_process


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

    return (
        requirement_data,
        nodes,
        edges,
        requirement_manager,
        graph_data,
        id_title_dict,
        unique_id_dict,
        id_title_list,
        add_list,
    )
