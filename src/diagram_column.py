import streamlit as st
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy
import os
import datetime
import hjson
import shutil

from src.utility import (
    get_diagram,
    save_config,
    get_default_data_structure,
    list_hjson_files,
)
from src.requirement_graph import RequirementGraph
from src.convert_puml_code import ConvertPumlCode

@dataclass
class DiagramContext:
    app_name: str
    unique_id_dict: Dict[str, str]
    id_title_dict: Dict[str, str]
    id_title_list: List[str]
    config_data: Dict[str, Any]
    requirements: Dict[str, Any]

@dataclass
class DiagramOptions:
    upstream_distance: int
    downstream_distance: int
    scale: float
    graph_data: Any = None
    landscape: bool = False
    title: bool = False
    detail: bool = False
    link_mode: bool = False
    previous_selected: str = "None"

# ConvertPumlCode の共通設定（不変のためモジュールレベルで定義）
_CONVERTER_CONFIG = {
    "detail": True,
    "debug": False,
    "width": 1200,
    "left_to_right": False,
}
_converter = ConvertPumlCode(_CONVERTER_CONFIG)


def _render_controls(context: DiagramContext, options: DiagramOptions) -> Optional[str]:
    """Render control widgets and update options."""
    (
        title_column,
        filter_column,
        upstream_distance_column,
        downstream_distance_column,
        scale_column,
        landscape_column,
    ) = st.columns([2, 2, 1, 1, 1, 1])

    with title_column:
        st.write(f"### {context.app_name}")
        st.write("クリックするとエンティティが選択されます")

    target = None
    with filter_column:
        target = st.query_params.get("target", None)
        if target == None or target == "None" or target not in context.unique_id_dict:
            target = "None"
        target = context.id_title_dict[
            st.selectbox(
                "フィルタ",
                context.id_title_list,
                index=context.id_title_list.index(context.unique_id_dict[target]),
                key=f"{context.app_name}_filter_selectbox",
            )
        ]

        if options.graph_data is None:
            options.graph_data = RequirementGraph(
                copy.deepcopy(context.requirements), context.app_name
            )

    with upstream_distance_column:
        options.upstream_distance = st.slider(
            "A方向フィルタ距離",
            min_value=-1,
            max_value=context.config_data["upstream_filter_max"],
            value=int(options.upstream_distance),
            step=1,
            key=f"{context.app_name}_upstream_slider",
        )

    with downstream_distance_column:
        options.downstream_distance = st.slider(
            "B方向フィルタ距離",
            min_value=-1,
            max_value=context.config_data["downstream_filter_max"],
            value=int(options.downstream_distance),
            step=1,
            key=f"{context.app_name}_downstream_slider",
        )

    with landscape_column:
        options.landscape = st.checkbox(
            "横向き",
            value=options.landscape,
            key=f"{context.app_name}_landscape_checkbox",
        )
        options.title = st.checkbox(
            "タイトル", value=options.title, key=f"{context.app_name}_title_checkbox"
        )
        options.detail = st.checkbox(
            "詳細", value=options.detail, key=f"{context.app_name}_detail_checkbox"
        )
        options.link_mode = st.toggle(
            "🖱️ 接続モード",
            value=options.link_mode,
            key=f"{context.app_name}_connect_mode",
        )

    with scale_column:
        options.scale = st.slider(
            "スケール",
            min_value=0.1,
            max_value=3.0,
            value=options.scale,
            step=0.1,
            key=f"{context.app_name}_scale_slider",
        )
    
    return target


def _render_diagram(
    context: DiagramContext, options: DiagramOptions, target: Optional[str]
) -> str:
    """Render the diagram and return plantuml code."""
    options.graph_data.extract_subgraph(
        target,
        upstream_distance=options.upstream_distance,
        downstream_distance=options.downstream_distance,
        detail=options.detail,
    )

    parameters_dict = {}
    parameters_dict["scale"] = options.scale
    parameters_dict["target"] = target
    parameters_dict["upstream_distance"] = options.upstream_distance
    parameters_dict["downstream_distance"] = options.downstream_distance
    parameters_dict["landscape"] = options.landscape
    parameters_dict["title"] = options.title
    parameters_dict["detail"] = options.detail
    parameters_dict["link_mode"] = options.link_mode
    parameters_dict["previous_selected"] = options.previous_selected

    plantuml_code = ""
    try:
        plantuml_code = _converter.convert_to_puml(
            context.app_name,
            options.graph_data.subgraph,
            title=None,
            parameters_dict=parameters_dict,
            diagram_title=context.requirements.get("title", ""),
        )
    except:
        st.error("PlantUMLコードの変換に失敗しました。")
        plantuml_code = ""

    svg_output = get_diagram(plantuml_code, context.config_data["plantuml"])
    svg_output = svg_output.replace(
        "<defs/>", "<defs/><style>a {text-decoration: none !important;}</style>"
    )

    # デバッグ用SVG出力（内容が変わった場合のみ書き出し）
    try:
        debug_svg_path = "debug.svg"
        should_write = True
        if os.path.exists(debug_svg_path):
            with open(debug_svg_path, "r", encoding="utf-8") as f:
                if f.read() == svg_output:
                    should_write = False
        if should_write:
            with open(debug_svg_path, "w", encoding="utf-8") as out:
                out.writelines(svg_output)
    except Exception:
        pass

    st.markdown(
        f"""
        <div style="width:100%; height:{context.config_data['viewer_height']}px; overflow:auto; border:0px solid black;">
            {svg_output}
        </div>
        """,
        unsafe_allow_html=True,
    )

    return plantuml_code


