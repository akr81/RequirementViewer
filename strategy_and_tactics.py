import streamlit as st
from src.requirement_manager import RequirementManager
from src.utility import (
    start_plantuml_server,
    load_config,
    load_source_data,
    load_app_data,
    load_colors,
)
from src.diagram_column import draw_diagram_column
from src.operate_buttons import add_operate_buttons
import uuid
import copy


@st.cache_data
def get_id_title_dict(requirement_data: list[dict]) -> dict:
    """Get ID and title dictionary from requirement data.

    Args:
        requirement_data (list[dict]): Requirement data list

    Returns:
        dict: ID and title dictionary
    """
    id_title_dict = {
        requirement["id"]: requirement["unique_id"] for requirement in requirement_data
    }
    id_title_dict["None"] = "None"  # 削除用の空要素を追加
    return id_title_dict


@st.cache_data
def get_unique_id_dict(requirement_data: list[dict]) -> dict:
    """Get unique ID dictionary from requirement data.

    Args:
        requirement_data (list[dict]): Requirement data list

    Returns:
        dict: Unique ID dictionary
    """
    unique_id_dict = {
        requirement["unique_id"]: requirement["id"] for requirement in requirement_data
    }
    unique_id_dict["None"] = "None"  # 削除用の空要素を追加
    return unique_id_dict


@st.cache_data
def get_id_title_list(requirement_data: list[dict]) -> list[str]:
    """Get ID and title list from requirement data.

    Args:
        requirement_data (list[dict]): Requirement data list

    Returns:
        list[str]: ID and title list
    """
    id_title_list = [requirement["id"] for requirement in requirement_data]
    id_title_list.sort()
    id_title_list.insert(0, "None")  # 指定がない場合の初期値
    return id_title_list


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
        "relations": [],
    }


color_list = load_colors()

st.session_state.app_name = "Strategy and Tactics Tree Viewer"

st.set_page_config(
    layout="wide",
    page_title=st.session_state.app_name,
    initial_sidebar_state="collapsed",  # サイドバーを閉じた状態で表示
)

# Configファイルを読み込む
config_data, demo = load_config()
st.session_state.config_data = config_data
app_data = load_app_data()
st.session_state.app_data = app_data

# PlantUMLサーバを起動（キャッシュされるので再度起動されません）
if not ("www.plantuml.com" in config_data["plantuml"]):
    plantuml_process = start_plantuml_server()
# st.write("PlantUMLサーバが立ち上がっています（プロセスID：", plantuml_process.pid, "）")


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

# IDとタイトルをキー, ユニークIDを値とする辞書とその逆を作成
id_title_dict = get_id_title_dict(requirement_data)
unique_id_dict = get_unique_id_dict(requirement_data)

id_title_list = get_id_title_list(requirement_data)

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
                d for d in requirement_data if d["unique_id"] == selected_unique_id
            ][0]

if not selected_entity:
    selected_entity = get_default_entity()

# Requirement diagram表示とデータ編集のレイアウトを設定
diagram_column, edit_column = st.columns([4, 1])

graph_data, plantuml_code = draw_diagram_column(
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
)

with edit_column:
    st.write("## データ編集")
    # 直接データ操作はせず、コピーに対して操作する
    tmp_entity = copy.deepcopy(selected_entity)
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

    for i, relation in enumerate(tmp_entity["relations"]):
        relation["destination"] = id_title_dict[
            st.selectbox(
                "接続先",
                id_title_list,
                id_title_list.index(unique_id_dict[relation["destination"]]),
                key=f"destination{i}",
            )
        ]

    # 関係追加の操作があるため、1つは常に表示
    destination_unique_id = id_title_dict[
        st.selectbox("接続先", id_title_list, index=id_title_list.index("None"))
    ]  # 末尾に追加用の空要素を追加

    tmp_entity["relations"].append(
        {
            "destination": destination_unique_id,
        }
    )

    add_operate_buttons(
        tmp_entity, requirement_manager, file_path, id_title_dict, unique_id_dict
    )

# セッション状態にgraph_dataを追加
st.session_state.graph_data = graph_data

# テキストエリアで PlantUML コードが確認可能
st.text_area("PlantUML コード", value=plantuml_code, height=250)
