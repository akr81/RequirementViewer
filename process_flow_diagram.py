import streamlit as st
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
        "type": "deliverable",
        "id": "",
        "color": "None",
        "unique_id": f"{uuid.uuid4()}".replace("-", ""),
    }


pfd_type_list = ["deliverable", "process", "note"]

color_list, config_data, demo, app_data, plantuml_process = initialize_page(
    "Process Flow Diagram Viewer"
)


if demo:
    st.title(st.session_state.app_name)


if "process_flow_diagram_data" not in config_data:
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
) = load_and_prepare_data(file_path, st.session_state.app_name)


# URL のクエリからパラメタを取得
scale = float(st.query_params.get("scale", 1.0))
selected_unique_id = st.query_params.get("selected", [None])
upstream_distance = st.query_params.get(
    "upstream_distance", config_data["upstream_filter_max"]
)
downstream_distance = st.query_params.get(
    "downstream_distance", config_data["downstream_filter_max"]
)


selected_entity = None
if selected_unique_id == [None]:
    # エンティティが選択されていない場合はデフォルトのエンティティを選択してリロード
    default_params = {"selected": "default"}
    st.query_params.setdefault("selected", "default")
    st.rerun()
else:
    if selected_unique_id == "default":
        # デフォルトの場合は何もしない
        pass
    else:
        if selected_unique_id not in unique_id_dict:
            # 存在しないユニークIDが指定された場合は何もしない
            pass
        else:
            selected_entity = [
                d
                for d in requirement_data["nodes"]
                if d["unique_id"] == selected_unique_id
            ][0]

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
    for i, edge in enumerate(tmp_edges):
        # 接続先が選択エンティティ
        if edge["destination"] == selected_unique_id:
            edge.setdefault("comment", "")
            edge["source"] = id_title_dict[
                st.selectbox(
                    "接続元",
                    id_title_list,
                    index=id_title_list.index(unique_id_dict[edge["source"]]),
                    key=f"predecessors{i}",
                )
            ]
            edge["comment"] = st.text_input(
                "説明", edge["comment"], key=f"comment_predecessor{i}"
            )

    # 関係追加の操作があるため、1つは常に表示
    temp_predecessor = {
        "source": None,
        "destination": tmp_entity["unique_id"],
        "comment": None,
    }
    temp_predecessor["source"] = id_title_dict[
        st.selectbox("接続元(新規)", id_title_list, index=id_title_list.index("None"))
    ]
    temp_predecessor["comment"] = st.text_input(
        "説明(新規)", "", key="comment_predecessor_new"
    )

    # 接続先の関係を取得
    for i, edge in enumerate(tmp_edges):
        # 接続元が選択エンティティ
        if edge["source"] == selected_unique_id:
            edge.setdefault("comment", "")
            edge["destination"] = id_title_dict[
                st.selectbox(
                    "接続先",
                    id_title_list,
                    index=id_title_list.index(unique_id_dict[edge["destination"]]),
                    key=f"ancestors{i}",
                )
            ]
            edge["comment"] = st.text_input(
                "説明", edge["comment"], key=f"comment_ancestors{i}"
            )

    # 関係追加の操作があるため、1つは常に表示
    temp_ancestor = {
        "source": tmp_entity["unique_id"],
        "destination": None,
        "comment": None,
    }
    temp_ancestor["destination"] = id_title_dict[
        st.selectbox("接続先(新規)", id_title_list, index=id_title_list.index("None"))
    ]  # 末尾に追加用の空要素を追加
    temp_ancestor["comment"] = st.text_input(
        "説明(新規)", "", key="comment_ancestor_new"
    )

    new_edges = [temp_predecessor, temp_ancestor]
    tmp_edges.extend(new_edges)

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
