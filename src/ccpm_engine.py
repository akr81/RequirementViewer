"""CCPM (Critical Chain Project Management) エンジン。

CCPMPlanner_light.py のロジックを RequirementViewer 向けに整理したもの。
クリティカルパス算出、ガントチャート PlantUML 生成、フィーバーチャートデータ計算を提供する。
"""
import networkx as nx
from datetime import datetime
from typing import List, Dict, Tuple, Any, Optional

try:
    import workdays
except ImportError:
    workdays = None


# ---------------------------------------------------------------------------
# グラフ解析
# ---------------------------------------------------------------------------

def get_in_out_edge_list(graph: nx.DiGraph) -> Tuple[List[str], List[str]]:
    """入力端（in_degree==0）と終端（out_degree==0）のノードリストを返す。"""
    inputs = [n for n, d in graph.in_degree() if d == 0]
    outputs = [n for n, d in graph.out_degree() if d == 0]
    return inputs, outputs


def calculate_critical_path(
    graph: nx.DiGraph, inputs: List[str], outputs: List[str]
) -> Tuple[float, List[str]]:
    """全パスを探索し、最長パス（クリティカルパス）を返す。

    Args:
        graph: ノード属性に "days" を持つ有向グラフ
        inputs: 入力端ノードリスト
        outputs: 終端ノードリスト

    Returns:
        (クリティカルパス長, クリティカルパスのノードリスト)
    """
    critical_path: List[str] = []
    critical_path_length: float = 0

    for output in outputs:
        for inp in inputs:
            try:
                for path in nx.all_simple_paths(graph, inp, output):
                    length = sum(
                        graph.nodes[task].get("days", 0) for task in path
                    )
                    if length > critical_path_length:
                        critical_path_length = length
                        critical_path = path
            except nx.NetworkXError:
                continue

    return critical_path_length, critical_path


# ---------------------------------------------------------------------------
# クリティカルチェーン算出（リソース競合考慮）
# ---------------------------------------------------------------------------

def _compute_earliest_schedule(graph: nx.DiGraph) -> Dict[str, Tuple[float, float]]:
    """ASAP スケジューリングで各ノードの最早開始・最早終了時刻を計算する。

    Returns:
        {node_id: (earliest_start, earliest_finish)}
    """
    schedule: Dict[str, Tuple[float, float]] = {}
    # トポロジカル順序で処理（DAG前提）
    try:
        topo_order = list(nx.topological_sort(graph))
    except nx.NetworkXUnfeasible:
        return schedule

    for node in topo_order:
        days = graph.nodes[node].get("days", 0)
        predecessors = list(graph.predecessors(node))
        if not predecessors:
            es = 0.0
        else:
            es = max(schedule[p][1] for p in predecessors if p in schedule)
        schedule[node] = (es, es + days)

    return schedule


def _compute_remaining_path_length(
    graph: nx.DiGraph, node: str, memo: Dict[str, float]
) -> float:
    """ノードから終端までの最長残パス長を計算する（メモ化再帰）。"""
    if node in memo:
        return memo[node]
    days = graph.nodes[node].get("days", 0)
    successors = list(graph.successors(node))
    if not successors:
        memo[node] = days
        return days
    max_child = max(_compute_remaining_path_length(graph, s, memo) for s in successors)
    result = days + max_child
    memo[node] = result
    return result


