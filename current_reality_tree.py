import streamlit as st
from src.utility import (
    get_next_and_number,
)
from src.diagram_column import draw_diagram_column
from src.operate_buttons import add_operate_buttons
from src.page_setup import initialize_page, load_and_prepare_data
import uuid
import copy


def get_default_entity() -> dict:
    """Get default entity data.

    Returns:
        entity_types: Entity data list
    """
    return {
        "id": "",
        "color": "None",
        "unique_id": f"{uuid.uuid4()}".replace("-", ""),
    }


entity_list = ["entity", "note"]

# ページの初期設定
color_list, config_data, demo, app_data, plantuml_process = initialize_page(
    "Current Reality Tree Viewer"
)

if demo:
    st.title(st.session_state.app_name)

if "current_reality_tree_data" not in config_data:
    st.error(
        """設定ファイルにデータファイル設定がありません。
        settingからファイルを設定してください。"""
    )
    st.stop()
data_key = st.session_state.app_data[st.session_state.app_name]["data"]
file_path = config_data[data_key]

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
) = load_and_prepare_data(file_path, st.session_state.app_name)

# 未選択の場合はデフォルトエンティティを設定
if not selected_entity:
    selected_entity = get_default_entity()

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
)

with edit_column:
    st.write("## データ編集")
    # 直接データ操作はせず、コピー(uuidは異なる)に対して操作する
    tmp_entity = copy.deepcopy(selected_entity)
    tmp_entity["unique_id"] = f"{uuid.uuid4()}".replace("-", "")
    tmp_entity.setdefault("color", "None")  # colorがない場合はNoneを設定
    tmp_entity.setdefault("type", "entity")  # typeがない場合はentityを設定
    tmp_entity["type"] = "entity"

    tmp_entity["type"] = st.selectbox(
        "タイプ", entity_list, index=entity_list.index(tmp_entity["type"])
    )
    tmp_entity["id"] = st.text_area("課題・状況", tmp_entity["id"])
    tmp_entity["color"] = st.selectbox(
        "色", color_list, index=color_list.index(tmp_entity["color"])
    )

    from_relations = []
    temp_predecessors = []
    # 保存するまで表示が変わらないよう、edge本体は更新しない
    tmp_edges = copy.deepcopy(edges)

    source_column_loop, source_and_column_loop = st.columns([7, 2])
    for i, edge in enumerate(tmp_edges):
        # 接続先が選択エンティティ
        if edge["destination"] == selected_unique_id:
            with source_column_loop:
                edge["source"] = id_title_dict[
                    st.selectbox(
                        "接続元",
                        id_title_list,
                        index=id_title_list.index(unique_id_dict[edge["source"]]),
                        key=f"predecessors{i}",
                    )
                ]
            with source_and_column_loop:
                edge["and"] = st.selectbox(
                    "and",
                    add_list,
                    index=add_list.index(edge["and"]),
                    key=f"and_predecessors{i}",
                )
                edge["and"] = get_next_and_number(add_list, edge["and"])
                if not edge["and"]:
                    edge["and"] = "None"

    # 関係追加の操作があるため、1つは常に表示
    temp_predecessor = {
        "source": "None",
        "destination": tmp_entity["unique_id"],
        "and": "None",
        "type": "arrow",
    }
    source_column, source_and_column = st.columns([7, 2])
    with source_column:
        temp_predecessor["source"] = id_title_dict[
            st.selectbox(
                "接続元(新規)",
                id_title_list,
                index=id_title_list.index("None"),
                key=f"predecessors_new",
            )
        ]
    with source_and_column:
        temp_predecessor["and"] = st.selectbox(
            "and", add_list, index=add_list.index("None"), key=f"and_predecessors"
        )
        temp_predecessor["and"] = get_next_and_number(add_list, temp_predecessor["and"])
        if not temp_predecessor["and"]:
            temp_predecessor["and"] = "None"

    loop_destination_column, loop_destination_and_column = st.columns([7, 2])
    for i, edge in enumerate(tmp_edges):
        if edge["source"] == selected_unique_id:
            with loop_destination_column:
                # 接続元が選択エンティティ
                edge["destination"] = id_title_dict[
                    st.selectbox(
                        "接続先",
                        id_title_list,
                        id_title_list.index(unique_id_dict[edge["destination"]]),
                        key=f"destination{i}",
                    )
                ]
            with loop_destination_and_column:
                edge["and"] = st.selectbox(
                    "and", add_list, add_list.index(edge["and"]), key=f"and{i}"
                )
                edge["and"] = get_next_and_number(add_list, edge["and"])
                if not edge["and"]:
                    edge["and"] = "None"

    # 関係追加の操作があるため、1つは常に表示
    temp_ancestor = {
        "source": tmp_entity["unique_id"],
        "destination": "None",
        "and": "None",
        "type": "arrow",
    }
    destination_column, destination_and_column = st.columns([7, 2])
    with destination_column:
        temp_ancestor["destination"] = id_title_dict[
            st.selectbox(
                "接続先(新規)", id_title_list, index=id_title_list.index("None")
            )
        ]
    with destination_and_column:
        temp_ancestor["and"] = st.selectbox("and", add_list, add_list.index("None"))
        temp_ancestor["and"] = get_next_and_number(add_list, temp_ancestor["and"])
        if not temp_ancestor["and"]:
            temp_ancestor["and"] = "None"

    tmp_edges.append(temp_predecessor)
    tmp_edges.append(temp_ancestor)

    add_operate_buttons(
        selected_unique_id,
        tmp_entity,
        requirement_manager,
        file_path,
        id_title_dict,
        unique_id_dict,
        tmp_edges=tmp_edges,
    )

# セッション状態にgraph_dataを追加
st.session_state.graph_data = graph_data

# テキストエリアで PlantUML コードが確認可能
st.text_area("PlantUML コード", value=plantuml_code, height=250)
