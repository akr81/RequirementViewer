import copy
import datetime
import os

import hjson
import pandas as pd
import streamlit as st

from src.ccpm_engine import calculate_fever_data_from_progress, calculate_working_days
from src.file_io import atomic_write_json, save_config, list_hjson_files
from src.page_setup import initialize_page

try:
    import plotly.graph_objects as go
except ImportError:
    go = None


APP_NAME = "Multi Project Fever Chart Viewer"
WORKING_DATA_KEY = "multi_project_fever_working_data"
WORKING_FILE_KEY = "multi_project_fever_working_file"


def _default_data() -> dict:
    return {
        "settings": {
            "display_last_n_points": 10,
            "default_buffer_percent": 30.0,
        },
        "common": {
            "holidays": [],
        },
        "projects": [],
    }


def _render_file_operations(app_name: str, file_path: str):
    """ファイル操作セクション（新規作成・既存ファイルを開く）を描画する。"""
    DATA_DIR = "data"
    os.makedirs(DATA_DIR, exist_ok=True)
    postfix = st.session_state.app_data[app_name].get("postfix", "multi_fever")

    file_col, create_col, open_col = st.columns([2, 1, 1])
    with file_col:
        st.caption(f"📁 データファイル: `{file_path}`")

    with create_col:
        with st.popover("📄 新規作成", use_container_width=True):
            new_file_name_key = f"{app_name}_new_file_name"
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
                            default_content = _default_data()
                            atomic_write_json(new_file_path, default_content)
                            data_file_key = st.session_state.app_data[app_name]["data"]
                            st.session_state.config_data[data_file_key] = new_file_path
                            save_config(st.session_state.config_data)
                            # working data をリセットして新ファイルを読み込む
                            if WORKING_DATA_KEY in st.session_state:
                                del st.session_state[WORKING_DATA_KEY]
                            st.success(f"'{new_file_path}' を作成しました。")
                            st.rerun()
                        except Exception as e:
                            st.error(f"ファイル作成に失敗しました: {e}")
                else:
                    st.error("有効なファイル名（.hjsonで終わる）を入力してください。")

    with open_col:
        with st.popover("📂 既存ファイルを開く", use_container_width=True):
            available_files = [
                f for f in list_hjson_files(DATA_DIR) if postfix in f
            ]
            file_options_map = {
                os.path.join(DATA_DIR, f): f for f in available_files
            }
            # 現在のファイルがdata外にある場合も選択肢に含める
            if file_path and file_path not in file_options_map:
                if os.path.isfile(file_path) and file_path.endswith(".hjson"):
                    file_options_map[file_path] = file_path

            if not file_options_map:
                st.info(f"'{DATA_DIR}' に利用可能な .hjson ファイルがありません。")
            else:
                options_paths = sorted(list(file_options_map.keys()))
                default_index = 0
                if file_path in options_paths:
                    default_index = options_paths.index(file_path)

                selected_file = st.selectbox(
                    "開くファイルを選択:",
                    options=options_paths,
                    format_func=lambda path: file_options_map[path],
                    index=default_index,
                    key=f"{app_name}_select_open_file",
                )
                if st.button("選択したファイルを開く", key=f"{app_name}_open_selected_file"):
                    if selected_file:
                        try:
                            data_file_key = st.session_state.app_data[app_name]["data"]
                            st.session_state.config_data[data_file_key] = selected_file
                            save_config(st.session_state.config_data)
                            # working data をリセットして新ファイルを読み込む
                            if WORKING_DATA_KEY in st.session_state:
                                del st.session_state[WORKING_DATA_KEY]
                            st.success(f"'{selected_file}' を開きます。")
                            st.rerun()
                        except Exception as e:
                            st.error(f"ファイル設定の更新に失敗しました: {e}")
                    else:
                        st.warning("開くファイルを選択してください。")


