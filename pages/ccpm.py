import streamlit as st
from src.operate_buttons import add_operate_buttons, add_node_selector
from src.page_setup import setup_page_layout_and_data
from src.diagram_column import draw_diagram_column
from src.bulk_input import render_bulk_input_ui
from src.utility import (
    get_backup_files_for_current_data,
    copy_file,
    calculate_text_area_height,
    unescape_newline,
    update_source_data,
    show_backup_diff_preview,
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
                    key=f"{params['selectbox_key']}_{params['selected_unique_id']}_{index}",
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
    if "--- 未選択 ---" in params["id_title_list"]:
        expected_index = params["id_title_list"].index("--- 未選択 ---")
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


# ページ全体のデータ読み込みと基本設定（ダイアグラム描画はスキップしタブ内で行う）
page_elements = setup_page_layout_and_data("CCPM Viewer", skip_diagram=True)

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

# 編集用カラムと図表示カラム、ダイアグラム描画用のコンテキストを取得
edit_column = page_elements["edit_column"]
diagram_column = page_elements["diagram_column"]
diagram_context = page_elements["diagram_context"]
diagram_options = page_elements["diagram_options"]

def _render_entity_settings(selected_entity: dict, selected_unique_id: str, ccpm_type_list: list, color_list: list) -> dict:
    """エンティティ編集 (PFD と同じ操作感) の UI を描画し、入力結果の辞書を返す"""
    tmp_entity = copy.deepcopy(selected_entity) or {}
    tmp_entity["unique_id"] = f"{uuid.uuid4()}".replace("-", "")
    tmp_entity.setdefault("color", "None")
    tmp_entity.setdefault("type", "process")
    # CCPM 固有フィールドのフォールバック
    for field, default in [
        ("days", 1), ("remains", 0), ("resource", ""),
        ("start", ""), ("end", ""), ("finished", False),
    ]:
        tmp_entity.setdefault(field, default)

    tmp_entity["type"] = st.selectbox(
        "タイプ", ccpm_type_list, index=ccpm_type_list.index(tmp_entity.get("type", "process")),
        key=f"ccpm_type_{selected_unique_id}",
    )
    tmp_entity["title"] = st.text_area(
        "タスク名",
        unescape_newline(tmp_entity.get("title", "")),
        height=calculate_text_area_height(unescape_newline(tmp_entity.get("title", ""))),
        key=f"ccpm_title_{selected_unique_id}",
    )

    # CCPM 固有フィールド
    col_days, col_remains, col_finished = st.columns([2, 2, 1])
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
    with col_finished:
        st.write("")
        st.write("")
        tmp_entity["finished"] = st.checkbox(
            "完了", value=tmp_entity.get("finished", False),
            key=f"ccpm_finished_{selected_unique_id}",
        )

    col_start, col_end, col_actual = st.columns([2, 2, 1])
    
    def _get_entity_date(d_str):
        if not d_str:
            return None
        try:
            from datetime import datetime
            return datetime.strptime(d_str, "%Y/%m/%d").date()
        except ValueError:
            return None

    def _get_val_node(key: str, default_val):
        if key in st.session_state:
            return st.session_state[key]
        return default_val

    with col_start:
        start_key = f"ccpm_start_{selected_unique_id}"
        raw_estart = st.date_input(
            "開始日", value=_get_val_node(start_key, _get_entity_date(tmp_entity.get("start", ""))),
            key=start_key,
        )
        tmp_entity["start"] = raw_estart.strftime("%Y/%m/%d") if raw_estart else ""

    with col_end:
        end_key = f"ccpm_end_{selected_unique_id}"
        raw_eend = st.date_input(
            "終了日", value=_get_val_node(end_key, _get_entity_date(tmp_entity.get("end", ""))),
            key=end_key,
        )
        tmp_entity["end"] = raw_eend.strftime("%Y/%m/%d") if raw_eend else ""

    with col_actual:
        st.write("")
        if raw_estart:
            from datetime import datetime
            import workdays
            
            calc_end = raw_eend if raw_eend else datetime.now().date()
            
            # config_dataのprojectから休日を取得
            # pages/ccpm.py自体にはconfig_dataが関数の引数等で直接渡されていない場合もあるため、
            # Streamlitのsession_stateなどから取れるか試みるか、デフォルト空で渡す
            holidays = []
            if "config_data" in st.session_state and "project" in st.session_state["config_data"]:
                h_strs = st.session_state["config_data"]["project"].get("holidays", [])
                holidays = [datetime.strptime(h, "%Y/%m/%d").date() for h in h_strs]
                
            actual_days = workdays.networkdays(raw_estart, calc_end, holidays=holidays)
            st.markdown(f"<div style='margin-top: 14px;'>実績: <b>{actual_days}日</b></div>", unsafe_allow_html=True)

    tmp_entity["resource"] = st.text_input(
        "担当者", tmp_entity.get("resource", ""),
        key=f"ccpm_resource_{selected_unique_id}",
    )

    tmp_entity["color"] = st.selectbox(
        "色", color_list,
        index=color_list.index(tmp_entity.get("color", "None")),
        key=f"ccpm_color_{selected_unique_id}",
    )
    
    return tmp_entity


def _render_edge_settings_and_buttons(
    requirement_data: dict,
    selected_unique_id: str,
    id_title_dict: dict,
    unique_id_dict: dict,
    id_title_list: list,
    tmp_entity: dict,
    top_button_container,
    requirement_manager,
    file_path: str,
):
    """エッジ編集 (依存関係) および保存/削除などの操作ボタン UI を描画する"""
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


def _render_project_settings(
    requirement_data: dict,
    graph_data,
    requirement_manager,
    file_path: str,
):
    """プロジェクトの基本設定 (開始日, 終了日, 祝日, リソースなど) UI を描画する"""
    project = requirement_data.get("project", {})
    with st.expander("📅 プロジェクト設定", expanded=False):
        from datetime import datetime
        
        # 文字列をdatetime(date)に変換するヘルパー。未設定ならNoneを返す
        def _get_date(date_str: str):
            if not date_str:
                return None
            try:
                return datetime.strptime(date_str, "%Y/%m/%d").date()
            except ValueError:
                return None
                
        # st.date_input がクリアされた時に初期値で巻き戻らないようにするヘルパー
        def _get_val(key: str, default_val):
            if key in st.session_state:
                return st.session_state[key]
            return default_val
        
        col_proj1, col_proj2, col_proj3 = st.columns(3)
        with col_proj1:
            raw_start = st.date_input(
                "開始日", value=_get_val("ccpm_proj_start", _get_date(project.get("start", ""))), key="ccpm_proj_start"
            )
        with col_proj2:
            raw_end = st.date_input(
                "終了日", value=_get_val("ccpm_proj_end", _get_date(project.get("end", ""))), key="ccpm_proj_end"
            )
        with col_proj3:
            raw_today = st.date_input(
                "今日の日付", value=_get_val("ccpm_proj_today", _get_date(project.get("today", ""))), key="ccpm_proj_today"
            )
            
        project["start"] = raw_start.strftime("%Y/%m/%d") if raw_start else ""
        project["end"] = raw_end.strftime("%Y/%m/%d") if raw_end else ""
        project["today"] = raw_today.strftime("%Y/%m/%d") if raw_today else ""

        col_text1, col_text2 = st.columns(2)
        with col_text1:
            holidays_str = st.text_area(
                "祝日 (YYYY/MM/DD を1行ずつ)",
                value="\n".join(project.get("holidays", [])),
                height=150,
                key="ccpm_proj_holidays",
            )
            project["holidays"] = [
                h.strip() for h in holidays_str.split("\n") if h.strip()
            ]
        with col_text2:
            resources_str = st.text_area(
                "利用可能リソース (上限数計算用 / 1名ずつ改行)",
                value="\n".join(project.get("resources", [])),
                height=150,
                key="ccpm_proj_resources",
                help="入力された行数（人数）が、プロジェクト全体の同時実行可能なタスク数の上限としてクリティカルチェーン算出時に考慮されます。"
            )
            project["resources"] = [
                r.strip() for r in resources_str.split("\n") if r.strip()
            ]

        requirement_data["project"] = project

        # クリティカルチェーン長の事前計算
        nx_graph = graph_data.graph
        try:
            inputs, outputs = get_in_out_edge_list(nx_graph)
            cp_length, cp = calculate_critical_path(nx_graph, inputs, outputs)
            max_concurrency = len(project.get("resources", []))
            cc_length, cc, _ = calculate_critical_chain(nx_graph, max_concurrency=max_concurrency)
            active_chain = cc if cc else cp
            active_length = cc_length if cc else cp_length
        except Exception:
            active_chain = []
            active_length = 0

        # 日数計算と表示
        try:
            if project.get("start") and project.get("end") and project.get("today"):
                import workdays as wd
                s_date = datetime.strptime(project["start"], "%Y/%m/%d")
                e_date = datetime.strptime(project["end"], "%Y/%m/%d")
                t_date = datetime.strptime(project["today"], "%Y/%m/%d")
                
                if s_date <= e_date:
                    # 1. 総日数 (両端含む)
                    total_days = (e_date - s_date).days + 1
                    
                    # 2. 土日抜きの日数
                    weekdays_only = wd.networkdays(s_date, e_date)
                    
                    # 3. 土日祝抜きの実稼働日数
                    holidays_list = []
                    for h_str in project.get("holidays", []):
                        try:
                            holidays_list.append(datetime.strptime(h_str, "%Y/%m/%d"))
                        except ValueError:
                            pass
                    actual_workdays = wd.networkdays(s_date, e_date, holidays_list)
                    
                    # 今日の日付からの残日数（土日祝抜）
                    if t_date <= e_date:
                        # 今日が開始日より前なら、開始日からの日数と同じにする
                        calc_start = max(s_date, t_date)
                        remain_workdays = wd.networkdays(calc_start, e_date, holidays_list)
                        remain_text = f"(残り {remain_workdays} 日)"
                    else:
                        remain_text = "(終了済み)"
                    
                    # 現在のCC情報の計算
                    cc_info_text = "<b>🚨 クリティカルチェーン情報</b><br>・<i>(ネットワーク図が計算されていません)</i>"
                    if active_chain and active_length > 0:
                        # 動的進捗情報の計算
                        fever_data = calculate_fever_data(
                            nx_graph, project, active_chain, active_length
                        )
                        progress = fever_data["progress"]
                        buffer_used = fever_data["buffer_used"]
                        remaining_cc = fever_data["remaining_cc_length"]
                        consumed_buf = fever_data["consumed_buffer"]
                        base_total_buf = fever_data["baseline_total_buffer"]
                        remaining_buf = base_total_buf - consumed_buf
                        
                        buffer_color = "red" if remaining_buf < 0 else "green"
                        
                        cc_info_text = f"""
                        <b>🚨 クリティカルチェーン情報</b><br>
                        ・現在のCC長 (予想総所要日数): <b>{active_length}</b> 日<br>
                        ・現在の全バッファ: <b>{base_total_buf:.1f}</b> 日<br>
                        ・今日からの残CC長: <b>{remaining_cc:.1f}</b> 日 (完了率: <b>{progress:.1f}%</b>)<br>
                        ・今日からの残バッファ: <span style='color: {buffer_color}; font-weight: bold;'>{remaining_buf:.1f}</span> 日 (消費率: <b>{buffer_used:.1f}%</b>)
                        """
    
                    st.markdown(
                        f"""
                        <div style='background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 10px;'>
                            <b>📅 プロジェクト期間情報</b><br>
                            ・総日数 (土日祝込): <b>{total_days}</b> 日<br>
                            ・土日抜き日数: <b>{weekdays_only}</b> 日<br>
                            ・実稼働日数 (土日祝抜): <span style='color: blue; font-weight: bold;'>{actual_workdays}</span> 日 <span style='color: red; font-weight: bold;'>{remain_text}</span>
                        </div>
                        
                        <div style='background-color: #fff3cd; padding: 10px; border-radius: 5px; margin-bottom: 10px;'>
                            {cc_info_text}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.warning("終了日は開始日以降に設定してください。")
            else:
                st.info("カレンダーで開始日、終了日、今日の日付を設定してください。")
        except Exception as e:
            st.warning("日付計算でエラーが発生しました。")

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🚩 現在のCCをベースラインに登録", key="ccpm_save_baseline"):
                if not (project.get("start") and project.get("end") and project.get("today")):
                    st.warning("開始日・終了日・今日の日付を設定してから登録してください。")
                elif active_length > 0:
                    try:
                        import workdays as wd
                        s_date = datetime.strptime(project["start"], "%Y/%m/%d")
                        e_date = datetime.strptime(project["end"], "%Y/%m/%d")
                        holidays_list = [datetime.strptime(h, "%Y/%m/%d") for h in project.get("holidays", []) if h]
                        
                        total_workdays = wd.networkdays(s_date, e_date, holidays_list)
                        total_buffer = total_workdays - active_length
                        
                        project["baseline"] = {
                            "cc_length": active_length,
                            "total_buffer": total_buffer,
                            "registered_at": datetime.today().strftime("%Y/%m/%d %H:%M:%S")
                        }
                        update_source_data(file_path, requirement_manager.requirements)
                        st.toast(f"CC長: {active_length}日, 全バッファ: {total_buffer}日 でベースラインを登録しました ✅")
                    except Exception as e:
                        st.error(f"ベースライン登録エラー: {e}")
                else:
                    st.warning("クリティカルチェーンが計算されていません。")
        with col_btn2:
            if st.button("💾 プロジェクト設定を保存", key="ccpm_save_project"):
                update_source_data(file_path, requirement_manager.requirements)
                st.toast("プロジェクト設定を保存しました ✅")
                st.rerun()
                    

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
            key="selected_backup_file",
        )
    show_backup_diff_preview(requirement_data)

    _render_project_settings(
        requirement_data=requirement_data,
        graph_data=graph_data,
        requirement_manager=requirement_manager,
        file_path=file_path,
    )

    # --- タブ切り替え: 個別入力 / 一括入力 ---
    tab_individual, tab_bulk = st.tabs(["✏️ 個別入力", "📝 一括入力"])

    with tab_individual:
        _render_individual_ccpm_edit()

    with tab_bulk:
        render_bulk_input_ui(
            nodes=requirement_data.get("nodes", []),
            requirement_manager=requirement_manager,
            file_path=file_path,
            type_list=ccpm_type_list,
            display_key="title",
            page_key_prefix="ccpm",
            content_field="title",
            extra_fields={"days": 1, "remains": 0, "resource": "",
                          "start": "", "end": "", "finished": False},
            metadata_columns=[
                {"key": "days", "name": "日数", "type": int, "default": 1},
                {"key": "resource", "name": "担当", "type": str, "default": ""},
                {"key": "color", "name": "色", "type": str, "default": "None"},
            ],
        )


def _render_individual_ccpm_edit():
    """個別エンティティ編集タブの内容を描画する。"""
    add_node_selector(id_title_list, id_title_dict, unique_id_dict, selected_unique_id)

    # 後でボタンを配置する
    top_button_container = st.container()

    tmp_entity = _render_entity_settings(selected_entity, selected_unique_id, ccpm_type_list, color_list)

    _render_edge_settings_and_buttons(
        requirement_data=requirement_data,
        selected_unique_id=selected_unique_id,
        id_title_dict=id_title_dict,
        unique_id_dict=unique_id_dict,
        id_title_list=id_title_list,
        tmp_entity=tmp_entity,
        top_button_container=top_button_container,
        requirement_manager=requirement_manager,
        file_path=file_path,
    )


def _render_gantt_tab(
    project: dict,
    active_chain: list,
    nx_graph,
    virtual_edges: list,
    config_data: dict,
):
    """ガントチャートタブの UI を描画する"""
    if project.get("start") and active_chain:
        gantt_puml = make_gantt_puml(nx_graph, project, active_chain, virtual_edges)
        plantuml_server = config_data.get("plantuml", "")
        if "runtime_plantuml_url" in st.session_state:
            plantuml_server = st.session_state["runtime_plantuml_url"]
        if plantuml_server:
            gantt_svg = get_diagram(gantt_puml, plantuml_server)
            if gantt_svg:
                # デバッグ用にファイル出力
                try:
                    with open("debug_gantt.svg", "w", encoding="utf-8") as f:
                        f.write(gantt_svg)
                    with open("debug_gantt.puml", "w", encoding="utf-8") as f:
                        f.write(gantt_puml)
                except Exception as e:
                    st.error(f"デバッグファイルの出力に失敗しました: {e}")

                # デフォルトで付くリンク下線を隠す
                gantt_svg = gantt_svg.replace(
                    "<defs/>", "<defs/><style>a {text-decoration: none !important;}</style>"
                )
                st.markdown(
                    f'''
                    <div style="width:100%; min-height:{config_data.get('viewer_height', 600)}px; overflow:auto; border:0px solid black;">
                        {gantt_svg}
                    </div>
                    ''',
                    unsafe_allow_html=True,
                )
            else:
                st.error("ガントチャートの生成に失敗しました。")
        else:
            st.warning("PlantUML サーバーが設定されていません。")
    else:
        st.info("プロジェクト開始日を設定してください。")


def _render_fever_tab(
    active_chain: list,
    nx_graph,
    requirement_data: dict,
    active_length: float,
    requirement_manager,
    file_path: str,
):
    """フィーバーチャートタブの UI を描画する"""
    if go is None:
        st.warning("plotly がインストールされていません。")
    elif active_chain:
        fever_data = calculate_fever_data(
            nx_graph, requirement_data.get("project", {}), active_chain, active_length
        )
        # progress と buffer_used を抽出
        fever = {
            "progress": fever_data["progress"],
            "buffer_used": fever_data["buffer_used"]
        }

        # 過去の進捗データ
        progress_data = requirement_data.get("progress", {})
        dates = []
        progress_hist = []
        buffer_hist = []
        memos = []
        for k, v in progress_data.items():
            dates.append(k)
            if isinstance(v, list):
                progress_hist.append(v[0] if len(v) > 0 else 0)
                buffer_hist.append(v[1] if len(v) > 1 else 0)
                memos.append(str(v[2]) if len(v) > 2 else "")
            else:
                progress_hist.append(v)
                buffer_hist.append(0)
                memos.append("")

        # 現在値を追加（もし今日の記録が既にある場合は、チャート上では現在の計算値で置き換える）
        today_str = requirement_data.get("project", {}).get("today", "now")
        if today_str in dates:
            idx = dates.index(today_str)
            dates.pop(idx)
            progress_hist.pop(idx)
            buffer_hist.pop(idx)
            memos.pop(idx)
        
        dates.append(today_str + " (現在)")
        progress_hist.append(fever["progress"])
        buffer_hist.append(fever["buffer_used"])
        memos.append("")
        
        # メモ付きのチャートラベルを生成
        plot_texts = []
        for d, m in zip(dates, memos):
            if m:
                plot_texts.append(f"{d}<br>🗣 {m}")
            else:
                plot_texts.append(d)

        # チャート（75%縮小に伴いカラム比率を拡大）とデータテーブルを横並び
        chart_col, data_col = st.columns([2, 1])

        with chart_col:
            fig = go.Figure()
            
            # Y軸の最大値を計算（100を超える場合は自動拡張）
            max_buf = max(buffer_hist) if buffer_hist else 0
            y_range_max = 100
            if max_buf > 100:
                y_range_max = int(max_buf + 9) // 10 * 10 + 10

            # ゾーン塗りつぶし（緑→黄→赤→グレー）
            x = list(range(0, 101))
            y1 = [0.6 * xi + 10 for xi in x]  # 緑/黄 境界 (以前の15から10に下げて厳格化)
            y2 = [0.6 * xi + 25 for xi in x]  # 黄/赤 境界 (以前の30から25に下げて厳格化)
            
            # 緑ゾーン（下）
            fig.add_trace(go.Scatter(
                x=x, y=y1, fill="tozeroy", fillcolor="rgba(144,238,144,0.3)",
                line=dict(color="green", width=1), showlegend=False,
            ))
            # 黄ゾーン（中）
            fig.add_trace(go.Scatter(
                x=x, y=y2, fill="tonexty", fillcolor="rgba(255,255,150,0.3)",
                line=dict(color="orange", width=1), showlegend=False,
            ))
            # 赤ゾーン（100%まで）
            y_100 = [100] * len(x)
            fig.add_trace(go.Scatter(
                x=x, y=y_100, fill="tonexty", fillcolor="rgba(255,160,160,0.3)",
                line=dict(width=0), showlegend=False,
            ))
            # 100%超え グレーゾーン
            if y_range_max > 100:
                y_top = [y_range_max] * len(x)
                fig.add_trace(go.Scatter(
                    x=x, y=y_top, fill="tonexty", fillcolor="rgba(200,200,200,0.3)",
                    line=dict(width=0), showlegend=False,
                ))

            # 進捗プロット（日付・メモラベル付き）
            fig.add_trace(go.Scatter(
                x=progress_hist, y=buffer_hist,
                mode="lines+markers+text",
                text=plot_texts,
                textposition="top center",
                textfont=dict(size=18),
                marker=dict(size=14),
                line=dict(width=4),
                name="進捗",
            ))
            fig.update_layout(
                xaxis_title="クリティカルチェーン完了率 (%)", yaxis_title="バッファ消費率 (%)",
                xaxis=dict(range=[0, 100], tickfont=dict(size=18)),
                yaxis=dict(range=[0, y_range_max], tickfont=dict(size=18)),
                font=dict(size=20),
                hoverlabel=dict(font_size=20),
                width=900, height=675, # 75%縮小
                margin=dict(t=30, b=50, l=50, r=30),
            )
            st.plotly_chart(fig, width="content")

        with data_col:
            st.caption(
                f"📊 CC完了率: **{fever['progress']:.1f}%** / バッファ消費率: **{fever['buffer_used']:.1f}%**"
            )
            if st.button("📝 現在の値を記録", key="ccpm_record_fever"):
                if "progress" not in requirement_data:
                    requirement_data["progress"] = {}
                requirement_data["progress"][today_str] = [
                    round(fever["progress"], 2),
                    round(fever["buffer_used"], 2),
                    ""
                ]
                update_source_data(file_path, requirement_manager.requirements)
                st.success(f"{today_str} の値を記録しました。")
                st.query_params.view = "fever"
                st.rerun()

            # 過去データの編集テーブル
            st.write("##### 📋 記録データ")
            import pandas as pd
            if progress_data:
                df = pd.DataFrame([
                    {
                        "日付": k, 
                        "CC完了率(%)": v[0] if isinstance(v, list) and len(v) > 0 else v, 
                        "バッファ消費率(%)": v[1] if isinstance(v, list) and len(v) > 1 else 0,
                        "メモ": str(v[2]) if isinstance(v, list) and len(v) > 2 else ""
                    }
                    for k, v in progress_data.items()
                ])
                edited_df = st.data_editor(
                    df, num_rows="dynamic", width="stretch",
                    key="ccpm_progress_editor",
                )
                if st.button("💾 データを保存", key="ccpm_save_progress"):
                    new_progress = {}
                    for _, row in edited_df.iterrows():
                        date_key = str(row["日付"])
                        if date_key and date_key != "nan":
                            new_progress[date_key] = [
                                round(float(row["CC完了率(%)"]), 2),
                                round(float(row["バッファ消費率(%)"]), 2),
                                str(row.get("メモ", ""))
                            ]
                    
                    # 日付キー辞書の昇順（文字列順）でソート
                    sorted_progress = dict(sorted(new_progress.items(), key=lambda item: item[0]))
                    requirement_data["progress"] = sorted_progress
                    update_source_data(file_path, requirement_manager.requirements)
                    st.toast("データを保存しました ✅")
                    st.query_params.view = "fever"
                    st.rerun()
            else:
                st.info("まだ記録がありません。")
    else:
        st.info("クリティカルパスが計算できません。")


def _render_priority_tab(active_chain: list, nx_graph):
    """優先度タブの UI (優先度テーブル) を描画する"""
    if active_chain:
        priority = calculate_priority_table(nx_graph, active_chain)
        if priority:
            import pandas as pd
            df = pd.DataFrame(priority)
            
            # 表示の整理と日本語ヘッダーへのリネーム
            df = df[["status", "title", "resource", "days", "total_remains", "buffer", "task"]]
            df = df.rename(columns={
                "status": "状態",
                "title": "タスク名",
                "resource": "担当",
                "days": "工数(日)",
                "total_remains": "後続パス長",
                "buffer": "余裕(バッファ)",
                "task": "ID"
            })
            
            # ID列などを見やすく調整しつつ出力
            st.dataframe(df, width="stretch", hide_index=True)
        else:
            st.info("優先度を計算できるタスクがありません。")
    else:
        st.info("クリティカルパスが計算できません。")


def render_ccpm_analysis():
    """左カラムに CCPM 分析セクションを描画する。"""
    st.write("### 📊 CCPM 分析")

    # グラフからクリティカルパスとクリティカルチェーンを算出
    nx_graph = graph_data.graph
    inputs, outputs = get_in_out_edge_list(nx_graph)
    cp_length, cp = calculate_critical_path(nx_graph, inputs, outputs)
    
    # プロジェクト設定から同時実行上限を取得
    project = requirement_data.get("project", {})
    max_concurrency = len(project.get("resources", []))
    cc_length, cc, virtual_edges = calculate_critical_chain(nx_graph, max_concurrency=max_concurrency)

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

    # 着手済み・未完了・残日数0 のタスクに対する警告
    zero_remains_tasks = [
        nx_graph.nodes[n].get("title", n)
        for n in nx_graph.nodes
        if nx_graph.nodes[n].get("start", "")
        and not nx_graph.nodes[n].get("finished", False)
        and float(nx_graph.nodes[n].get("remains", 0)) == 0
        and float(nx_graph.nodes[n].get("days", 0)) > 0
    ]
    if zero_remains_tasks:
        st.warning(
            f"⚠️ 着手済みで残日数が 0 のタスクがあります（CC計算上、所要 0 日として扱われます）: "
            f"**{'、'.join(zero_remains_tasks)}**"
        )

    # 分析で使うチェーン（CC があればそちらを優先）
    active_chain = cc if cc else cp
    active_length = cc_length if cc else cp_length

    # URLパラメータに基づく初期表示タブの切り替え設定
    view_mode = st.query_params.get("view", "")
    sub_titles = ["🌡️ フィーバーチャート", "📅 ガントチャート", "📋 優先度"]
    if view_mode == "gantt":
        # ガントチャートをデフォルトにするため先頭に移動
        sub_titles = ["📅 ガントチャート", "🌡️ フィーバーチャート", "📋 優先度"]

    sub_tabs = st.tabs(sub_titles)
    tab_fever = sub_tabs[sub_titles.index("🌡️ フィーバーチャート")]
    tab_gantt = sub_tabs[sub_titles.index("📅 ガントチャート")]
    tab_priority = sub_tabs[sub_titles.index("📋 優先度")]

    with tab_gantt:
        _render_gantt_tab(
            project=requirement_data.get("project", {}),
            active_chain=active_chain,
            nx_graph=nx_graph,
            virtual_edges=virtual_edges,
            config_data=config_data,
        )

    with tab_fever:
        _render_fever_tab(
            active_chain=active_chain,
            nx_graph=nx_graph,
            requirement_data=requirement_data,
            active_length=active_length,
            requirement_manager=requirement_manager,
            file_path=file_path,
        )

    with tab_priority:
        _render_priority_tab(
            active_chain=active_chain,
            nx_graph=nx_graph,
        )


with edit_column:
    render_edit_panel()

# 左カラムに「ネットワーク図」と「CCPM分析」のタブを配置
with diagram_column:
    view_mode = st.query_params.get("view", "")
    main_titles = ["🗗️ ネットワーク図", "📊 CCPM 分析"]
    if view_mode in ["gantt", "fever"]:
        main_titles = ["📊 CCPM 分析", "🗗️ ネットワーク図"]
        
    main_tabs = st.tabs(main_titles)
    tab_diagram = main_tabs[main_titles.index("🗗️ ネットワーク図")]
    tab_analysis = main_tabs[main_titles.index("📊 CCPM 分析")]

    with tab_diagram:
        plantuml_code = draw_diagram_column(
            tab_diagram, context=diagram_context, options=diagram_options,
        )
    with tab_analysis:
        render_ccpm_analysis()

st.session_state.graph_data = graph_data
