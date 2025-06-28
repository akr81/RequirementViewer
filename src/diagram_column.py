import streamlit as st
from src.utility import (
    get_diagram,
    save_config,
    get_default_data_structure,
    list_hjson_files,
)
from src.requirement_graph import RequirementGraph
from src.convert_puml_code import ConvertPumlCode
import copy
import os
import datetime
import hjson
import shutil


def draw_diagram_column(
    app_name,  # Renamed page_title to app_name for clarity
    column,
    unique_id_dict,
    id_title_dict,
    id_title_list,
    config_data,  # This is st.session_state.config_data
    requirements,
    upstream_distance,
    downstream_distance,
    scale,
    *,
    graph_data=None,
    landscape=False,
    title=False,
    detail=False,
):
    target = None
    DATA_DIR = "data"  # Define data directory
    os.makedirs(DATA_DIR, exist_ok=True)  # Ensure data directory exists

    with column:
        # Original diagram display logic starts here
        (
            title_column,
            filter_column,
            upstream_distance_column,
            downstream_distance_column,
            scale_column,
            landscape_column,
        ) = st.columns([2, 2, 1, 1, 1, 1])
        with title_column:
            st.write(f"### {app_name}")
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
                    key=f"{app_name}_filter_selectbox",
                )
            ]

            if graph_data is None:
                graph_data = RequirementGraph(copy.deepcopy(requirements), app_name)
        with upstream_distance_column:
            upstream_distance = st.slider(
                "A方向フィルタ距離",
                min_value=0,
                max_value=config_data["upstream_filter_max"],
                value=int(upstream_distance),
                step=1,
                key=f"{app_name}_upstream_slider",
            )
        with downstream_distance_column:
            downstream_distance = st.slider(
                "B方向フィルタ距離",
                min_value=0,
                max_value=config_data["downstream_filter_max"],
                value=int(downstream_distance),
                step=1,
                key=f"{app_name}_downstream_slider",
            )
        with landscape_column:
            landscape_mod = st.checkbox(
                "横向き", value=landscape, key=f"{app_name}_landscape_checkbox"
            )
            title_mod = st.checkbox(
                "タイトル", value=title, key=f"{app_name}_title_checkbox"
            )
            detail_mod = st.checkbox(
                "詳細", value=detail, key=f"{app_name}_detail_checkbox"
            )
        graph_data.extract_subgraph(
            target,
            upstream_distance=upstream_distance,
            downstream_distance=downstream_distance,
            detail=detail_mod,
        )
        with scale_column:
            scale = st.slider(
                "スケール",
                min_value=0.1,
                max_value=3.0,
                value=scale,
                step=0.1,
                key=f"{app_name}_scale_slider",
            )
            parameters_dict = {}
            parameters_dict["scale"] = scale
            parameters_dict["target"] = target
            parameters_dict["upstream_distance"] = upstream_distance
            parameters_dict["downstream_distance"] = downstream_distance
            parameters_dict["landscape"] = landscape_mod
            parameters_dict["title"] = title_mod
            parameters_dict["detail"] = detail_mod

            config = {
                "detail": True,
                "debug": False,
                "width": 1200,
                "left_to_right": False,
            }
            converter = ConvertPumlCode(config)

            try:
                plantuml_code = converter.convert_to_puml(
                    app_name,
                    graph_data.subgraph,
                    title=None,
                    parameters_dict=parameters_dict,
                    diagram_title=requirements.get("title", ""),
                )
            except:
                st.error("PlantUMLコードの変換に失敗しました。")
                plantuml_code = ""
            svg_output = get_diagram(plantuml_code, config_data["plantuml"])
            svg_output = svg_output.replace(
                "<defs/>", "<defs/><style>a {text-decoration: none !important;}</style>"
            )

        with open("debug.svg", "w") as out:
            out.writelines(svg_output)
        st.markdown(
            f"""
            <div style="width:100%; height:{config_data['viewer_height']}px; overflow:auto; border:0px solid black;">
                {svg_output}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Section for File Operations (Moved below diagram)
        st.markdown("---")  # Separator
        st.subheader("ファイル操作")

        file_op_cols = st.columns(2)
        with file_op_cols[0]:
            st.write("現在のファイル:", st.session_state.get("file_path", "未設定"))

        # New File Section
        with st.expander("新しいファイルを作成"):
            new_file_name_key = f"{app_name}_new_file_name"
            postfix = st.session_state.app_data[app_name].get("postfix", "data")
            if new_file_name_key not in st.session_state:
                current_time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                st.session_state[new_file_name_key] = (
                    f"{current_time_str}_{postfix}.hjson"
                )

            new_file_name = st.text_input(
                "新しいファイル名 (.hjson):", key=new_file_name_key
            )
            if st.button("作成して開く", key=f"{app_name}_create_new_file"):
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

                            data_file_key = st.session_state.app_data[app_name]["data"]
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
                    key=f"{app_name}_select_open_file",
                )

                if st.button(
                    "選択したファイルを開く", key=f"{app_name}_open_selected_file"
                ):
                    if selected_file_to_open:
                        try:
                            data_file_key = st.session_state.app_data[app_name]["data"]
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