def _normalize_data(data: dict) -> dict:
    normalized = copy.deepcopy(data or {})
    normalized.setdefault("settings", {})
    normalized.setdefault("common", {})
    normalized.setdefault("projects", [])
    normalized["settings"].setdefault("display_last_n_points", 10)
    normalized["settings"].setdefault("default_buffer_percent", 30.0)
    normalized["common"].setdefault("holidays", [])

    for index, project in enumerate(normalized["projects"]):
        project.setdefault("id", f"project-{index + 1}")
        project.setdefault("name", project["id"])
        project.setdefault("start", "")
        project.setdefault("end", "")
        project.setdefault(
            "buffer_percent", normalized["settings"]["default_buffer_percent"]
        )
        project["progress"] = [
            {
                "date": str(point.get("date", "")),
                "progress": float(point.get("progress", 0) or 0),
                "memo": str(point.get("memo", "")),
            }
            for point in project.get("progress", [])
        ]
    return normalized


def _load_data(file_path: str) -> dict | None:
    """データファイルを読み込む。パースエラー時は None を返す。"""
    if not os.path.exists(file_path):
        return _default_data()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            loaded = hjson.load(f)
        return _normalize_data(loaded)
    except Exception:
        return None


def _save_data(file_path: str, data: dict, postfix: str):
    atomic_write_json(file_path, data)
    os.makedirs("back", exist_ok=True)
    backup_name = (
        datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{postfix}.hjson"
    )
    atomic_write_json(os.path.join("back", backup_name), data)


def _calculate_project_metrics(project: dict, common_holidays: list) -> tuple[float, float]:
    workdays = calculate_working_days(
        project.get("start", ""),
        project.get("end", ""),
        common_holidays,
    )
    buffer_percent = float(project.get("buffer_percent", 30.0) or 30.0)
    buffer_days = workdays * (buffer_percent / 100.0) if workdays > 0 else 0.0
    return round(workdays, 1), round(buffer_days, 1)


def _sorted_progress_points(project: dict, common_holidays: list) -> list:
    points = []
    for point in project.get("progress", []):
        fever = calculate_fever_data_from_progress(
            project,
            point.get("progress", 0),
            point.get("date", ""),
            common_holidays=common_holidays,
        )
        points.append(
            {
                "date": str(point.get("date", "")),
                "progress": float(point.get("progress", 0) or 0),
                "memo": str(point.get("memo", "")),
                "fever": fever,
            }
        )
    return sorted(points, key=lambda item: item["date"])


def _build_projects_df(data: dict, common_holidays: list) -> pd.DataFrame:
    rows = []
    for project in data["projects"]:
        workdays, buffer_days = _calculate_project_metrics(project, common_holidays)
        buffer_percent = float(project.get("buffer_percent", 30.0) or 30.0)
        rows.append(
            {
                "id": project.get("id", ""),
                "name": project.get("name", ""),
                "start": project.get("start", ""),
                "end": project.get("end", ""),
                "buffer_percent": buffer_percent,
                "workdays": workdays,
                "buffer_days": buffer_days,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "id",
            "name",
            "start",
            "end",
            "buffer_percent",
            "workdays",
            "buffer_days",
        ],
    )


def _build_progress_df(project: dict) -> pd.DataFrame:
    rows = [
        {
            "date": point.get("date", ""),
            "progress": float(point.get("progress", 0) or 0),
            "memo": point.get("memo", ""),
        }
        for point in project.get("progress", [])
    ]
    return pd.DataFrame(rows, columns=["date", "progress", "memo"])


def _parse_projects_from_editor(
    edited_df: pd.DataFrame,
    existing_projects: list,
    default_buffer_percent: float,
) -> list:
    progress_by_id = {
        str(project.get("id", "")): copy.deepcopy(project.get("progress", []))
        for project in existing_projects
    }
    parsed = []
    for index, row in edited_df.iterrows():
        project_id = str(row.get("id", "")).strip()
        name = str(row.get("name", "")).strip()
        if not project_id and not name:
            continue
        if not project_id:
            project_id = f"project-{index + 1}"
        parsed.append(
            {
                "id": project_id,
                "name": name or project_id,
                "start": str(row.get("start", "")).strip(),
                "end": str(row.get("end", "")).strip(),
                "buffer_percent": float(
                    row.get("buffer_percent", default_buffer_percent)
                    or default_buffer_percent
                ),
                "progress": progress_by_id.get(project_id, []),
            }
        )
    return parsed


