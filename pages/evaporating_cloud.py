import streamlit as st
from src.operate_buttons import add_operate_buttons
from src.diagram_configs import *
from src.page_setup import setup_page_layout_and_data  # 変更
from src.utility import (  # copy_file, get_backup_files_for_current_data のみ使用
    get_backup_files_for_current_data,
    copy_file,
)
import copy


# ページ全体のデータ読み込みと基本設定
page_elements = setup_page_layout_and_data("Evaporating Cloud Viewer")

# setup_page_layout_and_data から返された要素を変数に展開
color_list = page_elements["color_list"]
config_data = page_elements["config_data"]
app_data = page_elements["app_data"]
file_path = page_elements["file_path"]
requirement_data = page_elements["requirement_data"]
nodes = page_elements["nodes"]  # Evaporating Cloud では直接使われないが、一応取得
# edges は Evaporating Cloud では直接使われない
requirement_manager = page_elements["requirement_manager"]
graph_data = page_elements["graph_data"]
id_title_dict = page_elements["id_title_dict"]
unique_id_dict = page_elements["unique_id_dict"]
id_title_list = page_elements[
    "id_title_list"
]  # Evaporating Cloud では直接使われないが、一応取得
# add_list は Evaporating Cloud では使われない
scale = page_elements["scale"]  # Evaporating Cloud では直接使われないが、一応取得
selected_unique_id = page_elements["selected_unique_id"]
upstream_distance = page_elements[
    "upstream_distance"
]  # Evaporating Cloud では直接使われないが、一応取得
downstream_distance = page_elements[
    "downstream_distance"
]  # Evaporating Cloud では直接使われないが、一応取得
selected_entity = page_elements["selected_entity"]
landscape = page_elements[
    "landscape"
]  # Evaporating Cloud では直接使われないが、一応取得

# 編集用カラムとPlantUMLコードを page_elements から取得
edit_column = page_elements["edit_column"]
plantuml_code = page_elements["plantuml_code"]

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
