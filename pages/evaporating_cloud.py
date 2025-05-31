import streamlit as st
from src.diagram_column import draw_diagram_column
from src.operate_buttons import add_operate_buttons
from src.diagram_configs import *
from src.page_setup import initialize_page, load_and_prepare_data
from src.utility import (
    get_backup_files_for_current_data,
    copy_file,
)
import copy


color_list, config_data, app_data = initialize_page("Evaporating Cloud Viewer")

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
    _,
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
    # 直接データ操作はせず、コピーに対して操作する
    tmp_entity = copy.deepcopy(selected_entity)
    tmp_entity.setdefault("color", "None")  # colorがない場合はNoneを設定

    st.write(tmp_entity["id"])
    if tmp_entity["id"] == "head":
        question = "共通の目的は何か？"
    elif tmp_entity["id"] == "right_shoulder" or tmp_entity["id"] == "left_shoulder":
        question = "目的は何か？"
    elif tmp_entity["id"] == "right_hand" or tmp_entity["id"] == "left_hand":
        question = "行動は何か？"
    else:
        question = "仮定・前提条件は何か？"
    tmp_entity["title"] = st.text_area(question, tmp_entity["title"], height=400)
    tmp_entity["color"] = st.selectbox(
        "色", color_list, index=color_list.index(tmp_entity["color"])
    )

    # 更新しないが旧フォーマットを更新するために読み込む
    tmp_edges = copy.deepcopy(requirement_data["edges"])

    add_operate_buttons(
        selected_unique_id,
        tmp_entity,
        requirement_manager,
        file_path,
        id_title_dict,
        unique_id_dict,
        no_new=True,
        no_add=True,
        no_remove=True,
        tmp_edges=tmp_edges,
    )

# セッション状態にgraph_dataを追加
st.session_state.graph_data = graph_data

# テキストエリアで PlantUML コードが確認可能
st.text_area("PlantUML コード", value=plantuml_code, height=250)