def _detect_resource_conflicts(
    graph: nx.DiGraph,
    schedule: Dict[str, Tuple[float, float]],
) -> List[Tuple[str, str, str]]:
    """同一リソースで時間帯が重なるタスクペアを検出する。

    Returns:
        [(task_a, task_b, resource), ...] task_a は開始が早い方
    """
    # リソースごとにタスクをグルーピング
    resource_tasks: Dict[str, List[str]] = {}
    for node in graph.nodes:
        res = graph.nodes[node].get("resource", "")
        days = graph.nodes[node].get("days", 0)
        if not res or days <= 0:
            continue
        resource_tasks.setdefault(res, []).append(node)

    conflicts: List[Tuple[str, str, str]] = []
    for resource, tasks in resource_tasks.items():
        if len(tasks) < 2:
            continue
        # 全ペアで重なりをチェック
        for i in range(len(tasks)):
            for j in range(i + 1, len(tasks)):
                a, b = tasks[i], tasks[j]
                if a not in schedule or b not in schedule:
                    continue
                a_start, a_end = schedule[a]
                b_start, b_end = schedule[b]
                # 時間帯が重なるか判定 (days > 0 のタスクのみ)
                if a_start < b_end and b_start < a_end:
                    # 既に依存関係があるペアはスキップ
                    if nx.has_path(graph, a, b) or nx.has_path(graph, b, a):
                        continue
                    # 開始が早い方を先にする
                    if a_start <= b_start:
                        conflicts.append((a, b, resource))
                    else:
                        conflicts.append((b, a, resource))

    return conflicts


def calculate_critical_chain(
    graph: nx.DiGraph,
) -> Tuple[float, List[str], List[Tuple[str, str, str]]]:
    """リソース競合を考慮したクリティカルチェーンを算出する。

    ゴールドラット流ヒューリスティック:
    1. ASAP スケジューリングで最早開始時刻を算出
    2. リソース競合を検出
    3. 残路長が長い方を優先し、短い方を遅らせる仮想エッジを追加
    4. 競合がなくなるまで繰り返し

    Args:
        graph: ノード属性に "days", "resource" を持つ有向グラフ

    Returns:
        (チェーン長, チェーンのノードリスト, 追加された仮想エッジ[(src, dst, resource)])
    """
    # 作業用にグラフをコピー（仮想エッジを追加するため）
    work_graph = graph.copy()
    virtual_edges: List[Tuple[str, str, str]] = []

    max_iterations = 50  # 無限ループ防止
    for _ in range(max_iterations):
        schedule = _compute_earliest_schedule(work_graph)
        if not schedule:
            break

        conflicts = _detect_resource_conflicts(work_graph, schedule)
        if not conflicts:
            break  # 競合がなくなったら終了

        # 最も影響の大きい競合を1つ解消
        # （残パス長が長い方を優先、短い方を遅らせる）
        memo: Dict[str, float] = {}
        best_conflict = None
        best_priority_diff = -1

        for task_a, task_b, resource in conflicts:
            rem_a = _compute_remaining_path_length(work_graph, task_a, memo)
            rem_b = _compute_remaining_path_length(work_graph, task_b, memo)
            diff = abs(rem_a - rem_b)
            if diff > best_priority_diff:
                best_priority_diff = diff
                # 残パス長が長い方を先に実行、短い方を遅らせる
                if rem_a >= rem_b:
                    best_conflict = (task_a, task_b, resource)
                else:
                    best_conflict = (task_b, task_a, resource)

        if best_conflict is None:
            break

        first, second, resource = best_conflict
        # 仮想エッジを追加（first が先に実行 → second は first 完了後に開始）
        if not work_graph.has_edge(first, second):
            work_graph.add_edge(first, second, virtual=True)
            virtual_edges.append((first, second, resource))

    # 最終的なクリティカルチェーンを算出
    inputs, outputs = get_in_out_edge_list(work_graph)
    cc_length, cc_path = calculate_critical_path(work_graph, inputs, outputs)

    return cc_length, cc_path, virtual_edges


# ---------------------------------------------------------------------------
# ガントチャート PlantUML 生成
# ---------------------------------------------------------------------------

def _make_project_header(project: Dict[str, str]) -> List[str]:
    """PlantUML ガントチャートのプロジェクト設定部を作成する。"""
    lines: List[str] = []
    today = project.get("today", "")
    if today:
        lines.append(f"today is {today} and is colored in #AAF")
    start = project.get("start", "")
    if start:
        lines.append(f"Project starts {start}")
    lines.append("saturday are closed")
    lines.append("sunday are closed")
    for holiday in project.get("holidays", []):
        lines.append(f"{holiday} are closed")
    end = project.get("end", "")
    if end:
        lines.append(f"[Deadline] happens at {end}")
    return lines


