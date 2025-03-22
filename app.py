import streamlit as st
import subprocess
from src.requirement_graph import RequirementGraph
from src.convert_puml_code import ConvertPumlCode
import json
import os
import uuid
import networkx as nx
import atexit
import requests
import zlib
import copy

# Streamlit のレイアウトをワイドに設定
st.set_page_config(layout="wide")


# PlantUMLサーバをバックグラウンドプロセスとして起動し、キャッシュする
@st.cache_resource
def start_plantuml_server():
    """Launch PlantUML server as a background process."""
    # plantuml.jarは同一ディレクトリに配置していると仮定
    command = ["java", "-jar", "plantuml.jar", "-picoweb"]
    process = subprocess.Popen(command)
    # プロセス終了時にクリーンアップするため、atexitに登録
    atexit.register(lambda: process.terminate())
    return process


# PlantUMLサーバを起動（キャッシュされるので再度起動されません）
plantuml_process = start_plantuml_server()
# st.write("PlantUMLサーバが立ち上がっています（プロセスID：", plantuml_process.pid, "）")


# PlantUMLサーバ向けのエンコード関数
def encode_plantuml(text: str) -> str:
    """Encode text to PlantUML server format.

    Args:
        text (str): Text to encode

    Returns:
        str: Encoded text
    """
    # UTF-8にエンコードし、zlibでdeflate圧縮
    data = text.encode("utf-8")
    compressed = zlib.compress(data)
    # zlibヘッダー(最初の2バイト)とチェックサム(最後の4バイト)を除去
    compressed = compressed[2:-4]
    return encode64(compressed)


def encode64(data: bytes) -> str:
    """Encode bytes to PlantUML server format.

    Args:
        data (bytes): Data to encode

    Returns:
        str: Encoded text
    """
    # PlantUML用のカスタム64エンコードテーブル
    char_map = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
    res = []
    # 3バイトずつ処理し、24ビット整数にまとめる
    for i in range(0, len(data), 3):
        b = data[i : i + 3]
        # 3バイトに満たない場合は0でパディング
        if len(b) < 3:
            b = b + bytes(3 - len(b))
        n = (b[0] << 16) + (b[1] << 8) + b[2]
        # 6ビットごとに分割して、char_mapの文字に変換
        res.append(char_map[(n >> 18) & 0x3F])
        res.append(char_map[(n >> 12) & 0x3F])
        res.append(char_map[(n >> 6) & 0x3F])
        res.append(char_map[n & 0x3F])
    return "".join(res)


# PlantUMLコードからSVG画像を取得する関数
def get_diagram(plantuml_code: str) -> str:
    """Get SVG diagram from PlantUML code.

    Args:
        plantuml_code (str): PlantUML code

    Returns:
        str: SVG diagram as text
    """
    # PlantUMLサーバ用にエンコード
    encoded = encode_plantuml(plantuml_code)
    url = f"http://localhost:8080/svg/{encoded}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        st.error("PlantUMLサーバから図を取得できませんでした。")
        return ""


def extract_subgraph(graph: nx.DiGraph, target_node: str) -> nx.DiGraph:
    """Extract subgraph from graph with target node.

    Args:
        graph (nx.Digraph): Whole graph
        target_node (str): Target node to extract subgraph

    Returns:
        nx.DiGraph: Subgraph with target node
    """
    if target_node is None or target_node == "None":
        return graph

    reachable_upper_nodes = nx.descendants(graph, target_node)
    reachable_lower_nodes = nx.ancestors(graph, target_node)
    reachable_nodes = reachable_upper_nodes.union(reachable_lower_nodes)
    reachable_nodes.add(target_node)  # 自分自身も含める

    # これらのノードを含むサブグラフを作成
    subgraph = graph.subgraph(reachable_nodes).copy()

    return subgraph


st.title("Requirement Diagram Viewer")

# テキストでJSONファイルのパスを指定(デフォルトはdefault.json)
file_path = st.text_input("JSONファイルのパスを入力してください", "default.json")

# ファイルが存在する場合は読み込む
if os.path.exists(file_path):
    # JSONファイルを読み込む。文字コードに注意
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            requirement_data = json.load(f)
        except:
            st.error("JSONファイルの読み込みに失敗しました。")
            st.stop()
else:
    # 存在しない場合は空で始める
    requirement_data = []