def _render_file_operations(
    context: DiagramContext, options: DiagramOptions, plantuml_code: str
):
    """Render file operations section."""
    DATA_DIR = "data"  # Define data directory
    os.makedirs(DATA_DIR, exist_ok=True)  # Ensure data directory exists

    st.markdown("---")  # Separator
    st.subheader("ファイル操作")

    file_op_cols = st.columns(2)
    with file_op_cols[0]:
        st.write("現在のファイル:", st.session_state.get("file_path", "未設定"))

    # New File Section
    with st.expander("新しいファイルを作成"):
        new_file_name_key = f"{context.app_name}_new_file_name"
        postfix = st.session_state.app_data[context.app_name].get("postfix", "data")
        if new_file_name_key not in st.session_state:
            current_time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            st.session_state[new_file_name_key] = (
                f"{current_time_str}_{postfix}.hjson"
            )

        new_file_name = st.text_input(
            "新しいファイル名 (.hjson):", key=new_file_name_key
        )
        if st.button("作成して開く", key=f"{context.app_name}_create_new_file"):
            if new_file_name and new_file_name.endswith(".hjson"):
                new_file_path = os.path.join(DATA_DIR, new_file_name)
                if os.path.exists(new_file_path):
                    st.error(f"ファイル '{new_file_path}' は既に存在します。")
                else:
                    try:
                        default_content = get_default_data_structure()
                        with open(new_file_path, "w", encoding="utf-8") as f:
                            hjson.dump(
                                default_content, f, ensure_ascii=False, indent=4
                            )
                        if postfix == "ec":
                            # For Evaporating Cloud Viewer, copy default template
                            shutil.copyfile("template/ec.hjson", new_file_path)

                        data_file_key = st.session_state.app_data[context.app_name][
                            "data"
                        ]
                        st.session_state.config_data[data_file_key] = new_file_path
                        save_config(st.session_state.config_data)
                        st.session_state.file_path = new_file_path
                        st.success(
                            f"新しいファイル '{new_file_path}' を作成し、設定を更新しました。"
                        )
                        st.query_params.clear()
                        st.query_params.selected = "default"
                        st.query_params.detail = "True"
                        st.rerun()
                    except Exception as e:
                        st.error(
                            f"ファイルの作成または設定の更新に失敗しました: {e}"
                        )
            else:
                st.error("有効なファイル名（.hjsonで終わる）を入力してください。")

    # Open File Section
    with st.expander("既存のファイルを開く"):
        available_files_in_data_dir = list_hjson_files(DATA_DIR)

        file_options_map = {
            os.path.join(DATA_DIR, f): f for f in available_files_in_data_dir
        }

        current_file_path = st.session_state.get("file_path")

        if current_file_path and current_file_path not in file_options_map:
            if os.path.isfile(current_file_path) and current_file_path.endswith(
                ".hjson"
            ):
                file_options_map[current_file_path] = current_file_path

        if not file_options_map:
            st.info(
                f"'{DATA_DIR}' ディレクトリまたは現在のパスに利用可能な .hjson ファイルがありません。"
            )
        else:
            options_paths = sorted(list(file_options_map.keys()))

            default_index = 0
            if current_file_path in options_paths:
                default_index = options_paths.index(current_file_path)

            selected_file_to_open = st.selectbox(
                "開くファイルを選択:",
                options=options_paths,
                format_func=lambda path: file_options_map[path],
                index=default_index,
                key=f"{context.app_name}_select_open_file",
            )

            if st.button(
                "選択したファイルを開く", key=f"{context.app_name}_open_selected_file"
            ):
                if selected_file_to_open:
                    try:
                        data_file_key = st.session_state.app_data[context.app_name][
                            "data"
                        ]
                        st.session_state.config_data[data_file_key] = (
                            selected_file_to_open
                        )
                        save_config(st.session_state.config_data)
                        st.session_state.file_path = selected_file_to_open
                        st.success(
                            f"ファイル '{selected_file_to_open}' を開くように設定を更新しました。"
                        )
                        st.query_params.clear()
                        st.query_params.selected = "default"
                        st.query_params.detail = "True"
                        st.rerun()
                    except Exception as e:
                        st.error(f"ファイル設定の更新に失敗しました: {e}")
                else:
                    st.warning("開くファイルを選択してください。")

    st.markdown("---")  # Separator

    if st.session_state.get("save_png", False):
        postfix_file = st.session_state.app_data[context.app_name]["postfix"]
        os.makedirs("back", exist_ok=True)
        png_output = get_diagram(
            plantuml_code, context.config_data["plantuml"], png_out=True
        )
        filename = (
            datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            + f"_{postfix_file}.png"
        )
        with open(os.path.join("back", filename), "wb") as out:
            out.write(png_output)
        st.session_state["save_png"] = False


def draw_diagram_column(
    column,
    context: DiagramContext,
    options: DiagramOptions,
):
    with column:
        target = _render_controls(context, options)
        plantuml_code = _render_diagram(context, options, target)
        _render_file_operations(context, options, plantuml_code)

    return plantuml_code
