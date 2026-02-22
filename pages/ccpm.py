import streamlit as st
from src.operate_buttons import add_operate_buttons
from src.page_setup import setup_page_layout_and_data
from src.utility import (
    get_backup_files_for_current_data,
    copy_file,
    calculate_text_area_height,
    unescape_newline,
    update_source_data,
)
from src.ccpm_engine import (
    get_in_out_edge_list,
    calculate_critical_path,
    calculate_critical_chain,
    make_gantt_puml,
    calculate_fever_data,
    calculate_priority_table,
)
from src.plantuml_service import get_diagram
import uuid
import copy

try:
    import plotly.graph_objects as go
except ImportError:
    go = None


# PFD と同じタイプリスト
ccpm_type_list = ["process", "deliverable", "note", "cloud"]

# エッジ編集パラメータ (PFD と同じ構造)
edge_params = {
    "to_selected": {
        "condition": "destination",
        "selectbox_label": "接続元",
        "selectbox_index": "source",
        "selectbox_key": "ccpm_predecessors",
    },
    "from_selected": {
        "condition": "source",
        "selectbox_label": "接続先",
        "selectbox_index": "destination",
        "selectbox_key": "ccpm_successors",
    },
}


def render_edge_connection(
    edge: dict, index: int, visibility: str, params: dict
) -> str:
    """PFD と同様のエッジ接続 UI。"""
    if edge[params["condition"]] == params["selected_unique_id"]:
        edge.setdefault("comment", "")
        with params["connection_column"]:
            current_id = edge[params["selectbox_index"]]
            current_label = params["unique_id_dict"].get(current_id, "None")
            edge[params["selectbox_index"]] = params["id_title_dict"][
                st.selectbox(
                    params["selectbox_label"],
                    params["id_title_list"],
                    index=params["id_title_list"].index(current_label),
                    key=f"{params['selectbox_key']}{index}",
                    label_visibility=visibility,
                )
            ]
        with params["description_column"]:
            edge["comment"] = st.text_input(
                "説明",
                unescape_newline(edge["comment"]),
                key=f"comment_{params['selectbox_key']}_{params['selected_unique_id']}_{index}",
                label_visibility=visibility,
            )
        return "collapsed"
    return visibility


def render_edge_connection_new(edge: dict, _: int, visibility: str, params: dict):
    """新規エッジ接続 UI。"""
    expected_index = -1
    if "None" in params["id_title_list"]:
        expected_index = params["id_title_list"].index("None")
    with params["connection_column"]:
        connection_key = f"{params['selectbox_key']}_new"
        selected_value = st.selectbox(
            f"{params['selectbox_label']}(新規)",
            params["id_title_list"],
            index=(expected_index if expected_index != -1 else 0),
            key=connection_key,
            label_visibility=visibility,
        )
        edge[params["selectbox_index"]] = params["id_title_dict"][selected_value]
    with params["description_column"]:
        comment_key = f"comment_{params['selectbox_key']}_new"
        edge["comment"] = st.text_input(
            "説明(新規)",
            value="",
            key=comment_key,
            label_visibility=visibility,
        )


# ページ全体のデータ読み込みと基本設定
page_elements = setup_page_layout_and_data("CCPM Viewer")

# setup_page_layout_and_data から返された要素を変数に展開
color_list = page_elements["color_list"]
config_data = page_elements["config_data"]
app_data = page_elements["app_data"]
file_path = page_elements["file_path"]
requirement_data = page_elements["requirement_data"]
nodes = page_elements["nodes"]
edges = page_elements["edges"]
requirement_manager = page_elements["requirement_manager"]
graph_data = page_elements["graph_data"]
id_title_dict = page_elements["id_title_dict"]
unique_id_dict = page_elements["unique_id_dict"]
id_title_list = page_elements["id_title_list"]
selected_unique_id = page_elements["selected_unique_id"]
selected_entity = page_elements["selected_entity"]

# 編集用カラムと図表示カラム、PlantUMLコードを page_elements から取得
edit_column = page_elements["edit_column"]
diagram_column = page_elements["diagram_column"]
plantuml_code = page_elements["plantuml_code"]


