import streamlit as st
from src.utility import get_diagram
from src.requirement_graph import RequirementGraph
from src.convert_puml_code import ConvertPumlCode
import copy
import os
import datetime


def draw_diagram_column(
    page_title,
    column,
    unique_id_dict,
    id_title_dict,
    id_title_list,
    config_data,
    requirements,
    upstream_distance,
    downstream_distance,
    scale,
    *,
    graph_data=None,
    landscape=False,
):

    target = None
    with column:
        (
            title_column,
            filter_column,
            upstream_distance_column,
            downstream_distance_column,
            scale_column,
            landscape_column,
        ) = st.columns([2, 2, 1, 1, 1, 1])
        with title_column:
            st.write(f"## {page_title}")
            st.write("クリックするとエンティティが選択されます")
        with filter_column:
            target = st.query_params.get("target", None)
            if target == None or target == "None" or target not in unique_id_dict:
                target = "None"
            target = id_title_dict[
                st.selectbox(
                    "フィルタ",
                    id_title_list,
                    index=id_title_list.index(unique_id_dict[target]),
                )
            ]

            # 読み込んだデータをグラフデータに変換
            # グラフ変換時に描画を意識した前処理を行うため、元データを維持するためコピーを渡す
            if graph_data is None:
                graph_data = RequirementGraph(copy.deepcopy(requirements), page_title)
        with upstream_distance_column:
            upstream_distance = st.slider(
                "上流フィルタ距離",
                min_value=0,
                max_value=config_data["upstream_filter_max"],
                value=int(upstream_distance),
                step=1,
            )
        with downstream_distance_column:
            downstream_distance = st.slider(
                "下流フィルタ距離",
                min_value=0,
                max_value=config_data["downstream_filter_max"],
                value=int(downstream_distance),
                step=1,
            )
        with landscape_column:
            # 横向きのチェックボックス
            landscape_mod = st.checkbox(
                "横向き", value=landscape, key="landscape_checkbox"
            )
        # グラフをフィルタリング
        graph_data.extract_subgraph(
            target,
            upstream_distance=upstream_distance,
            downstream_distance=downstream_distance,
        )
        with scale_column:
            # 出力svgの拡大縮小倍率を設定
            scale = st.slider(
                "スケール", min_value=0.1, max_value=3.0, value=scale, step=0.1
            )
            # ローカルで PlantUML コードから SVG を生成
            parameters_dict = {}
            parameters_dict["scale"] = scale
            parameters_dict["target"] = target
            parameters_dict["upstream_distance"] = upstream_distance
            parameters_dict["downstream_distance"] = downstream_distance
            parameters_dict["landscape"] = landscape_mod

            # グラフデータをPlantUMLコードに変換
            config = {
                "detail": True,
                "debug": False,
                "width": 1200,
                "left_to_right": False,
            }
            converter = ConvertPumlCode(config)

            plantuml_code = converter.convert_to_puml(
                page_title,
                graph_data.subgraph,
                title=None,
                parameters_dict=parameters_dict,
            )
            svg_output = get_diagram(plantuml_code, config_data["plantuml"])
            svg_output = svg_output.replace(
                "<defs/>", "<defs/><style>a {text-decoration: none !important;}</style>"
            )

        # svg出力のデバッグ
        with open("debug.svg", "w") as out:
            out.writelines(svg_output)
        # SVG をそのまま表示
        st.markdown(
            f"""
            <div style="width:100%; height:{config_data['viewer_height']}px; overflow:auto; border:0px solid black;">
                {svg_output}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # png画像を生成(出力はファイル更新時)
        if st.session_state["save_png"]:
            postfix_file = st.session_state.app_data[st.session_state.app_name][
                "postfix"
            ]
            os.makedirs("back", exist_ok=True)
            png_output = get_diagram(
                plantuml_code, config_data["plantuml"], png_out=True
            )
            filename = (
                datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                + f"_{postfix_file}.png"
            )
            with open(os.path.join("back", filename), "wb") as out:
                out.write(png_output)
            st.session_state["save_png"] = False

    return plantuml_code
