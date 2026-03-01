import streamlit as st
from src.utility import (
    get_next_and_number,
    get_backup_files_for_current_data,
    copy_file,
    calculate_text_area_height,
    unescape_newline,
    show_backup_diff_preview,
)  # draw_diagram_column を削除
from src.operate_buttons import add_operate_buttons, add_node_selector
from src.page_setup import setup_page_layout_and_data  # 変更
import uuid
import copy


def render_edge_connection(
    edge: dict, index: int, visibility: str, params: dict, entity_type: str = "entity"
) -> str:
    if edge[params["condition"]] == params["selected_unique_id"]:
        with params["connection_column"]:
            # unique_id_dict に存在しないIDが入っていた場合は "None" にフォールバック
            current_id = edge[params["selectbox_index"]]
            current_label = params["unique_id_dict"].get(current_id, "None")
            edge[params["selectbox_index"]] = params["id_title_dict"][
                st.selectbox(
                    params["selectbox_label"],
                    params["id_title_list"],
                    index=params["id_title_list"].index(current_label),
                    key=f"{params['selectbox_key']}{index}",
                    label_visibility=visibility,
                )
            ]
        with params["and_column"]:
            edge["and"] = st.selectbox(
                "and",
                params["add_list"],
                index=params["add_list"].index(edge["and"]),
                key=f"and_{params['selectbox_key']}{index}",
                label_visibility=visibility,
            )
            edge["and"] = get_next_and_number(params["add_list"], edge["and"])
            if not edge["and"]:
                edge["and"] = "None"
        if entity_type == "note":
            edge["type"] = "flat_long"

        return "collapsed"  # 1つ目の要素は表示し、以降は非表示にする
    return visibility


def render_edge_connection_new(edge: dict, _: int, visibility: str, params: dict):
    with params["connection_column"]:
        edge[params["selectbox_index"]] = params["id_title_dict"][
            st.selectbox(
                f"{params['selectbox_label']}(新規)",
                params["id_title_list"],
                index=params["id_title_list"].index("None"),
                key=f"{params['selectbox_key']}_new",
                label_visibility=visibility,
            )
        ]
    with params["and_column"]:
        edge["and"] = st.selectbox(
            "and",
            params["add_list"],
            index=params["add_list"].index("None"),
            key=f"and_{params['selectbox_key']}_new",
            label_visibility=visibility,
        )
        edge["and"] = get_next_and_number(params["add_list"], edge["and"])
        if not edge["and"]:
            edge["and"] = "None"


entity_list = ["entity", "note"]

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
            key="selected_backup_file",
        )
    show_backup_diff_preview(requirement_data)
    add_node_selector(id_title_list, id_title_dict, unique_id_dict, selected_unique_id)
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
    tmp_entity["text"] = st.text_area(
        "課題・状況",
        unescape_newline(tmp_entity.get("text", "")),
        height=calculate_text_area_height(unescape_newline(tmp_entity.get("text", ""))),
        key=f"crt_text_{selected_unique_id}",
    )
    
    tmp_entity["color"] = st.selectbox(
        "色",
        color_list,
        index=color_list.index(tmp_entity["color"]),
        key=f"crt_color_{selected_unique_id}",
    )

    # 保存するまで表示が変わらないよう、edge本体は更新しない
    tmp_edges = copy.deepcopy(edges)

    # 接続関係の描画をループ化
    new_edges = []
    connection_configs = [
        (edge_params["to_selected"], "destination", "source"),
        (edge_params["from_selected"], "source", "destination"),
    ]
    
    for idx, (params, dest_key, src_key) in enumerate(connection_configs):
        if idx > 0:
            st.write("---")  # to と from の区切り線

        # データ参照を params に追加（関数シグネチャを変えずにグローバル依存を除去）
        params["selected_unique_id"] = selected_unique_id
        params["id_title_dict"] = id_title_dict
        params["unique_id_dict"] = unique_id_dict
        params["id_title_list"] = id_title_list
        params["add_list"] = add_list
        params["connection_column"], params["and_column"] = st.columns([7, 2])
        visibility = "visible"
        for i, edge in enumerate(tmp_edges):
            visibility = render_edge_connection(edge, i, visibility, params, tmp_entity["type"])

        # 関係追加の操作があるため、1つは常に表示
        temp_edge = {
            dest_key: tmp_entity["unique_id"] if dest_key == "source" else "None",
            src_key: "None" if dest_key == "source" else tmp_entity["unique_id"],
            "and": "None",
            "type": "arrow",
        }
        # dest_key == "source" なら connection_configs[1] (from_selected) 相当
        # dest_key == "destination" なら connection_configs[0] (to_selected) 相当
        # 上記の辞書キーは、temp_predecessorとtemp_ancestorの生成ロジックを統合しています
        
        visibility = "visible"
        render_edge_connection_new(temp_edge, 0, visibility, params)
        new_edges.append(temp_edge)

    # 操作ボタンの共通引数辞書を作成
    btn_kwargs = {
        "selected_unique_id": selected_unique_id,
        "tmp_entity": tmp_entity,
        "requirement_manager": requirement_manager,
        "file_path": file_path,
        "id_title_dict": id_title_dict,
        "unique_id_dict": unique_id_dict,
        "tmp_edges": tmp_edges,
        "new_edges": new_edges,
        "display_key": "text",
    }

    # 上部のボタンを配置
    with top_button_container:
        add_operate_buttons(**btn_kwargs, key_suffix="top")

    # 下部のボタンを配置
    add_operate_buttons(**btn_kwargs, key_suffix="bottom")



with edit_column:
    render_edit_panel()
    
st.session_state.graph_data = graph_data
