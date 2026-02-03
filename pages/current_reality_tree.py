import streamlit as st
from src.utility import (
    get_next_and_number,
    get_backup_files_for_current_data,
    copy_file,
)  # draw_diagram_column を削除
from src.operate_buttons import add_operate_buttons
from src.diagram_configs import *
from src.page_setup import setup_page_layout_and_data  # 変更
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

# ページ全体のデータ読み込みと基本設定
page_elements = setup_page_layout_and_data("Current Reality Tree Viewer")

# setup_page_layout_and_data から返された要素を変数に展開
color_list = page_elements["color_list"]
config_data = page_elements["config_data"]
app_data = page_elements["app_data"]
file_path = page_elements["file_path"]
requirement_data = page_elements["requirement_data"]
nodes = page_elements["nodes"]
edges = page_elements["edges"]  # tmp_edges の元データとして必要
requirement_manager = page_elements["requirement_manager"]
graph_data = page_elements["graph_data"]
id_title_dict = page_elements["id_title_dict"]
unique_id_dict = page_elements["unique_id_dict"]
id_title_list = page_elements["id_title_list"]
add_list = page_elements["add_list"]
scale = page_elements["scale"]
selected_unique_id = page_elements["selected_unique_id"]
upstream_distance = page_elements["upstream_distance"]
downstream_distance = page_elements["downstream_distance"]
selected_entity = page_elements["selected_entity"]
landscape = page_elements["landscape"]

# 編集用カラムとPlantUMLコードを page_elements から取得
edit_column = page_elements["edit_column"]
plantuml_code = page_elements["plantuml_code"]


with edit_column:
    # --- リセット対象キーの登録 ---
    if "clearable_new_connection_keys" not in st.session_state:
        st.session_state.clearable_new_connection_keys = {}
    # このページの新規接続用ウィジェットのキーを登録
    # render_edge_connection_new で使用されるキーと一致させる
    st.session_state.clearable_new_connection_keys["Current Reality Tree Viewer"] = [
        f"{edge_params['to_selected']['selectbox_key']}_new",  # e.g., "predecessors_new"
        f"and_{edge_params['to_selected']['selectbox_key']}_new",  # e.g., "and_predecessors_new"
        f"{edge_params['from_selected']['selectbox_key']}_new",  # e.g., "ancestors_new"
        f"and_{edge_params['from_selected']['selectbox_key']}_new",  # e.g., "and_ancestors_new"
    ]
    title_column, file_selector_column = st.columns([4, 4])
    with title_column:
        st.write("### データ編集")
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
    # ダイアグラムのタイトルを表示
    diagram_title = st.text_input(
        "CRTタイトル",
        value=requirement_data.get("title", ""),
        key="diagram_title_input",
    )
    requirement_data["title"] = diagram_title  # タイトルを更新
    
    # 直接データ操作はせず、コピー(uuidは異なる)に対して操作する
    tmp_entity = copy.deepcopy(selected_entity)
    tmp_entity["unique_id"] = f"{uuid.uuid4()}".replace("-", "")
    tmp_entity.setdefault("color", "None")  # colorがない場合はNoneを設定
    tmp_entity.setdefault("type", "entity")  # typeがない場合はentityを設定

    # 後でボタンを配置する
    top_button_container = st.container()

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

    # 上部のボタンを配置
    with top_button_container:
        add_operate_buttons(
            selected_unique_id,
            tmp_entity,
            requirement_manager,
            file_path,
            id_title_dict,
            unique_id_dict,
            tmp_edges=tmp_edges,
            new_edges=new_edges,
            key_suffix="top"  # 重複エラー回避用
        )

    # 下部のボタンを配置
    add_operate_buttons(
        selected_unique_id,
        tmp_entity,
        requirement_manager,
        file_path,
        id_title_dict,
        unique_id_dict,
        tmp_edges=tmp_edges,
        new_edges=new_edges,
        key_suffix="bottom"  # 重複エラー回避用
    )

# セッション状態にgraph_dataを追加
st.session_state.graph_data = graph_data

# テキストエリアで PlantUML コードが確認可能
st.text_area("PlantUML コード", value=plantuml_code, height=250)
