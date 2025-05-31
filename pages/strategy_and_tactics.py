import streamlit as st
from src.diagram_column import draw_diagram_column
from src.operate_buttons import add_operate_buttons
from src.diagram_configs import *
from src.page_setup import initialize_page, load_and_prepare_data
from src.utility import (
    get_backup_files_for_current_data,
    copy_file,
)
import uuid
import copy


color_list, config_data, app_data, plantuml_process = initialize_page(
    "Strategy and Tactics Tree Viewer"
)


data_key = st.session_state.app_data[st.session_state.app_name]["data"]
if data_key not in config_data:
    st.error(
        """設定ファイルにデータファイル設定がありません。
        settingからファイルを設定してください。"""
    )
    st.stop()

file_path = config_data[data_key]
st.session_state["file_path"] = file_path

# データの読み込みと準備
(
    requirement_data,
    nodes,
    edges,
    requirement_manager,
    graph_data,
    id_title_dict,
    unique_id_dict,
    id_title_list,
    _,
    scale,
    selected_unique_id,
    upstream_distance,
    downstream_distance,
    selected_entity,
    landscape,
) = load_and_prepare_data(file_path, st.session_state.app_name)

if not selected_entity:
    selected_entity = DEFAULT_ENTITY_GETTERS[st.session_state.app_name]()

# Requirement diagram表示とデータ編集のレイアウトを設定
diagram_column, edit_column = st.columns([4, 1])

plantuml_code = draw_diagram_column(
    st.session_state.app_name,
    diagram_column,
    unique_id_dict,
    id_title_dict,
    id_title_list,
    config_data,
    requirement_data,
    upstream_distance,
    downstream_distance,
    scale,
    graph_data=graph_data,
    landscape=landscape,
)

with edit_column:
    title_column, file_selector_column = st.columns([4, 4])
    with title_column:
        st.write("## データ編集")
    with file_selector_column:
        # ファイル選択boxを表示
        backup_files = get_backup_files_for_current_data()
        st.selectbox(
            "ファイルを選択",
            backup_files,
            0,
            label_visibility="collapsed",
            on_change=copy_file,
            key="selected_backup_file",
        )
    # 直接データ操作はせず、コピー(uuidは異なる)に対して操作する
    tmp_entity = copy.deepcopy(selected_entity)
    tmp_entity["unique_id"] = f"{uuid.uuid4()}".replace("-", "")
    tmp_entity.setdefault("color", "None")  # colorがない場合はNoneを設定

    tmp_entity["id"] = st.text_input("ID", tmp_entity["id"])
    tmp_entity["necessary_assumption"] = st.text_area(
        "なぜこの変化が必要か？", tmp_entity["necessary_assumption"]
    )
    tmp_entity["strategy"] = st.text_area(
        "**何がこの変化の具体的な目的なのか？**", tmp_entity["strategy"]
    )
    tmp_entity["parallel_assumption"] = st.text_area(
        "なぜこの戦略をとるのか？", tmp_entity["parallel_assumption"]
    )
    tmp_entity["tactics"] = st.text_area(
        "**どのようにこの変化を達成するのか？**", tmp_entity["tactics"]
    )
    tmp_entity["sufficient_assumption"] = st.text_area(
        "なぜより詳細な具体策とアクションが必要なのか？",
        tmp_entity["sufficient_assumption"],
    )
    tmp_entity["color"] = st.selectbox(
        "色", color_list, index=color_list.index(tmp_entity["color"])
    )

    # 接続元の関係を取得
    # 直接edgeは操作せず、コピーに対して操作する
    tmp_edges = copy.deepcopy(requirement_data["edges"])
    for i, edge in enumerate(tmp_edges):
        if edge["source"] != selected_unique_id:
            continue
        edge["destination"] = id_title_dict[
            st.selectbox(
                "接続先",
                id_title_list,
                id_title_list.index(unique_id_dict[edge["destination"]]),
                key=f"destination{i}",
            )
        ]

    # 関係追加の操作があるため、1つは常に表示
    destination_unique_id = id_title_dict[
        st.selectbox("接続先(新規)", id_title_list, index=id_title_list.index("None"))
    ]  # 末尾に追加用の空要素を追加

    new_edge = {
        "source": tmp_entity["unique_id"],
        "destination": destination_unique_id,
        "type": "arrow",
    }

    add_operate_buttons(
        selected_unique_id,
        tmp_entity,
        requirement_manager,
        file_path,
        id_title_dict,
        unique_id_dict,
        tmp_edges=tmp_edges,
        new_edges=[new_edge],
    )

# セッション状態にgraph_dataを追加
st.session_state.graph_data = graph_data

# テキストエリアで PlantUML コードが確認可能
st.text_area("PlantUML コード", value=plantuml_code, height=250)
