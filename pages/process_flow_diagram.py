import streamlit as st
from src.operate_buttons import add_operate_buttons, add_node_selector
from src.bulk_input import render_bulk_input_ui
from src.page_setup import setup_page_layout_and_data  # 変更
from src.utility import (  # copy_file, get_backup_files_for_current_data のみ使用
    get_backup_files_for_current_data,
    copy_file,
    calculate_text_area_height,
    unescape_newline,
    show_backup_diff_preview,
)
import uuid
import copy


def render_edge_connection(
    edge: dict, index: int, visibility: str, params: dict
) -> str:
    # 接続元が選択エンティティ
    if edge[params["condition"]] == params["selected_unique_id"]:
        edge.setdefault("comment", "")
        with params["connection_column"]:
            # unique_id_dict に存在しないIDが入っていた場合は "None" にフォールバック
            current_id = edge[params["selectbox_index"]]
            current_label = params["unique_id_dict"].get(current_id, "None")
            edge[params["selectbox_index"]] = params["id_title_dict"][
                st.selectbox(
                    params["selectbox_label"],
                    params["id_title_list"],
                    index=params["id_title_list"].index(current_label),
                    key=f"{params['selectbox_key']}_{params['selected_unique_id']}_{index}",
                    label_visibility=visibility,
                )
            ]
        with params["description_column"]:
            edge["comment"] = st.text_input(
                "説明",
                unescape_newline(edge["comment"]),
                key=f"comment_{params['selectbox_key']}_{params['selected_unique_id']}_{index}",
                label_visibility=visibility,
            )
        return "collapsed"  # 1つ目の要素は表示し、以降は非表示にする
    return visibility