# 読み込んだデータからIDとタイトルをキーとする辞書を作成
id_title_dict = {
    requirement["id"] + ": " + requirement["title"]: requirement["unique_id"]
    for requirement in requirement_data
}
id_title_dict["None"] = "None"
# 逆にユニークIDをキーとする辞書も作成
unique_id_dict = {
    requirement["unique_id"]: requirement["id"] + ": " + requirement["title"]
    for requirement in requirement_data
}
unique_id_dict["None"] = "None"

id_title_list = [
    requirement["id"] + ": " + requirement["title"] for requirement in requirement_data
]
id_title_list.insert(0, "None")

# URL のクエリパラメータから、選択されたエンティティを取得
scale = st.query_params.get("scale", [None])
if scale == [None]:
    scale = 1.0
else:
    scale = float(scale)

# グラフデータをPlantUMLコードに変換
config = {"detail": True, "debug": False, "width": 800, "left_to_right": False}
converter = ConvertPumlCode(config)

# URL のクエリパラメータから、選択されたエンティティを取得
selected_unique_id = st.query_params.get("selected", [None])

# パラメタがない場合はデフォルトのエンティティを選択してリロード
selected_entity = {}
if selected_unique_id == [None]:
    default_params = {"selected": "default"}
    st.query_params.setdefault("selected", "default")
    st.rerun()
else:
    if selected_unique_id == "default":
        selected_entity = None
    else:
        if selected_unique_id not in unique_id_dict:
            selected_entity = None
        else:
            selected_entity = [
                d for d in requirement_data if d["unique_id"] == selected_unique_id
            ][0]

if not selected_entity:
    selected_entity = {
        "type": "functionalRequirement",
        "id": "",
        "title": "",
        "text": "",
        "unique_id": uuid.uuid4(),
        "relations": [],
    }


# 2つのカラムに表示を分割
col1, col2 = st.columns([4, 1])

target = None
with col1:
    col11, col12, col13 = st.columns([3, 1, 1])
    with col11:
        st.write("## Requirement Diagram")
        st.write("クリックするとエンティティが選択されます")
    with col12:
        target = st.query_params.get("target", None)
        if target != None and target != "None":
            target = id_title_dict[
                st.selectbox(
                    "フィルタ",
                    id_title_list,
                    index=id_title_list.index(unique_id_dict[target]),
                )
            ]
        else:
            target = id_title_dict[
                st.selectbox(
                    "フィルタ",
                    id_title_list,
                    index=id_title_list.index(unique_id_dict["None"]),
                )
            ]

        # 読み込んだデータをグラフデータに変換
        graph_data = RequirementGraph(requirement_data)
        # グラフをフィルタリング
        graph_data.subgraph = extract_subgraph(graph_data.graph, target)
    with col13:
        # 出力svgの拡大縮小倍率を設定
        scale = st.slider(
            "スケール", min_value=0.1, max_value=3.0, value=scale, step=0.1
        )
        # ローカルで PlantUML コードから SVG を生成
        plantuml_code = converter.convert_to_puml(
            graph_data.subgraph, title=None, target=target, scale=scale
        )
        svg_output = get_diagram(plantuml_code)
        svg_output = svg_output.replace(
            "<defs/>", "<defs/><style>a {text-decoration: none !important;}</style>"
        )

    # svg出力のデバッグ
    with open("debug.svg", "w") as out:
        out.writelines(svg_output)
        # SVG をそのまま表示
        st.markdown(
            f"""
            <div style="width:100%; height:800px; overflow:auto; border:0px solid black;">
                {svg_output}
            </div>
            """,
            unsafe_allow_html=True,
        )