def _make_story_bars(
    graph: nx.DiGraph,
    critical_path: List[str],
    project: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """各ノードのバー文字列を作成する。"""
    lines: List[str] = []
    for node_id in graph.nodes:
        attrs = graph.nodes[node_id]
        days = attrs.get("days", 0)
        if days <= 0:
            continue  # 成果物など日数0のノードはスキップ

        start = attrs.get("start", "")
        finished = attrs.get("finished", False)

        if start and project:
            # 着手済み: 残日数ベースで終了日を推定
            remains = attrs.get("remains", 0)
            if remains > 0 and workdays and not finished:
                end_date = _estimate_end_date(project, start, remains)
                bar = f"[{node_id}] starts {start} and ends {end_date}"
            elif finished and attrs.get("end", ""):
                bar = f"[{node_id}] starts {start} and ends {attrs['end']}"
            else:
                bar = f"[{node_id}] lasts {days} days"
        else:
            bar = f"[{node_id}] lasts {days} days"

        # 完了タスクの色
        if finished:
            bar += " and is colored in lightgray"
        elif node_id in critical_path:
            bar += " and is colored in pink"

        lines.append(bar)
    return lines


def _make_dependency_arrows(
    graph: nx.DiGraph, critical_path: List[str]
) -> List[str]:
    """エッジの依存関係文字列を作成する（クリティカルパス優先）。"""
    arrows: List[str] = []

    # クリティカルパスの依存を先に定義
    for i in range(len(critical_path) - 1):
        src_days = graph.nodes[critical_path[i]].get("days", 0)
        dst_days = graph.nodes[critical_path[i + 1]].get("days", 0)
        if src_days > 0 and dst_days > 0:
            arrows.append(f"[{critical_path[i]}] -> [{critical_path[i + 1]}]")

    # その他の依存
    for src, dst in graph.edges:
        src_days = graph.nodes[src].get("days", 0)
        dst_days = graph.nodes[dst].get("days", 0)
        if src_days > 0 and dst_days > 0:
            arrow = f"[{src}] -> [{dst}]"
            if arrow not in arrows:
                arrows.append(arrow)

    return arrows


def _estimate_end_date(
    project: Dict[str, Any], start_date: str, remain_day: int
) -> str:
    """稼働日ベースで完了予定日を計算する。"""
    if not workdays:
        return ""
    holidays_str = project.get("holidays", [])
    dt_holidays = [datetime.strptime(h, "%Y/%m/%d") for h in holidays_str]
    today_str = project.get("today", "")
    if not today_str:
        return ""
    dt_today = datetime.strptime(today_str, "%Y/%m/%d")
    dt_start = datetime.strptime(start_date, "%Y/%m/%d")

    elapsed = workdays.networkdays(dt_start, dt_today, holidays=dt_holidays) - 1
    estimated = elapsed + remain_day
    dt_end = workdays.workday(dt_start, days=estimated, holidays=dt_holidays)
    return dt_end.date().strftime("%Y/%m/%d")


def make_gantt_puml(
    graph: nx.DiGraph,
    project: Dict[str, Any],
    critical_path: List[str],
) -> str:
    """グラフとプロジェクト設定からPlantUMLガントチャートコードを生成する。

    Returns:
        PlantUML ガントチャートコード文字列
    """
    lines: List[str] = ["@startgantt", ""]
    lines.extend(_make_project_header(project))
    lines.append("")
    lines.extend(_make_story_bars(graph, critical_path, project))
    lines.append("")
    lines.extend(_make_dependency_arrows(graph, critical_path))
    lines.append("")
    lines.append("@endgantt")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# フィーバーチャート計算
# ---------------------------------------------------------------------------

def calculate_fever_data(
    graph: nx.DiGraph,
    project: Dict[str, Any],
    critical_path: List[str],
    critical_path_length: float,
) -> Dict[str, float]:
    """フィーバーチャート用のデータを計算する。

    Returns:
        {"progress": float, "buffer_used": float} (0-100%)
    """
    if not workdays or not critical_path or critical_path_length <= 0:
        return {"progress": 0.0, "buffer_used": 0.0}

    # クリティカルパスの完了状況
    finished_days = 0.0
    remain_days = 0.0
    for task_id in critical_path:
        attrs = graph.nodes[task_id]
        if attrs.get("finished", False):
            finished_days += attrs.get("days", 0)
        else:
            r = attrs.get("remains", 0)
            if r > 0:
                remain_days += r
            else:
                remain_days += attrs.get("days", 0)

    progress = (finished_days / critical_path_length) * 100 if critical_path_length > 0 else 0

    # バッファ消費率
    holidays_str = project.get("holidays", [])
    dt_holidays = [datetime.strptime(h, "%Y/%m/%d") for h in holidays_str]
    buffer_start = project.get("buffer_start", project.get("end", ""))
    end_str = project.get("end", "")
    today_str = project.get("today", "")

    if not buffer_start or not end_str or not today_str:
        return {"progress": progress, "buffer_used": 0.0}

    try:
        dt_buffer_start = datetime.strptime(buffer_start, "%Y/%m/%d")
        dt_end = datetime.strptime(end_str, "%Y/%m/%d")
        buffer_days = workdays.networkdays(
            dt_buffer_start, dt_end, holidays=dt_holidays
        )
        if buffer_days <= 0:
            return {"progress": progress, "buffer_used": 0.0}

        # 今日時点の完了予定日
        estimated_finish = _estimate_end_date(project, today_str, int(remain_days))
        if estimated_finish:
            dt_finish = datetime.strptime(estimated_finish, "%Y/%m/%d")
            remain_buffer = (
                workdays.networkdays(dt_finish, dt_end, holidays=dt_holidays) - 1
            )
            buffer_used = (1 - (remain_buffer / buffer_days)) * 100
        else:
            buffer_used = 0.0
    except Exception:
        buffer_used = 0.0

    return {"progress": progress, "buffer_used": buffer_used}


# ---------------------------------------------------------------------------
# 優先度テーブル
# ---------------------------------------------------------------------------

def calculate_priority_table(
    graph: nx.DiGraph,
    critical_path: List[str],
) -> List[Dict[str, Any]]:
    """タスクのバッファ消費に基づく優先度テーブルを計算する。

    Returns:
        タスク情報の辞書リスト (バッファ昇順)
    """
    if not critical_path:
        return []

    inputs, _ = get_in_out_edge_list(graph)
    final_task = critical_path[-1]

    # 未完了のCPタスクから残りのCP長を算出
    first_unfinished = None
    for t in critical_path:
        if not graph.nodes[t].get("finished", False):
            first_unfinished = t
            break
    if not first_unfinished:
        return []

    unfinished_cp_length = sum(
        graph.nodes[t].get("days", 0)
        for t in critical_path[critical_path.index(first_unfinished):]
    )

    # 全パスのタスク情報を収集
    all_info: Dict[str, Dict[str, Any]] = {}
    for inp in inputs:
        try:
            for path in nx.all_simple_paths(graph, inp, final_task):
                for task in path:
                    if graph.nodes[task].get("finished", False):
                        continue
                    remain_length = sum(
                        graph.nodes[t].get("days", 0)
                        for t in path[path.index(task):]
                    )
                    buffer = unfinished_cp_length - remain_length
                    # 最小バッファを保持
                    if task not in all_info or buffer < all_info[task]["buffer"]:
                        all_info[task] = {
                            "task": task,
                            "title": graph.nodes[task].get("title", task),
                            "days": graph.nodes[task].get("days", 0),
                            "resource": graph.nodes[task].get("resource", ""),
                            "total_remains": remain_length,
                            "cp_remains": unfinished_cp_length,
                            "buffer": buffer,
                        }
        except nx.NetworkXError:
            continue

    return sorted(all_info.values(), key=lambda x: x["buffer"])