def _apply_progress_edits(data: dict, progress_frames: dict):
    project_map = {project["id"]: project for project in data["projects"]}
    for project_id, edited_df in progress_frames.items():
        project = project_map.get(project_id)
        if not project:
            continue
        new_points = []
        for _, row in edited_df.iterrows():
            date_str = str(row.get("date", "")).strip()
            if not date_str or date_str == "nan":
                continue
            new_points.append(
                {
                    "date": date_str,
                    "progress": min(100.0, max(0.0, float(row.get("progress", 0) or 0))),
                    "memo": str(row.get("memo", "")).strip(),
                }
            )
        project["progress"] = sorted(new_points, key=lambda item: item["date"])


def _render_chart(projects: list, common_holidays: list, latest_n: int):
    if go is None:
        st.warning("plotly がインストールされていません。")
        return

    # ゾーン塗りつぶし（緑・黄・赤・グレー）と被らない配色
    _PROJECT_COLORS = [
        "#e6194b",  # 赤系
        "#3cb44b",  # 緑系
        "#4363d8",  # 青
        "#f58231",  # オレンジ
        "#911eb4",  # 紫
        "#42d4f4",  # シアン
        "#f032e6",  # マゼンタ
        "#e6beff",  # ラベンダー
        "#469990",  # ティール
        "#dcbeff",  # ライトパープル
        "#9a6324",  # ブラウン
        "#800000",  # マルーン
    ]

    # 事前にデータを収集し、max_buffer を計算する
    project_traces = []
    max_buffer = 100.0
    color_idx = 0
    for project in projects:
        points = _sorted_progress_points(project, common_holidays)
        if latest_n > 0:
            points = points[-latest_n:]
        if not points:
            continue
        max_buffer = max(
            max_buffer, max(point["fever"]["buffer_used"] for point in points)
        )
        project_traces.append((project, points, _PROJECT_COLORS[color_idx % len(_PROJECT_COLORS)]))
        color_idx += 1

    if not project_traces:
        st.info("表示できる進捗データがありません。")
        return

    y_range_max = int(max_buffer + 9) // 10 * 10 + 10 if max_buffer > 100 else 100

    # ゾーン塗りつぶしを先にすべて描画（tonexty が連続するように）
    fig = go.Figure()
    x = list(range(0, 101))
    y1 = [0.6 * xi + 10 for xi in x]
    y2 = [0.6 * xi + 25 for xi in x]

    # 緑ゾーン
    fig.add_trace(go.Scatter(
        x=x, y=y1, fill="tozeroy", fillcolor="rgba(144,238,144,0.3)",
        line=dict(color="green", width=1), showlegend=False, hoverinfo="skip",
    ))
    # 黄ゾーン
    fig.add_trace(go.Scatter(
        x=x, y=y2, fill="tonexty", fillcolor="rgba(255,255,150,0.3)",
        line=dict(color="orange", width=1), showlegend=False, hoverinfo="skip",
    ))
    # 赤ゾーン（100%まで）
    fig.add_trace(go.Scatter(
        x=x, y=[100] * len(x), fill="tonexty", fillcolor="rgba(255,160,160,0.3)",
        line=dict(width=0), showlegend=False, hoverinfo="skip",
    ))
    # 100%超えグレーゾーン（必要な場合、赤ゾーンの直後に連続して描画）
    if y_range_max > 100:
        fig.add_trace(go.Scatter(
            x=x, y=[y_range_max] * len(x), fill="tonexty", fillcolor="rgba(200,200,200,0.3)",
            line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))

    # プロジェクトのデータトレースを描画（ゾーンの上に重ねる）
    for project, points, color in project_traces:
        fig.add_trace(
            go.Scatter(
                x=[point["fever"]["progress"] for point in points],
                y=[point["fever"]["buffer_used"] for point in points],
                mode="lines+markers",
                name=project.get("name", project.get("id", "")),
                marker=dict(
                    size=[11] * (len(points) - 1) + [18],
                    color=color,
                ),
                line=dict(width=3, color=color),
                hovertext=[
                    (
                        f"{project.get('name', project.get('id', ''))}<br>"
                        f"{point['date']}<br>"
                        f"進捗率: {point['progress']:.1f}%<br>"
                        f"バッファ消費率: {point['fever']['buffer_used']:.1f}%<br>"
                        f"{point['memo']}"
                    )
                    for point in points
                ],
                hoverinfo="text",
            )
        )

    fig.update_layout(
        xaxis_title="進捗率 (%)",
        yaxis_title="バッファ消費率 (%)",
        xaxis=dict(range=[0, 100]),
        yaxis=dict(range=[0, y_range_max]),
        width=980,
        height=700,
        margin=dict(t=20, b=40, l=40, r=20),
    )
    st.plotly_chart(fig, width="stretch")


