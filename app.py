import streamlit as st
import subprocess
from urllib.parse import urlencode
from src.requirement_graph import RequirementGraph
from src.convert_puml_code import ConvertPumlCode
import json
import os
import uuid
import networkx as nx

# Streamlit のレイアウトをワイドに設定
st.set_page_config(layout="wide")

# キャッシュを利用して、同じコードの場合は再実行を防ぐ
@st.cache_data
def plantuml_svg(plantuml_code: str) -> str:
    """
    ローカルの PlantUML jar を利用して、PlantUML コードから SVG を生成する関数
    ※PlantUML jar（plantuml.jar）はこのコードと同じディレクトリに配置すること。
    """
    try:
        process = subprocess.run(
            ["java", "-jar", "plantuml.jar", "-pipe", "-tsvg"],
            input=plantuml_code.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return process.stdout.decode("utf-8")
    except subprocess.CalledProcessError as e:
        st.error("PlantUML の図生成中にエラーが発生しました:")
        st.error(e.stderr.decode("utf-8"))
        return ""

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
    #存在しない場合は空で始める
    requirement_data = []

print(requirement_data)

# 読み込んだデータからIDとタイトルのリストを作成
id_title_list = [requirement["id"] + ": " + requirement["title"] for requirement in requirement_data]
id_title_list.insert(0, "None")

# 読み込んだデータをグラフデータに変換
graph_data = RequirementGraph(requirement_data)
print(graph_data)
# graph_data = {
#     "nodes": [],
#     "edges": []
# }

# グラフデータをPlantUMLコードに変換
config = {
    "detail": True,
    "debug": True,
    "width": 800,
    "left_to_right": False
}
converter = ConvertPumlCode(config)
puml_code = converter.convert_to_puml(graph_data.graph, title=None, target=None)
print(puml_code)
st.write(puml_code)


st.write("""
PlantUML のコード内で各要求（エンティティ）にハイパーリンクを設定しています。
例: `[[?selected=req1]]` とすることで、エンティティ req1 がクリックされた際に
URL パラメータとして `selected=req1` が付与され、Streamlit 側で検出できます。
""")

# 初期の PlantUML コード（クリック可能なハイパーリンク付き）
# default_code = """@startuml
# ' PlantUML Requirement Diagram with clickable entities
# '!pragma svginteractive true
# skinparam svgLinkTarget _href
# skinparam pathHoverColor green
# agent "System Requirement: システムは安全に動作すること" as req1 [[?selected=req1]]
# agent "User Requirement: ユーザは容易に操作できること" as req2 [[?selected=req2]]
# agent "Derived Requirement: 操作性と安全性の両立を実現すること" as req3 [[?selected=req3]]

# req1 --> req3 : satisfies
# req2 --> req3 : verifies
# @enduml
# """

# テキストエリアで PlantUML コードの編集が可能
plantuml_code = st.text_area("PlantUML コード", value=puml_code, height=250)

# URL のクエリパラメータから、選択されたエンティティを取得
# query_params = st.query_params()
selected_entity = st.query_params.get("selected", [None])

# パラメタがない場合はデフォルトのエンティティを選択してリロード
print(selected_entity)
if selected_entity == [None]:
    print("Set default params")
    default_params = {"selected": "default"}
    st.query_params.setdefault("selected", "default")
    st.rerun()

# ローカルで PlantUML コードから SVG を生成
svg_output = plantuml_svg(plantuml_code)

# svg出力のデバッグ
with open("debug.svg", "w") as out:
    out.writelines(svg_output)

# 2つのカラムに表示を分割
col1, col2 = st.columns([4, 1])

with col1:
    st.write("## PlantUML 図")
    st.write("クリックするとエンティティが選択されます")
    st.write(selected_entity)
    # SVG をそのまま HTML コンポーネントで表示
    st.markdown(svg_output, unsafe_allow_html=True)

with col2:
    st.write("## データ操作")
    # エンティティタイプを定義
    entity_types = ["functionalRequirement", "performanceRequirement", "designConstraint", "interfaceRequirement", "physicalRequirement"]
    entity_type = st.selectbox("エンティティタイプ", entity_types)
    entity_id = st.text_input("ID", "")
    entity_title = st.text_input("タイトル", "")
    entity_text = st.text_area("説明", "")
    # ユニークIDをGUIDで生成
    entity_unique_id = uuid.uuid4()

    # テキストエリアでエンティティの詳細情報を入力
    # 関係は複数ありえるため、繰り返し表示させる
    # また、関係の追加を行うケースがあるため、最初の項目は空にしておき2つめ以後は設定されているデータを表示する
    relation_types = ["None", "deriveReqt", "satisfy", "refine", "containment", "problem"]

    col21, col22 = st.columns(2)
    with col21:
        relation_type = st.selectbox("関係タイプ", relation_types)
    with col22:
        destination_unique_id = st.selectbox("接続先", id_title_list)

    # 追加ボタンを表示
    if st.button("追加"):
        # 関係を追加
        # 1. 関係を追加
        # 2. 画面をリロード
        st.write("追加ボタンが押されました")
        st.write(relation_type)


# 選択されたエンティティの情報を表示・編集
# if selected_entity:
#     st.subheader(f"選択されたエンティティ: {selected_entity}")
#     # サンプル用のダミーデータ（実際は session_state 等で管理することを検討）
#     entity_info = {
#         "req1": "System Requirement: システムは安全に動作すること",
#         "req2": "User Requirement: ユーザは容易に操作できること",
#         "req3": "Derived Requirement: 操作性と安全性の両立を実現すること"
#     }
#     current_info = entity_info.get(selected_entity, "情報なし")
#     new_info = st.text_area("エンティティ情報", value=current_info)
#     if st.button("更新"):
#         # 更新処理（ここではダミー）
#         st.success(f"{selected_entity} の情報が更新されました。（この例では更新処理はダミーです）")
