import streamlit as st
from src.requirement_manager import RequirementManager
from src.requirement_graph import RequirementGraph
from src.utility import (
    load_source_data,
    build_mapping,
    build_sorted_list,
)
from src.diagram_column import draw_diagram_column
from src.operate_buttons import add_operate_buttons
from src.page_setup import initialize_page
import uuid
import copy
import datetime
import pprint


def get_default_entity() -> dict:
    """Get default entity data.

    Returns:
        entity_types: Entity data list
    """
    return {
        "id": "",
        "necessary_assumption": "",
        "strategy": "",
        "parallel_assumption": "",
        "tactics": "",
        "sufficient_assumption": "",
        "unique_id": f"{uuid.uuid4()}".replace("-", ""),
    }


color_list, config_data, demo, app_data, plantuml_process = initialize_page(
    "Strategy and Tactics Tree Viewer"
)


if demo:
    st.title(st.session_state.app_name)

data_key = st.session_state.app_data[st.session_state.app_name]["data"]
if data_key not in config_data:
    st.error(
        """設定ファイルにデータファイル設定がありません。
        settingからファイルを設定してください。"""
    )
    st.stop()

file_path = config_data[data_key]

requirement_data = load_source_data(file_path)
requirement_manager = RequirementManager(requirement_data)
graph_data = RequirementGraph(requirement_data, st.session_state.app_name)

# IDとタイトルをキー, ユニークIDを値とする辞書とその逆を作成
nodes = requirement_data["nodes"]
id_title_dict = build_mapping(nodes, "id", "unique_id", add_empty=True)
unique_id_dict = build_mapping(nodes, "unique_id", "id", add_empty=True)
id_title_list = build_sorted_list(nodes, "id", prepend=["None"])

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

    tmp_entity["id"] = st.text_input("ID", tmp_entity["id"])
    tmp_entity["necessary_assumption"] = st.text_area(
        "なぜこの変化が必要か？", tmp_entity["necessary_assumption"]
    )
    tmp_entity["strategy"] = st.text_area(
        "**何がこの変化の具体的な目的なのか？**", tmp_entity["strategy"]
    )
    tmp_entity["parallel_assumption"] = st.text_area(
        "なぜこの戦略をとるのか？", tmp_entity["parallel_assumption"]
    )
    tmp_entity["tactics"] = st.text_area(
        "**どのようにこの変化を達成するのか？**", tmp_entity["tactics"]
    )
    tmp_entity["sufficient_assumption"] = st.text_area(
        "なぜより詳細な具体策とアクションが必要なのか？",
        tmp_entity["sufficient_assumption"],
    )
    tmp_entity["color"] = st.selectbox(
        "色", color_list, index=color_list.index(tmp_entity["color"])
    )

    # 接続元の関係を取得
    # 直接edgeは操作せず、コピーに対して操作する
    tmp_edges = copy.deepcopy(requirement_data["edges"])
    for i, edge in enumerate(tmp_edges):
        if edge["source"] != selected_unique_id:
            continue
        edge["destination"] = id_title_dict[
            st.selectbox(
                "接続先",
                id_title_list,
                id_title_list.index(unique_id_dict[edge["destination"]]),
                key=f"destination{i}",
            )
        ]

    # 関係追加の操作があるため、1つは常に表示
    destination_unique_id = id_title_dict[
        st.selectbox("接続先(新規)", id_title_list, index=id_title_list.index("None"))
    ]  # 末尾に追加用の空要素を追加

    new_edge = {
        "source": tmp_entity["unique_id"],
        "destination": destination_unique_id,
        "type": "arrow",
    }

    tmp_edges.append(new_edge)

    print(f"=={datetime.datetime.now()}==")

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
