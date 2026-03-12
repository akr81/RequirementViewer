import streamlit as st
from src.operate_buttons import add_operate_buttons, add_node_selector
from src.page_setup import setup_page_layout_and_data  # 変更
from src.bulk_input import render_bulk_input_ui
from src.utility import (  # copy_file, get_backup_files_for_current_data のみ使用
    get_backup_files_for_current_data,
    copy_file,
    calculate_text_area_height,
    unescape_newline,
    show_backup_diff_preview,
)
import hjson
import os
import uuid
import copy


@st.cache_data
def load_entity_types() -> list[str]:
    """JSONファイルからエンティティタイプ一覧を読み込む。

    Returns:
        list[str]: エンティティタイプのリスト
    """
    with open(os.path.join("setting", "entity_types.json"), "r", encoding="utf-8") as f:
        entity_types = hjson.load(f)
    return entity_types


@st.cache_data
def load_relation_types() -> list[str]:
    """JSONファイルから関係タイプ一覧を読み込む。

    Returns:
        list[str]: 関係タイプのリスト
    """
    with open(
        os.path.join("setting", "relation_types.json"), "r", encoding="utf-8"
    ) as f:
        relation_types = hjson.load(f)
    return relation_types


@st.cache_data
def load_note_types() -> list[str]:
    """JSONファイルからノートタイプ一覧を読み込む。

    Returns:
        list[str]: ノートタイプのリスト
    """
    with open(os.path.join("setting", "note_types.json"), "r", encoding="utf-8") as f:
        note_types = hjson.load(f)
    return note_types


# エンティティタイプと関係タイプを読み込む
entity_types = load_entity_types()
relation_types = load_relation_types()
note_types = load_note_types()

# ページ全体のデータ読み込みと基本設定
page_elements = setup_page_layout_and_data(
    "Requirement Diagram Viewer",
    default_entity_creation_args={"entity_types": entity_types},
)

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
    st.session_state.clearable_new_connection_keys["Requirement Diagram Viewer"] = [
        "new_relation_type",
        "new_relation_destination",
        "new_relation_note_type",
        "new_relation_note_text",
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
        "REQタイトル",
        value=requirement_data.get("title", ""),
        key="diagram_title_input",  # ページ全体の設定なので固定keyでよい
    )
    requirement_data["title"] = diagram_title  # タイトルを更新

    # --- タブ切り替え: 個別入力 / 一括入力 ---
    tab_individual, tab_bulk = st.tabs(["✏️ 個別入力", "📝 一括入力"])

    with tab_individual:
        _render_individual_edit()

    with tab_bulk:
        render_bulk_input_ui(
            nodes=requirement_data.get("nodes", []),
            requirement_manager=requirement_manager,
            file_path=file_path,
            type_list=entity_types,
            display_key="title",
            page_key_prefix="req",
            metadata_columns=[
                {"key": "color", "name": "色", "type": str, "default": "None"},
            ],
        )