with col2:
    st.write("## データ操作")
    # 直接データ操作はせず、コピーに対して操作する
    tmp_entity = copy.deepcopy(selected_entity)

    # エンティティタイプを定義
    entity_types = [
        "functionalRequirement",
        "performanceRequirement",
        "designConstraint",
        "interfaceRequirement",
        "physicalRequirement",
        "block",
        "element",
    ]
    tmp_entity["type"] = st.selectbox(
        "エンティティタイプ",
        entity_types,
        index := entity_types.index(tmp_entity["type"]),
    )
    tmp_entity["id"] = st.text_input("ID", tmp_entity["id"])
    tmp_entity["title"] = st.text_input("タイトル", tmp_entity["title"])
    tmp_entity["text"] = st.text_area("説明", tmp_entity["text"])

    # テキストエリアでエンティティの詳細情報を入力
    # 関係は複数ありえるため、繰り返し表示させる
    # また、関係の追加を行うケースがあるため、最初の項目は空にしておき2つめ以後は設定されているデータを表示する
    relation_types = [
        "None",
        "deriveReqt",
        "satisfy",
        "refine",
        "containment",
        "problem",
    ]

    # 関係追加の操作があるため、1つは常に表示
    col21, col22 = st.columns(2)
    with col21:
        relation_type = st.selectbox("関係タイプ", relation_types)
        for i, relation in enumerate(tmp_entity["relations"]):
            relation["type"] = st.selectbox(
                "関係タイプ",
                relation_types,
                relation_types.index(relation["type"]),
                key=f"relation_type{i}",
            )
    with col22:
        destination_unique_id = id_title_dict[
            st.selectbox("接続先", id_title_dict.keys(), index=len(id_title_dict) - 1)
        ]  # 末尾に追加用の空要素を追加
        for i, relation in enumerate(tmp_entity["relations"]):
            relation["destination"] = id_title_dict[
                st.selectbox(
                    "接続先",
                    id_title_dict.keys(),
                    list(id_title_dict.keys()).index(
                        unique_id_dict[relation["destination"]]
                    ),
                    key=f"destination{i}",
                )
            ]

    space_col, col31, col32, col33 = st.columns([3, 1, 1, 1])
    with col31:
        # 追加ボタンを表示
        if st.button("追加"):
            if (tmp_entity["id"] + ": " + tmp_entity["title"]) in id_title_dict:
                st.error("IDとタイトルが既存のエンティティと重複しています。")
            else:
                # ユニークID振り直し
                tmp_entity["unique_id"] = f"{uuid.uuid4()}".replace("-", "")
                # tmp_entityでdestinationがNoneのものを削除
                tmp_entity["relations"] = [
                    relation
                    for relation in tmp_entity["relations"]
                    if relation["destination"] != "None"
                ]
                if destination_unique_id != "None":
                    tmp_entity["relations"].append(
                        {"type": relation_type, "destination": destination_unique_id}
                    )
                requirement_data.append(tmp_entity)
                with open("default.json", "w", encoding="utf-8") as f:
                    json.dump(requirement_data, f, ensure_ascii=False, indent=4)
                st.write("エンティティを追加しました。")
                st.rerun()
    with col32:
        # 更新ボタンを表示
        if st.button("更新"):
            if not (tmp_entity["unique_id"]) in unique_id_dict:
                st.error("更新すべきエンティティがありません。")
            else:
                # 一度削除してから追加
                requirement_data.remove(
                    [
                        d
                        for d in requirement_data
                        if d["unique_id"] == tmp_entity["unique_id"]
                    ][0]
                )
                # tmp_entityでdestinationがNoneのものを削除
                tmp_entity["relations"] = [
                    relation
                    for relation in tmp_entity["relations"]
                    if relation["destination"] != "None"
                ]
                if destination_unique_id != "None":
                    tmp_entity["relations"].append(
                        {"type": relation_type, "destination": destination_unique_id}
                    )
                requirement_data.append(tmp_entity)
                with open("default.json", "w", encoding="utf-8") as f:
                    json.dump(requirement_data, f, ensure_ascii=False, indent=4)
                st.write("エンティティを更新しました。")
                st.rerun()
    with col33:
        # 削除ボタンを表示
        if st.button("削除"):
            if not (tmp_entity["id"] + ": " + tmp_entity["title"]) in id_title_dict:
                st.error("削除すべきエンティティがありません。")
            else:
                # 削除
                # TODO: 関連エンティティも削除する
                requirement_data.remove(
                    [
                        d
                        for d in requirement_data
                        if d["unique_id"] == tmp_entity["unique_id"]
                    ][0]
                )
                with open("default.json", "w", encoding="utf-8") as f:
                    json.dump(requirement_data, f, ensure_ascii=False, indent=4)
                st.write("エンティティを削除しました。")
                st.rerun()


# テキストエリアで PlantUML コードのが可能
st.text_area("PlantUML コード", value=plantuml_code, height=250)