def _classify_zone(progress: float, buffer_used: float) -> str:
    """チャートのゾーン境界と同じ式でゾーンを判定する。"""
    green_yellow = 0.6 * progress + 10  # 緑/黄 境界
    yellow_red = 0.6 * progress + 25    # 黄/赤 境界
    if buffer_used >= yellow_red:
        return "🔴"
    elif buffer_used >= green_yellow:
        return "🟡"
    return "🟢"


def _render_summary(projects: list, common_holidays: list):
    today = datetime.date.today()
    rows = []
    for project in projects:
        points = _sorted_progress_points(project, common_holidays)
        if not points:
            continue
        latest = points[-1]
        progress = round(latest["fever"]["progress"], 1)
        buffer_used = round(latest["fever"]["buffer_used"], 1)
        total_workdays = calculate_working_days(
            project.get("start", ""), project.get("end", ""), common_holidays
        )
        remaining_days = max(
            0, round(calculate_working_days(today, project.get("end", ""), common_holidays), 0)
        )
        zone = _classify_zone(progress, buffer_used)
        rows.append(
            {
                "状態": zone,
                "プロジェクト": project.get("name", project.get("id", "")),
                "最終記録日": latest["date"],
                "進捗率(%)": progress,
                "バッファ消費率(%)": buffer_used,
                "残日数": int(remaining_days),
                "稼働日数": round(total_workdays, 1),
                "バッファ率(%)": round(
                    float(project.get("buffer_percent", 30.0) or 30.0), 1
                ),
            }
        )
    if rows:
        # ゾーン順（赤→黄→緑）、次にバッファ消費率降順でソート
        zone_order = {"🔴": 0, "🟡": 1, "🟢": 2}
        rows.sort(key=lambda r: (zone_order.get(r["状態"], 9), -r["バッファ消費率(%)"]))
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _add_project_to_working_data(
    data: dict,
    common_holidays: list,
    project_id: str,
    name: str,
    start_date,
    end_date,
    buffer_percent: float,
):
    new_id = project_id.strip()
    new_name = name.strip()
    if not new_id:
        st.warning("新規追加には ID が必要です。")
        return
    if any(project.get("id", "") == new_id for project in data["projects"]):
        st.warning("同じ ID のプロジェクトが既にあります。")
        return

    project = {
        "id": new_id,
        "name": new_name or new_id,
        "start": start_date.strftime("%Y/%m/%d") if start_date else "",
        "end": end_date.strftime("%Y/%m/%d") if end_date else "",
        "buffer_percent": float(buffer_percent),
        "progress": [],
    }
    data["projects"].append(project)
    st.session_state[WORKING_DATA_KEY] = _normalize_data(data)
    workdays, buffer_days = _calculate_project_metrics(project, common_holidays)
    st.toast(
        f"プロジェクトを追加しました。稼働日数 {workdays} 日 / バッファ日数 {buffer_days} 日"
    )
    st.rerun()


color_list, config_data, app_data = initialize_page(APP_NAME)
file_key = app_data[APP_NAME]["data"]
file_path = config_data[file_key]
postfix = app_data[APP_NAME]["postfix"]

loaded_data = _load_data(file_path)