def _render_individual_edit():
    """個別エンティティ編集タブの内容を描画する。"""
    add_node_selector(id_title_list, id_title_dict, unique_id_dict, selected_unique_id)

    # 直接データ操作はせず、コピー(uuidは異なる)に対して操作する
    tmp_entity = copy.deepcopy(selected_entity) or {}
    tmp_entity["unique_id"] = f"{uuid.uuid4()}".replace("-", "")
    tmp_entity.setdefault("color", "None")  # colorがない場合はNoneを設定

    # 後でボタンを配置する
    top_button_container = st.container()

    tmp_entity["type"] = st.selectbox(
        "エンティティタイプ",
        entity_types,
        index=entity_types.index(tmp_entity.get("type", "Requirement")),
        key=f"entity_type_{selected_unique_id}",
    )
    tmp_entity["title"] = st.text_input(
        "タイトル",
        tmp_entity.get("title", ""),
        key=f"entity_title_{selected_unique_id}",
    )
    tmp_entity["id"] = st.text_input(
        "ID",
        tmp_entity.get("id", ""),
        key=f"entity_id_{selected_unique_id}",
    )
    tmp_entity["text"] = st.text_area(
        "説明",
        unescape_newline(tmp_entity.get("text", "")),
        height=calculate_text_area_height(unescape_newline(tmp_entity.get("text", ""))),
        key=f"entity_text_{selected_unique_id}",
    )
    
    tmp_entity["color"] = st.selectbox(
        "色",
        color_list,
        index=color_list.index(tmp_entity.get("color", "None")),
        key=f"entity_color_{selected_unique_id}",
    )

    # テキストエリアでエンティティの詳細情報を入力
    # 関係は複数ありえるため、繰り返し表示させる
    # また、関係の追加を行うケースがあるため、最初の項目は空にしておき2つめ以後は設定されているデータを表示する
    relation_column, destination_column = st.columns(2)
    tmp_edges = copy.deepcopy(requirement_data["edges"])
    visibility = "visible"
    for i, tmp_edge in enumerate(tmp_edges):

        # 接続元が選択エンティティでないものはスキップ
        if tmp_edge["source"] != selected_unique_id:
            continue

        relation_column, destination_column = st.columns(2)
        with relation_column:
            tmp_edge["type"] = st.selectbox(
                "関係タイプ",
                relation_types,
                relation_types.index(tmp_edge["type"]),
                key=f"relation_type{i}",
                label_visibility=visibility,
            )
        with destination_column:
            tmp_edge["destination"] = id_title_dict[
                st.selectbox(
                    "接続先",
                    id_title_list,
                    id_title_list.index(unique_id_dict[tmp_edge["destination"]]),
                    key=f"destination{i}",
                    label_visibility=visibility,
                )
            ]
        expander_title = (
            "関係の注釈"
            if "text" in tmp_edge["note"] and tmp_edge["note"]["text"] != ""
            else "関係の注釈(なし)"
        )
        with st.expander(
            expander_title,
            expanded=bool("text" in tmp_edge["note"] and tmp_edge["note"]["text"]),
        ):
            tmp_edge["note"]["type"] = st.selectbox(
                "注釈タイプ",
                note_types,
                key=f"note_type_{selected_unique_id}_{i}",
                index=note_types.index(tmp_edge.get("note").get("type", "None")),
            )
            if "note" in tmp_edge:
                tmp_edge["note"]["text"] = st.text_area(
                    "説明",
                    unescape_newline(tmp_edge.get("note").get("text", "")),
                    key=f"relation_note_{selected_unique_id}_{i}",
                    height=calculate_text_area_height(unescape_newline(tmp_edge.get("note").get("text", ""))),
                )
            else:
                tmp_edge["note"] = st.text_area(
                    "説明",
                    "",
                    key=f"relation_note_{selected_unique_id}_{i}",
                    height=calculate_text_area_height(""),
                )
        visibility = "collapsed"  # 1つ目の要素は表示し、以降は非表示にする

    # 関係追加の操作があるため、1つは常に表示
    relation_column_new, destination_column_new = st.columns(2)

    with relation_column_new:
        relation_type = st.selectbox(
            "関係タイプ(新規)", relation_types, key="new_relation_type"
        )
    with destination_column_new:
        destination_unique_id = id_title_dict[
            st.selectbox(
                "接続先(新規)",
                id_title_list,
                index=id_title_list.index("--- 未選択 ---"),
                key="new_relation_destination",
            )
        ]  # 末尾に追加用の空要素を追加
    if relation_type == "None" and destination_unique_id != "None":
        # エラーを避けるため、関係タイプがNoneの場合はデフォルトの関係タイプを設定
        relation_type = relation_types[1]
    with st.expander("関係の注釈(新規)", expanded=True):
        relation_note = {}
        relation_note["type"] = st.selectbox(
            "注釈タイプ", note_types, key="new_relation_note_type"
        )
        relation_note["text"] = st.text_area(
            "説明",
            "",
            key="new_relation_note_text",
            height=calculate_text_area_height(""),
        )

    new_edge = []
    if not relation_note:
        new_edge.append(
            {
                "source": tmp_entity["unique_id"],
                "type": relation_type,
                "destination": destination_unique_id,
                "note": {},
            }
        )
    else:
        new_edge.append(
            {
                "source": tmp_entity["unique_id"],
                "type": relation_type,
                "destination": destination_unique_id,
                "note": relation_note,
            }
        )

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
            new_edges=new_edge,
            key_suffix="top"  # 重複エラー回避用
        )

    add_operate_buttons(
        selected_unique_id,
        tmp_entity,
        requirement_manager,
        file_path,
        id_title_dict,
        unique_id_dict,
        tmp_edges=tmp_edges,
        new_edges=new_edge,
        key_suffix="bottom"  # 重複エラー回避用
    )


with edit_column:
    render_edit_panel()
    
st.session_state.graph_data = graph_data
