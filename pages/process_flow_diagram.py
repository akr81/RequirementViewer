import streamlit as st
from src.operate_buttons import add_operate_buttons
from src.diagram_configs import *
from src.page_setup import setup_page_layout_and_data  # 変更
from src.utility import (  # copy_file, get_backup_files_for_current_data のみ使用
    get_backup_files_for_current_data,
    copy_file,
)
import copy


def render_edge_connection(
    edge: dict, index: int, visibility: str, params: dict
) -> str:
    # 接続元が選択エンティティ
    if edge[params["condition"]] == selected_unique_id:
        edge.setdefault("comment", "")
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
        with params["description_column"]:
            edge["comment"] = st.text_input(
                "説明",
                edge["comment"],
                key=f"comment_{params['selectbox_key']}{index}",
                label_visibility=visibility,
            )
        return "collapsed"  # 1つ目の要素は表示し、以降は非表示にする
    return visibility


def render_edge_connection_new(edge: dict, _: int, visibility: str, params: dict):
    expected_index = -1
    if "None" in id_title_list:
        expected_index = id_title_list.index("None")
    with params["connection_column"]:
        connection_key = f"{params['selectbox_key']}_new"
        selected_value_from_widget = st.selectbox(
            f"{params['selectbox_label']}(新規)",
            id_title_list,
            index=(
                expected_index if expected_index != -1 else 0
            ),  # 'None' がなければ先頭を選択
            key=connection_key,
            label_visibility=visibility,
        )

        edge[params["selectbox_index"]] = id_title_dict[selected_value_from_widget]
    with params["description_column"]:
        comment_key = f"comment_{params['selectbox_key']}_new"
        edge["comment"] = st.text_input(
            "説明(新規)",
            value="",  # 明示的にデフォルト値を設定
            key=comment_key,
            label_visibility=visibility,
        )


pfd_type_list = ["deliverable", "process", "note", "cloud"]

edge_params = {
    "to_selected": {
        "condition": "destination",
        "selectbox_label": "接続元",
        "selectbox_index": "source",
        "selectbox_key": "predecessors",
        "connection_column": None,
        "description_column": None,
    },
    "from_selected": {
        "condition": "source",
        "selectbox_label": "接続先",
        "selectbox_index": "destination",
        "selectbox_key": "ancestors",
        "connection_column": None,
        "description_column": None,
    },
}

# ページ全体のデータ読み込みと基本設定
page_elements = setup_page_layout_and_data("Process Flow Diagram Viewer")

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
# add_list は Process Flow Diagram では使われない
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
    st.session_state.clearable_new_connection_keys["Process Flow Diagram Viewer"] = [
        f"{edge_params['to_selected']['selectbox_key']}_new",  # e.g., "predecessors_new"
        f"comment_{edge_params['to_selected']['selectbox_key']}_new",  # e.g., "comment_predecessors_new"
        f"{edge_params['from_selected']['selectbox_key']}_new",  # e.g., "ancestors_new"
        f"comment_{edge_params['from_selected']['selectbox_key']}_new",  # e.g., "comment_ancestors_new"
    ]

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
        "タイプ", pfd_type_list, index=pfd_type_list.index(tmp_entity["type"])
    )
    tmp_entity["id"] = st.text_area("課題・状況", tmp_entity["id"])
    tmp_entity["color"] = st.selectbox(
        "色", color_list, index=color_list.index(tmp_entity["color"])
    )

    # 接続元の関係を取得
    # 直接edgeは操作せず、コピーに対して操作する
    tmp_edges = copy.deepcopy(requirement_data["edges"])

    params_to = edge_params["to_selected"]
    params_to["connection_column"], params_to["description_column"] = st.columns([1, 1])
    visibility = "visible"
    for i, edge in enumerate(tmp_edges):
        visibility = render_edge_connection(
            edge, i, visibility, edge_params["to_selected"]
        )

    # 関係追加の操作があるため、1つは常に表示
    temp_predecessor = {
        "source": "None",  # selectboxの選択肢に合わせる
        "destination": tmp_entity["unique_id"],
        "comment": "",  # text_inputのデフォルトに合わせる
        "type": "arrow",
    }

    visibility = "visible"
    render_edge_connection_new(
        temp_predecessor, 0, visibility, edge_params["to_selected"]
    )

    st.write("---")

    # 接続先の関係を取得
    params_from = edge_params["from_selected"]
    params_from["connection_column"], params_from["description_column"] = st.columns(
        [1, 1]
    )
    visibility = "visible"
    for i, edge in enumerate(tmp_edges):
        visibility = render_edge_connection(
            edge, i, visibility, edge_params["from_selected"]
        )

    # 関係追加の操作があるため、1つは常に表示
    temp_ancestor = {
        "source": tmp_entity["unique_id"],
        "destination": "None",  # selectboxの選択肢に合わせる
        "comment": "",  # text_inputのデフォルトに合わせる
        "type": "arrow",
    }

    visibility = "visible"
    render_edge_connection_new(
        temp_ancestor, 0, visibility, edge_params["from_selected"]
    )

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