@st.fragment
def render_edit_panel():
    """右側操作パネルの描画（部分再描画対応）"""
    # リセット対象キーの登録
    if "clearable_new_connection_keys" not in st.session_state:
        st.session_state.clearable_new_connection_keys = {}
    st.session_state.clearable_new_connection_keys["CCPM Viewer"] = [
        f"{edge_params['to_selected']['selectbox_key']}_new",
        f"comment_{edge_params['to_selected']['selectbox_key']}_new",
        f"{edge_params['from_selected']['selectbox_key']}_new",
        f"comment_{edge_params['from_selected']['selectbox_key']}_new",
    ]

    title_column, file_selector_column = st.columns([4, 4])
    with title_column:
        st.write("### データ編集")
    with file_selector_column:
        backup_files = get_backup_files_for_current_data()
        st.selectbox(
            "ファイルを選択",
            backup_files,
            0,
            label_visibility="collapsed",
            on_change=copy_file,
            key="selected_backup_file",
        )

    # --- プロジェクト設定 (expander) ---
    project = requirement_data.get("project", {})
    with st.expander("📅 プロジェクト設定", expanded=False):
        project["start"] = st.text_input(
            "プロジェクト開始日", value=project.get("start", ""), key="ccpm_proj_start"
        )
        project["end"] = st.text_input(
            "プロジェクト終了日", value=project.get("end", ""), key="ccpm_proj_end"
        )
        project["today"] = st.text_input(
            "今日の日付", value=project.get("today", ""), key="ccpm_proj_today"
        )
        holidays_str = st.text_area(
            "祝日 (YYYY/MM/DD を1行ずつ)",
            value="\n".join(project.get("holidays", [])),
            height=100,
            key="ccpm_proj_holidays",
        )
        project["holidays"] = [
            h.strip() for h in holidays_str.split("\n") if h.strip()
        ]
        requirement_data["project"] = project

        if st.button("プロジェクト設定を保存", key="ccpm_save_project"):
            update_source_data(file_path, requirement_manager.requirements)
            st.success("プロジェクト設定を保存しました。")
            st.rerun()

    st.write("---")

    # --- エンティティ編集 (PFD と同じ操作感) ---
    tmp_entity = copy.deepcopy(selected_entity)
    tmp_entity["unique_id"] = f"{uuid.uuid4()}".replace("-", "")
    tmp_entity.setdefault("color", "None")
    tmp_entity.setdefault("type", "process")
    # CCPM 固有フィールドのフォールバック
    for field, default in [
        ("days", 1), ("remains", 0), ("resource", ""),
        ("start", ""), ("end", ""), ("finished", False),
    ]:
        tmp_entity.setdefault(field, default)

    # 後でボタンを配置する
    top_button_container = st.container()

    tmp_entity["type"] = st.selectbox(
        "タイプ", ccpm_type_list, index=ccpm_type_list.index(tmp_entity["type"]),
        key=f"ccpm_type_{selected_unique_id}",
    )
    tmp_entity["title"] = st.text_area(
        "タスク名",
        unescape_newline(tmp_entity.get("title", "")),
        height=calculate_text_area_height(unescape_newline(tmp_entity.get("title", ""))),
        key=f"ccpm_title_{selected_unique_id}",
    )

    # CCPM 固有フィールド
    col_days, col_remains = st.columns(2)
    with col_days:
        tmp_entity["days"] = st.number_input(
            "見積り日数", min_value=0.0, value=float(tmp_entity.get("days", 1)),
            step=0.5, key=f"ccpm_days_{selected_unique_id}",
        )
    with col_remains:
        tmp_entity["remains"] = st.number_input(
            "残日数", min_value=0.0, value=float(tmp_entity.get("remains", 0)),
            step=0.5, key=f"ccpm_remains_{selected_unique_id}",
        )

    tmp_entity["resource"] = st.text_input(
        "担当者", tmp_entity.get("resource", ""),
        key=f"ccpm_resource_{selected_unique_id}",
    )

    col_start, col_end = st.columns(2)
    with col_start:
        tmp_entity["start"] = st.text_input(
            "開始日", tmp_entity.get("start", ""),
            key=f"ccpm_start_{selected_unique_id}",
        )
    with col_end:
        tmp_entity["end"] = st.text_input(
            "終了日", tmp_entity.get("end", ""),
            key=f"ccpm_end_{selected_unique_id}",
        )

    tmp_entity["finished"] = st.checkbox(
        "完了", value=tmp_entity.get("finished", False),
        key=f"ccpm_finished_{selected_unique_id}",
    )

    tmp_entity["color"] = st.selectbox(
        "色", color_list,
        index=color_list.index(tmp_entity["color"]),
        key=f"ccpm_color_{selected_unique_id}",
    )

    # --- エッジ編集 (PFD と同じ) ---
    tmp_edges = copy.deepcopy(requirement_data["edges"])

    # 接続元
    params_to = edge_params["to_selected"]
    params_to["selected_unique_id"] = selected_unique_id
    params_to["id_title_dict"] = id_title_dict
    params_to["unique_id_dict"] = unique_id_dict
    params_to["id_title_list"] = id_title_list
    params_to["connection_column"], params_to["description_column"] = st.columns([1, 1])
    visibility = "visible"
    for i, edge in enumerate(tmp_edges):
        visibility = render_edge_connection(edge, i, visibility, edge_params["to_selected"])

    temp_predecessor = {
        "source": "None",
        "destination": tmp_entity["unique_id"],
        "comment": "",
        "type": "arrow",
    }
    visibility = "visible"
    render_edge_connection_new(temp_predecessor, 0, visibility, edge_params["to_selected"])

    st.write("---")

    # 接続先
    params_from = edge_params["from_selected"]
    params_from["selected_unique_id"] = selected_unique_id
    params_from["id_title_dict"] = id_title_dict
    params_from["unique_id_dict"] = unique_id_dict
    params_from["id_title_list"] = id_title_list
    params_from["connection_column"], params_from["description_column"] = st.columns([1, 1])
    visibility = "visible"
    for i, edge in enumerate(tmp_edges):
        visibility = render_edge_connection(edge, i, visibility, edge_params["from_selected"])

    temp_successor = {
        "source": tmp_entity["unique_id"],
        "destination": "None",
        "comment": "",
        "type": "arrow",
    }
    visibility = "visible"
    render_edge_connection_new(temp_successor, 0, visibility, edge_params["from_selected"])

    # --- ボタン ---
    new_edges = [temp_predecessor, temp_successor]
    with top_button_container:
        add_operate_buttons(
            selected_unique_id, tmp_entity, requirement_manager,
            file_path, id_title_dict, unique_id_dict,
            tmp_edges=tmp_edges, new_edges=new_edges,
            key_suffix="top", display_key="title",
        )

    add_operate_buttons(
        selected_unique_id, tmp_entity, requirement_manager,
        file_path, id_title_dict, unique_id_dict,
        tmp_edges=tmp_edges, new_edges=new_edges,
        key_suffix="bottom", display_key="title",
    )


