import streamlit as st
from src.utility import (
    get_next_and_number,
    get_backup_files_for_current_data,
    copy_file,
)
from src.diagram_column import draw_diagram_column
from src.operate_buttons import add_operate_buttons
from src.diagram_configs import *
from src.page_setup import initialize_page, load_and_prepare_data
import uuid
import copy


def render_edge_connection(
    edge: dict, index: int, visibility: str, params: dict
) -> str:
    if edge[params["condition"]] == selected_unique_id:
        with params["connection_column"]:
            edge[params["selectbox_index"]] = id_title_dict[
                st.selectbox(
                    params["selectbox_label"],
                    id_title_list,
                    index=id_title_list.index(
                        unique_id_dict[edge[params["selectbox_index"]]]
                    ),
                    key=f"{params['selectbox_key']}{index}",
                    label_visibility=visibility,
                )
            ]
        with params["and_column"]:
            edge["and"] = st.selectbox(
                "and",
                add_list,
                index=add_list.index(edge["and"]),
                key=f"and_{params['selectbox_key']}{index}",
                label_visibility=visibility,
            )
            edge["and"] = get_next_and_number(add_list, edge["and"])
            if not edge["and"]:
                edge["and"] = "None"
        if tmp_entity["type"] == "note":
            edge["type"] = "flat_long"

        return "collapsed"  # 1つ目の要素は表示し、以降は非表示にする
    return visibility


def render_edge_connection_new(edge: dict, _: int, visibility: str, params: dict):
    with params["connection_column"]:
        edge[params["selectbox_index"]] = id_title_dict[
            st.selectbox(
                f"{params['selectbox_label']}(新規)",
                id_title_list,
                index=id_title_list.index("None"),
                key=f"{params['selectbox_key']}_new",
                label_visibility=visibility,
            )
        ]
    with params["and_column"]:
        edge["and"] = st.selectbox(
            "and",
            add_list,
            index=add_list.index("None"),
            key=f"and_{params['selectbox_key']}_new",
            label_visibility=visibility,
        )
        edge["and"] = get_next_and_number(add_list, edge["and"])
        if not edge["and"]:
            edge["and"] = "None"


entity_list = ["entity", "note"]

edge_params = {
    "to_selected": {
        "condition": "destination",
        "selectbox_label": "接続元",
        "selectbox_index": "source",
        "selectbox_key": "predecessors",
        "connection_column": None,
        "and_column": None,
    },
    "from_selected": {
        "condition": "source",
        "selectbox_label": "接続先",
        "selectbox_index": "destination",
        "selectbox_key": "ancestors",
        "connection_column": None,
        "and_column": None,
    },
}

# ページの初期設定
color_list, config_data, app_data, plantuml_process = initialize_page(
    "Current Reality Tree Viewer"
)

if "current_reality_tree_data" not in config_data:
    st.error(
        """設定ファイルにデータファイル設定がありません。
        settingからファイルを設定してください。"""
    )
    st.stop()
data_key = st.session_state.app_data[st.session_state.app_name]["data"]
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
    add_list,
    scale,
    selected_unique_id,
    upstream_distance,
    downstream_distance,
    selected_entity,
    landscape,
) = load_and_prepare_data(file_path, st.session_state.app_name)

# 未選択の場合はデフォルトエンティティを設定
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
    tmp_entity.setdefault("type", "entity")  # typeがない場合はentityを設定

    tmp_entity["type"] = st.selectbox(
        "タイプ", entity_list, index=entity_list.index(tmp_entity["type"])
    )
    tmp_entity["id"] = st.text_area("課題・状況", tmp_entity["id"])
    tmp_entity["color"] = st.selectbox(
        "色", color_list, index=color_list.index(tmp_entity["color"])
    )

    # 保存するまで表示が変わらないよう、edge本体は更新しない
    tmp_edges = copy.deepcopy(edges)

    params_to = edge_params["to_selected"]
    params_to["connection_column"], params_to["and_column"] = st.columns([7, 2])
    visibility = "visible"
    for i, edge in enumerate(tmp_edges):
        visibility = render_edge_connection(edge, i, visibility, params_to)

    # 関係追加の操作があるため、1つは常に表示
    temp_predecessor = {
        "source": "None",
        "destination": tmp_entity["unique_id"],
        "and": "None",
        "type": "arrow",
    }
    visibility = "visible"
    render_edge_connection_new(temp_predecessor, 0, visibility, params_to)

    st.write("---")

    params_from = edge_params["from_selected"]
    params_from["connection_column"], params_from["and_column"] = st.columns([7, 2])
    visibility = "visible"
    for i, edge in enumerate(tmp_edges):
        visibility = render_edge_connection(edge, i, visibility, params_from)

    # 関係追加の操作があるため、1つは常に表示
    temp_ancestor = {
        "source": tmp_entity["unique_id"],
        "destination": "None",
        "and": "None",
        "type": "arrow",
    }
    visibility = "visible"
    render_edge_connection_new(temp_ancestor, 0, visibility, params_from)

    new_edges = [temp_predecessor, temp_ancestor]

    add_operate_buttons(
        selected_unique_id,
        tmp_entity,
        requirement_manager,
        file_path,
        id_title_dict,
        unique_id_dict,
        tmp_edges=tmp_edges,
        new_edges=new_edges,
    )

# セッション状態にgraph_dataを追加
st.session_state.graph_data = graph_data

# テキストエリアで PlantUML コードが確認可能
st.text_area("PlantUML コード", value=plantuml_code, height=250)