def render_edge_connection_new(edge: dict, _: int, visibility: str, params: dict):
    expected_index = -1
    if "--- 未選択 ---" in params["id_title_list"]:
        expected_index = params["id_title_list"].index("--- 未選択 ---")
    with params["connection_column"]:
        connection_key = f"{params['selectbox_key']}_new"
        selected_value_from_widget = st.selectbox(
            f"{params['selectbox_label']}(新規)",
            params["id_title_list"],
            index=(
                expected_index if expected_index != -1 else 0
            ),  # 'None' がなければ先頭を選択
            key=connection_key,
            label_visibility=visibility,
        )

        edge[params["selectbox_index"]] = params["id_title_dict"][selected_value_from_widget]
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
    },
    "from_selected": {
        "condition": "source",
        "selectbox_label": "接続先",
        "selectbox_index": "destination",
        "selectbox_key": "successors",
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
selected_unique_id = page_elements["selected_unique_id"]
selected_entity = page_elements["selected_entity"]

# 編集用カラムとPlantUMLコードを page_elements から取得
edit_column = page_elements["edit_column"]
plantuml_code = page_elements["plantuml_code"]

@st.fragment
def render_edit_panel():
    """右側操作パネルの描画（部分再描画対応）"""
    # --- リセット対象キーの登録 ---
    if "clearable_new_connection_keys" not in st.session_state:
        st.session_state.clearable_new_connection_keys = {}
    # このページの新規接続用ウィジェットのキーを登録
    # render_edge_connection_new で使用されるキーと一致させる
    st.session_state.clearable_new_connection_keys["Process Flow Diagram Viewer"] = [
        f"{edge_params['to_selected']['selectbox_key']}_new",  # e.g., "predecessors_new"
        f"comment_{edge_params['to_selected']['selectbox_key']}_new",  # e.g., "comment_predecessors_new"
        f"{edge_params['from_selected']['selectbox_key']}_new",  # e.g., "successors_new"
        f"comment_{edge_params['from_selected']['selectbox_key']}_new",  # e.g., "comment_successors_new"
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
            key="selected_backup_file",
        )
    show_backup_diff_preview(requirement_data)
    # ダイアグラムのタイトルを表示
    diagram_title = st.text_input(
        "PFDタイトル",
        value=requirement_data.get("title", ""),
        key="diagram_title_input",
    )
    requirement_data["title"] = diagram_title

    # --- タブ切り替え: 個別入力 / 一括入力 ---
    tab_individual, tab_bulk = st.tabs(["✏️ 個別入力", "📝 一括入力"])

    with tab_individual:
        _render_individual_edit()

    with tab_bulk:
        render_bulk_input_ui(
            nodes=requirement_data.get("nodes", []),
            requirement_manager=requirement_manager,
            file_path=file_path,
            type_list=pfd_type_list,
            display_key="title",
            page_key_prefix="pfd",
            extra_fields={"finished": False},
            metadata_columns=[
                {"key": "color", "name": "色", "type": str, "default": "None"},
                {"key": "finished", "name": "完了", "type": bool, "default": False},
            ],
        )

def _render_individual_edit():
    """個別エンティティ編集タブの内容を描画する。"""
    add_node_selector(id_title_list, id_title_dict, unique_id_dict, selected_unique_id)
    tmp_entity = copy.deepcopy(selected_entity) or {}
    tmp_entity["unique_id"] = f"{uuid.uuid4()}".replace("-", "")
    tmp_entity.setdefault("color", "None")
    tmp_entity.setdefault("type", "entity")
    tmp_entity.setdefault("finished", False)

    top_button_container = st.container()

    tmp_entity["type"] = st.selectbox(
        "タイプ", pfd_type_list, index=pfd_type_list.index(tmp_entity.get("type", "entity"))
    )
    title_value = tmp_entity.get("title", "") or tmp_entity.get("id", "")
    tmp_entity["title"] = st.text_area(
        "プロセス名 / タイトル",
        unescape_newline(title_value),
        height=calculate_text_area_height(unescape_newline(title_value)),
        key=f"pfd_title_{selected_unique_id}",
    )

    tmp_entity["finished"] = st.checkbox(
        "完了",
        value=tmp_entity.get("finished", False),
        key=f"pfd_finished_{selected_unique_id}",
    )

    tmp_entity["color"] = st.selectbox(
        "色",
        color_list,
        index=color_list.index(tmp_entity.get("color", "None")),
        key=f"pfd_color_{selected_unique_id}",
    )
    
    tmp_edges = copy.deepcopy(requirement_data["edges"])

    params_to = edge_params["to_selected"]
    params_to["selected_unique_id"] = selected_unique_id
    params_to["id_title_dict"] = id_title_dict
    params_to["unique_id_dict"] = unique_id_dict
    params_to["id_title_list"] = id_title_list
    params_to["connection_column"], params_to["description_column"] = st.columns([1, 1])
    visibility = "visible"
    for i, edge in enumerate(tmp_edges):
        visibility = render_edge_connection(
            edge, i, visibility, edge_params["to_selected"]
        )

    temp_predecessor = {
        "source": "None",
        "destination": tmp_entity["unique_id"],
        "comment": "",
        "type": "arrow",
    }
    visibility = "visible"
    render_edge_connection_new(
        temp_predecessor, 0, visibility, edge_params["to_selected"]
    )

    st.write("---")

    params_from = edge_params["from_selected"]
    params_from["selected_unique_id"] = selected_unique_id
    params_from["id_title_dict"] = id_title_dict
    params_from["unique_id_dict"] = unique_id_dict
    params_from["id_title_list"] = id_title_list
    params_from["connection_column"], params_from["description_column"] = st.columns(
        [1, 1]
    )
    visibility = "visible"
    for i, edge in enumerate(tmp_edges):
        visibility = render_edge_connection(
            edge, i, visibility, edge_params["from_selected"]
        )

    temp_successor = {
        "source": tmp_entity["unique_id"],
        "destination": "None",
        "comment": "",
        "type": "arrow",
    }
    visibility = "visible"
    render_edge_connection_new(
        temp_successor, 0, visibility, edge_params["from_selected"]
    )

    new_edges = [temp_predecessor, temp_successor]

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
            key_suffix="top",
            display_key="title",
        )

    add_operate_buttons(
        selected_unique_id,
        tmp_entity,
        requirement_manager,
        file_path,
        id_title_dict,
        unique_id_dict,
        tmp_edges=tmp_edges,
        new_edges=new_edges,
        key_suffix="bottom",
        display_key="title",
    )


with edit_column:
    render_edit_panel()

st.session_state.graph_data = graph_data