def render_ccpm_analysis():
    """左カラムに CCPM 分析セクションを描画する。"""
    st.write("---")
    st.write("### 📊 CCPM 分析")

    # グラフからクリティカルパスとクリティカルチェーンを算出
    nx_graph = graph_data.graph
    inputs, outputs = get_in_out_edge_list(nx_graph)
    cp_length, cp = calculate_critical_path(nx_graph, inputs, outputs)
    cc_length, cc, virtual_edges = calculate_critical_chain(nx_graph)

    def _format_chain(graph, chain):
        """チェーンのタスク名リストを作成する（days>0のみ）。"""
        return [graph.nodes[n].get("title", n) for n in chain if graph.nodes[n].get("days", 0) > 0]

    if cp:
        cp_titles = _format_chain(nx_graph, cp)
        cc_titles = _format_chain(nx_graph, cc) if cc else []

        # CP と CC が異なるか判定
        cp_changed = (cp != cc)

        if cp_changed and cc:
            st.warning(
                f"**クリティカルパス** (依存関係のみ, {cp_length}日): {' → '.join(cp_titles)}"
            )
            st.error(
                f"**クリティカルチェーン** (リソース競合考慮, {cc_length}日): {' → '.join(cc_titles)}"
            )
        elif cc:
            st.info(
                f"**クリティカルチェーン** ({cc_length}日): {' → '.join(cc_titles)}\n\n"
                f"リソース競合なし — クリティカルパスと一致"
            )
        else:
            st.info(f"**クリティカルパス** ({cp_length}日): {' → '.join(cp_titles)}")

        # リソース競合（仮想エッジ）情報
        if virtual_edges:
            with st.expander(f"⚠️ リソース競合: {len(virtual_edges)}件の直列化が必要", expanded=True):
                for src, dst, resource in virtual_edges:
                    src_title = nx_graph.nodes[src].get("title", src)
                    dst_title = nx_graph.nodes[dst].get("title", dst)
                    st.write(
                        f"- **{resource}**: "
                        f"「{src_title}」→「{dst_title}」（{resource} が並行不可のため直列化）"
                    )
    else:
        st.warning("クリティカルパスが計算できません。タスクと依存関係を確認してください。")

    # 分析で使うチェーン（CC があればそちらを優先）
    active_chain = cc if cc else cp
    active_length = cc_length if cc else cp_length

    # タブ表示
    tab_gantt, tab_fever, tab_priority = st.tabs(["📅 ガントチャート", "🌡️ フィーバーチャート", "📋 優先度"])

    with tab_gantt:
        project = requirement_data.get("project", {})
        if project.get("start") and active_chain:
            gantt_puml = make_gantt_puml(nx_graph, project, active_chain)
            plantuml_server = config_data.get("plantuml", "")
            if "runtime_plantuml_url" in st.session_state:
                plantuml_server = st.session_state["runtime_plantuml_url"]
            if plantuml_server:
                gantt_svg = get_diagram(gantt_puml, plantuml_server)
                if gantt_svg:
                    st.html(gantt_svg)
                else:
                    st.error("ガントチャートの生成に失敗しました。")
            else:
                st.warning("PlantUML サーバーが設定されていません。")
        else:
            st.info("プロジェクト開始日を設定してください。")

    with tab_fever:
        if go is None:
            st.warning("plotly がインストールされていません。")
        elif active_chain:
            fever = calculate_fever_data(
                nx_graph, requirement_data.get("project", {}), active_chain, active_length
            )

            # 過去の進捗データ
            progress_data = requirement_data.get("progress", {})
            dates = list(progress_data.keys())
            progress_hist = [v[0] if isinstance(v, list) else v for v in progress_data.values()]
            buffer_hist = [v[1] if isinstance(v, list) else 0 for v in progress_data.values()]

            # 現在値を追加
            today_str = requirement_data.get("project", {}).get("today", "now")
            dates.append(today_str)
            progress_hist.append(fever["progress"])
            buffer_hist.append(fever["buffer_used"])

            fig = go.Figure()
            # ゾーン境界線
            x = list(range(0, 110))
            y1 = [0.6 * xi + 15 for xi in x]
            y2 = [0.6 * xi + 30 for xi in x]
            fig.add_trace(go.Scatter(x=x, y=y1, mode="lines", line=dict(color="green", width=1), showlegend=False))
            fig.add_trace(go.Scatter(x=x, y=y2, mode="lines", line=dict(color="orange", width=1), showlegend=False))
            # 進捗プロット（日付ラベル付き）
            fig.add_trace(go.Scatter(
                x=progress_hist, y=buffer_hist,
                mode="lines+markers+text",
                text=dates,
                textposition="top center",
                textfont=dict(size=9),
                name="進捗",
            ))
            fig.update_layout(
                xaxis_title="クリティカルチェーン完了率 (%)", yaxis_title="バッファ消費率 (%)",
                xaxis=dict(range=[0, 100]), yaxis=dict(range=[0, 100]),
                height=400,
            )
            fig.add_shape(type="rect", x0=0, x1=100, y0=0, y1=0, line_width=0)
            st.plotly_chart(fig, use_container_width=True)

            # 記録ボタン
            st.caption(
                f"📊 CC完了率: **{fever['progress']:.1f}%** / バッファ消費率: **{fever['buffer_used']:.1f}%**"
            )
            if st.button("📝 現在の値を記録", key="ccpm_record_fever"):
                if "progress" not in requirement_data:
                    requirement_data["progress"] = {}
                requirement_data["progress"][today_str] = [
                    round(fever["progress"], 2),
                    round(fever["buffer_used"], 2),
                ]
                update_source_data(file_path, requirement_manager.requirements)
                st.success(f"{today_str} の値を記録しました。")
                st.rerun()
        else:
            st.info("クリティカルパスが計算できません。")

    with tab_priority:
        if active_chain:
            priority = calculate_priority_table(nx_graph, active_chain)
            if priority:
                st.dataframe(priority, use_container_width=True)
            else:
                st.info("全タスクが完了しているか、優先度を計算できません。")
        else:
            st.info("クリティカルパスが計算できません。")


with edit_column:
    render_edit_panel()

with diagram_column:
    render_ccpm_analysis()

st.session_state.graph_data = graph_data
