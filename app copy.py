import streamlit as st
import subprocess
from urllib.parse import urlencode

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

st.title("PlantUML の図とエンティティ情報の編集")

st.write("""
PlantUML のコード内で各要求（エンティティ）にハイパーリンクを設定しています。
例: `[[?selected=req1]]` とすることで、エンティティ req1 がクリックされた際に
URL パラメータとして `selected=req1` が付与され、Streamlit 側で検出できます。
""")

# 初期の PlantUML コード（クリック可能なハイパーリンク付き）
default_code = """@startuml
' PlantUML Requirement Diagram with clickable entities
agent "System Requirement: システムは安全に動作すること" as req1 [[?selected=req1]]
agent "User Requirement: ユーザは容易に操作できること" as req2 [[?selected=req2]]
agent "Derived Requirement: 操作性と安全性の両立を実現すること" as req3 [[?selected=req3]]

req1 --> req3 : satisfies
req2 --> req3 : verifies
@enduml
"""

# テキストエリアで PlantUML コードの編集が可能
plantuml_code = st.text_area("PlantUML コード", value=default_code, height=250)

# URL のクエリパラメータから、選択されたエンティティを取得
# query_params = st.query_params()
selected_entity = st.query_params.get("selected", [None])
st.write(f"{selected_entity}")

# ローカルで PlantUML コードから SVG を生成
svg_output = plantuml_svg(plantuml_code)

# 強制遷移させるようリンクを修正
svg_output = svg_output.replace('target="_top"', 'target="_parent"')

with open("debug.svg", "w") as svg:
    svg.writelines(svg_output)


# SVG をそのまま HTML コンポーネントで表示
st.components.v1.html(svg_output, height=600, scrolling=True)
selected_entity = st.query_params.get("selected", [None])
st.write(f"{selected_entity}")
selected_entity = st.query_params.set("selected", ["hoge"])
selected_entity = st.query_params.get("selected", [None])
st.write(f"{selected_entity}")

# 選択されたエンティティの情報を表示・編集
if selected_entity:
    st.info(f"{selected_entity}が選択されました")
    st.subheader(f"選択されたエンティティ: {selected_entity}")
    # サンプル用のダミーデータ（実際は session_state 等で管理することを検討）
    entity_info = {
        "req1": "System Requirement: システムは安全に動作すること",
        "req2": "User Requirement: ユーザは容易に操作できること",
        "req3": "Derived Requirement: 操作性と安全性の両立を実現すること"
    }
    # current_info = entity_info.get(selected_entity, "情報なし")
    # new_info = st.text_area("エンティティ情報", value=current_info)
    # if st.button("更新"):
        # 更新処理（ここではダミー）
        # st.success(f"{selected_entity} の情報が更新されました。（この例では更新処理はダミーです）")