st.session_state.app_name = APP_NAME
st.session_state.config_data = config_data

st.write("### フィーバーチャート")
_render_file_operations(APP_NAME, file_path)

# データ読み込みエラー時はファイル操作UIだけ表示して停止
if loaded_data is None:
    st.error(
        f"データファイル `{file_path}` の読み込みに失敗しました。\n\n"
        "このファイルはこの画面用のデータではない可能性があります。\n\n"
        "上の **📄 新規作成** または **📂 既存ファイルを開く** から別のデータを選択してください。"
    )
    st.stop()

if (
    WORKING_DATA_KEY not in st.session_state
    or st.session_state.get(WORKING_FILE_KEY) != file_path
):
    st.session_state[WORKING_DATA_KEY] = copy.deepcopy(loaded_data)
    st.session_state[WORKING_FILE_KEY] = file_path

data = copy.deepcopy(st.session_state[WORKING_DATA_KEY])

chart_col, side_col = st.columns([2, 1])

with side_col:
    default_buffer_percent = float(
        data["settings"].get("default_buffer_percent", 30.0) or 30.0
    )
    settings_col, action_col = st.columns([2, 1])
    with settings_col:
        latest_n = st.number_input(
            "直近から表示する点数",
            min_value=1,
            value=int(data["settings"].get("display_last_n_points", 10) or 10),
            step=1,
        )
    with action_col:
        st.write("")
        st.write("")
        save_requested = st.button("保存", width="stretch")

    with st.expander("祝日設定", expanded=False):
        holiday_text = st.text_area(
            "共通祝日 (YYYY/MM/DD を1行ずつ)",
            value="\n".join(data["common"].get("holidays", [])),
            height=140,
        )
    common_holidays = [line.strip() for line in holiday_text.splitlines() if line.strip()]

    with st.expander("新規プロジェクト追加", expanded=False):
        new_project_id = st.text_input("ID", key="multi_project_fever_new_id")
        new_project_name = st.text_input(
            "プロジェクト名", key="multi_project_fever_new_name"
        )
        new_start = st.date_input(
            "開始日", value=None, key="multi_project_fever_new_start"
        )
        new_end = st.date_input(
            "終了日", value=None, key="multi_project_fever_new_end"
        )
        new_buffer_percent = st.number_input(
            "バッファ率 (%)",
            min_value=0.0,
            max_value=95.0,
            value=default_buffer_percent,
            step=1.0,
            key="multi_project_fever_new_buffer",
        )
        preview_project = {
            "start": new_start.strftime("%Y/%m/%d") if new_start else "",
            "end": new_end.strftime("%Y/%m/%d") if new_end else "",
            "buffer_percent": float(new_buffer_percent),
        }
        preview_workdays, preview_buffer_days = _calculate_project_metrics(
            preview_project, common_holidays
        )
        metric_col1, metric_col2 = st.columns(2)
        with metric_col1:
            st.metric("稼働日数", preview_workdays)
        with metric_col2:
            st.metric("バッファ日数", preview_buffer_days)

        if st.button("一覧に追加", key="multi_project_fever_add_project", width="stretch"):
            _add_project_to_working_data(
                data,
                common_holidays,
                new_project_id,
                new_project_name,
                new_start,
                new_end,
                float(new_buffer_percent),
            )

    st.subheader("プロジェクト")
    projects_df = _build_projects_df(data, common_holidays)
    edited_projects_df = st.data_editor(
        projects_df,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "id": st.column_config.TextColumn("ID"),
            "name": st.column_config.TextColumn("プロジェクト名"),
            "start": st.column_config.TextColumn("開始日"),
            "end": st.column_config.TextColumn("終了日"),
            "buffer_percent": st.column_config.NumberColumn(
                "バッファ率(%)", min_value=0.0, max_value=95.0, step=1.0
            ),
            "workdays": st.column_config.NumberColumn("稼働日数", disabled=True),
            "buffer_days": st.column_config.NumberColumn("バッファ日数", disabled=True),
        },
        key="multi_project_fever_projects",
    )

    edited_projects = _parse_projects_from_editor(
        edited_projects_df, data["projects"], default_buffer_percent
    )
    edited_data = {
        "settings": {
            "display_last_n_points": int(latest_n),
            "default_buffer_percent": default_buffer_percent,
        },
        "common": {"holidays": common_holidays},
        "projects": edited_projects,
    }
    st.session_state[WORKING_DATA_KEY] = copy.deepcopy(edited_data)

    st.subheader("進捗データ")
    progress_frames = {}
    for project in edited_data["projects"]:
        # 最新の進捗ポイントを取得してラベルに表示
        sorted_pts = sorted(project.get("progress", []), key=lambda p: p.get("date", ""))
        latest_info = ""
        if sorted_pts:
            lp = sorted_pts[-1]
            latest_info = f" — 最新: {lp.get('date', '')} / {lp.get('progress', 0):.0f}%"
        expander_label = f"{project.get('name', project.get('id', ''))}{latest_info}"

        with st.expander(expander_label, expanded=False):
            # --- 簡易追加フォーム ---
            add_date_col, add_progress_col, add_memo_col, add_btn_col = st.columns([2, 2, 3, 1])
            add_key_prefix = f"mpf_add_{project['id']}"
            with add_date_col:
                add_date = st.date_input(
                    "日付",
                    value=datetime.date.today(),
                    key=f"{add_key_prefix}_date",
                )
            with add_progress_col:
                add_progress = st.number_input(
                    "進捗率 (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=1.0,
                    key=f"{add_key_prefix}_progress",
                )
            with add_memo_col:
                add_memo = st.text_input(
                    "メモ",
                    value="",
                    key=f"{add_key_prefix}_memo",
                )
            with add_btn_col:
                st.write("")
                st.write("")
                if st.button("追加", key=f"{add_key_prefix}_btn", width="stretch"):
                    date_str = add_date.strftime("%Y/%m/%d") if add_date else ""
                    if date_str:
                        # 同じ日付があれば上書き、なければ追加
                        existing_dates = [
                            p.get("date", "") for p in project.get("progress", [])
                        ]
                        if date_str in existing_dates:
                            for p in project["progress"]:
                                if p.get("date", "") == date_str:
                                    p["progress"] = min(100.0, max(0.0, float(add_progress)))
                                    p["memo"] = add_memo
                                    break
                        else:
                            project.setdefault("progress", []).append({
                                "date": date_str,
                                "progress": min(100.0, max(0.0, float(add_progress))),
                                "memo": add_memo,
                            })
                        project["progress"] = sorted(
                            project["progress"], key=lambda item: item["date"]
                        )
                        # working data を更新
                        st.session_state[WORKING_DATA_KEY] = copy.deepcopy(edited_data)
                        st.toast(f"{date_str} の進捗率 {add_progress:.0f}% を追加しました")
                        st.rerun()

            # --- 既存データの確認・編集 (ネスト折りたたみ) ---
            with st.expander(f"📋 記録データ ({len(project.get('progress', []))}件)", expanded=False):
                progress_frames[project["id"]] = st.data_editor(
                    _build_progress_df(project),
                    num_rows="dynamic",
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "date": st.column_config.TextColumn("日付"),
                        "progress": st.column_config.NumberColumn(
                            "進捗率(%)", min_value=0.0, max_value=100.0, step=1.0
                        ),
                        "memo": st.column_config.TextColumn("メモ"),
                    },
                    key=f"multi_project_fever_progress_{project['id']}",
                )

    _apply_progress_edits(edited_data, progress_frames)

    if save_requested:
        config_data["last_used_page"] = APP_NAME
        save_config(config_data)
        st.session_state.config_data = config_data
        _save_data(file_path, edited_data, postfix)
        st.session_state[WORKING_DATA_KEY] = copy.deepcopy(edited_data)
        st.success("データを保存しました。")
        st.rerun()

with chart_col:
    _render_chart(edited_data["projects"], common_holidays, int(latest_n))
    st.subheader("最新サマリー")
    _render_summary(edited_data["projects"], common_holidays)
