"""CCPM (Critical Chain Project Management) エンジン。

CCPMPlanner_light.py のロジックを RequirementViewer 向けに整理したもの。
クリティカルパス算出、ガントチャート PlantUML 生成、フィーバーチャートデータ計算を提供する。
"""
import networkx as nx
import math
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


def _get_effective_days(graph: nx.DiGraph, node: str) -> float:
    """ノードの実質的な残日数を返す。
    - 完了済み: 0.0
    - 着手済み（開始日あり）: remains
    - 未着手: days (見積もり日数)
    """
    if graph.nodes[node].get("finished", False):
        return 0.0
    if graph.nodes[node].get("start", ""):
        return float(graph.nodes[node].get("remains", 0.0))
    return float(graph.nodes[node].get("days", 0.0))


def calculate_critical_path(
    graph: nx.DiGraph, inputs: List[str], outputs: List[str]
) -> Tuple[float, List[str]]:
    """動的計画法 (DP) を用いて O(V+E) で最長パス（クリティカルパス）を返す。

    Args:
        graph: ノード属性に "days" を持つ有向グラフ
        inputs: 入力端ノードリスト
        outputs: 終端ノードリスト

    Returns:
        (クリティカルパス長, クリティカルパスのノードリスト)
    """
    if not graph.nodes:
        return 0.0, []

    # トポロジカルソート（CCPMはDAG前提）
    try:
        topo_order = list(nx.topological_sort(graph))
    except nx.NetworkXUnfeasible:
        # 閉路がある場合は空を返す
        return 0.0, []

    # dist[node] = そのノードの終了時点での最長距離（入力からの距離 + 自身の日数）
    # pred[node] = 最長パスを構成するための親ノード
    dist: Dict[str, float] = {}
    pred: Dict[str, Optional[str]] = {}

    for node in topo_order:
        days = _get_effective_days(graph, node)
        dist[node] = days  # 親がない入端の場合
        pred[node] = None
        
        # 親ノードの終了距離(dist)が最も大きいものを選ぶ
        predecessors = list(graph.predecessors(node))
        if predecessors:
            max_p = None
            max_d = -1.0
            for p in predecessors:
                if p in dist and dist[p] > max_d:
                    max_d = dist[p]
                    max_p = p
            if max_p is not None:
                dist[node] = dist[max_p] + days
                pred[node] = max_p

    # outputs の中で最大の dist を持つノードを見つける
    target_outputs = outputs if outputs else list(graph.nodes)
    max_out_node = None
    max_out_dist = -1.0
    for out in target_outputs:
        if out in dist and dist[out] > max_out_dist:
            max_out_dist = dist[out]
            max_out_node = out

    if max_out_node is None:
        return 0.0, []

    # 経路の復元（後ろから辿って反転）
    critical_path = []
    curr = max_out_node
    while curr is not None:
        critical_path.append(curr)
        curr = pred.get(curr)
    
    critical_path.reverse()
    return max_out_dist, critical_path


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
        days = _get_effective_days(graph, node)
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
    days = _get_effective_days(graph, node)
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
    max_concurrency: int = 0
) -> List[Tuple[str, str, str]]:
    """同一リソースで時間帯が重なるタスクペア、または同時実行上限を超えるタスクペアを検出する。

    Returns:
        [(task_a, task_b, resource), ...] task_a は開始が早い方
    """
    # リソースごとにタスクをグルーピング
    resource_tasks: Dict[str, List[str]] = {}
    for node in graph.nodes:
        if graph.nodes[node].get("finished", False):
            continue
        res = graph.nodes[node].get("resource", "")
        days = _get_effective_days(graph, node)
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

    # 2. 全体での同時実行上限（無名リソース）の競合チェック
    if max_concurrency > 0:
        events = []
        for node, (start, end) in schedule.items():
            if graph.nodes[node].get("finished", False):
                continue
            node_type = graph.nodes[node].get("type", "")
            if _get_effective_days(graph, node) > 0 and node_type != "deliverable":
                events.append((start, "start", node))
                events.append((end, "end", node))
        
        # 時間順でソート（同じ時刻なら終了 'end' を先に処理して重なりと判定させない）
        events.sort(key=lambda x: (x[0], 0 if x[1] == "end" else 1))
        
        active_tasks = set()
        for t, evt_type, node in events:
            if evt_type == "start":
                active_tasks.add(node)
                if len(active_tasks) > max_concurrency:
                    # 同時実行数の上限を超えた場合、走っているタスクの中から依存関係のない2つを選んで
                    # 疑似的な競合ペアとして（短い方を遅らせるべく）追加する
                    import itertools
                    conflict_found = False
                    for a, b in itertools.combinations(list(active_tasks), 2):
                        if nx.has_path(graph, a, b) or nx.has_path(graph, b, a):
                            continue
                        
                        a_start = schedule[a][0]
                        b_start = schedule[b][0]
                        if a_start <= b_start:
                            pair = (a, b, "ConcurrencyLimit")
                        else:
                            pair = (b, a, "ConcurrencyLimit")
                            
                        # 既存の明示的競合ペアなどと重複していなければ追加
                        already_exists = any((p[0] == pair[0] and p[1] == pair[1]) for p in conflicts)
                        if not already_exists:
                            conflicts.append(pair)
                            conflict_found = True
                            break # 1ループにつき1つの競合を解消させれば再スケジュールが走るので十分
                            
                    if conflict_found:
                        break # 一度競合が見つかれば、最初の競合を返すだけでループを回せる
            else:
                if node in active_tasks:
                    active_tasks.remove(node)

    return conflicts


def calculate_critical_chain(
    graph: nx.DiGraph,
    max_concurrency: int = 0
) -> Tuple[float, List[str], List[Tuple[str, str, str]]]:
    """リソース競合および同時実行上限を考慮したクリティカルチェーンを算出する。

    ゴールドラット流ヒューリスティック:
    1. ASAP スケジューリングで最早開始時刻を算出
    2. リソース名による競合、および同時実行タスク数上限の超過を検出
    3. 残路長が長い方を優先し、短い方を遅らせる仮想エッジを追加
    4. 競合がなくなるまで繰り返し

    Args:
        graph: ノード属性に "days", "resource" を持つ有向グラフ
        max_concurrency: 同時実行可能なタスク数の上限（0以下の場合は無制限）

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

        conflicts = _detect_resource_conflicts(work_graph, schedule, max_concurrency)
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

    # --- 仮想エッジの推移的簡約（冗長な迂回ルートの除去） ---
    try:
        tr_graph = nx.transitive_reduction(work_graph)
        reduced_virtual_edges = []
        for src, dst, res in virtual_edges:
            if tr_graph.has_edge(src, dst):
                reduced_virtual_edges.append((src, dst, res))
        virtual_edges = reduced_virtual_edges
    except Exception:
        pass  # 閉路などで推移的簡約が失敗した場合はそのまま

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
        start = attrs.get("start", "")
        finished = attrs.get("finished", False)
        node_type = attrs.get("type", "")
        
        # 描画対象の判定: メモやクラウドなどの図形はスキップする。
        # process や deliverable は日数が0でもマイルストーンとして描画し、依存関係を繋げる
        if node_type in ["note", "cloud"]:
            continue
        title = attrs.get("title", node_id)
        # title内に改行が含まれる可能性を考慮し空白に置換
        title = title.replace("\n", " ").replace("\r", "")

        head = f"[{title}] as [{node_id}]"

        if start and project:
            # 着手済み: 残日数ベースで終了日を推定
            remains = attrs.get("remains", 0)
            if remains > 0 and workdays and not finished:
                end_date = _estimate_end_date(project, start, remains)
                bar = f"{head} starts {start} and ends {end_date}"
            elif finished and attrs.get("end", ""):
                bar = f"{head} starts {start} and ends {attrs['end']}"
            else:
                bar = f"{head} lasts {math.ceil(float(days))} days"
        else:
            bar = f"{head} lasts {math.ceil(float(days))} days"

        # 完了タスクの色
        if finished:
            bar += " and is colored in lightgray"
        elif node_id in critical_path:
            bar += " and is colored in pink"
        elif node_type == "deliverable":
            # 成果物で日数を持つものはフィードバッファとして青色で表示
            bar += " and is colored in lightblue"

        lines.append(bar)
        
        # ガントバーをクリックした際に、右側の編集パネル（selectedパラメータ）を連動させるためのリンク
        lines.append(f"[{node_id}] links to [[?selected={node_id}&view=gantt]]")
        
    return lines


def _make_dependency_arrows(
    graph: nx.DiGraph, critical_path: List[str], virtual_edges: Optional[List[Tuple[str, str, str]]] = None
) -> List[str]:
    """エッジの依存関係文字列を作成する（クリティカルパス優先）。"""
    arrows: List[str] = []

    # ガントチャートにバーとして描画される対象のノード判定
    def _is_target(n_id):
        node_type = graph.nodes[n_id].get("type", "")
        return node_type not in ["note", "cloud"]

    # 仮想エッジを含めた描画順序計算用のグラフを作成
    render_graph = graph.copy()
    if virtual_edges:
        for src, dst, _ in virtual_edges:
            if not render_graph.has_edge(src, dst):
                render_graph.add_edge(src, dst, virtual=True)

    # 1. 各ノードの earliest_end を計算 (PlantUMLの複数合流バグ回避のため)
    # 複数先行タスクがある場合、最も遅く終わるタスクにのみ依存するようにフィルタする
    try:
        topo_nodes = list(nx.topological_sort(render_graph))
    except nx.NetworkXUnfeasible:
        # 閉路がある場合は諦めてそのままの順序等にする
        topo_nodes = list(render_graph.nodes)

    # トポロジカルソート順に生成してPlantUMLの1パスパースによる波及バグを回避する
    for node in topo_nodes:
        if not _is_target(node):
            continue
        
        preds = list(render_graph.predecessors(node))
        valid_preds = [p for p in preds if _is_target(p)]
        
        for p in valid_preds:
            arrow = f"[{p}] -> [{node}]"
            if arrow not in arrows:
                arrows.append(arrow)

    return arrows


def _estimate_end_date(
    project: Dict[str, Any], start_date: str, remain_day: int
) -> str:
    """稼働日ベースで完了予定日を計算する。

    CCPMでは着手済みタスクの完了見込みは「今日 + 残日数」で算出する。
    """
    if not workdays:
        return ""
    holidays_str = project.get("holidays", [])
    dt_holidays = [datetime.strptime(h, "%Y/%m/%d") for h in holidays_str]
    today_str = project.get("today", "")
    if not today_str:
        return ""
    dt_today = datetime.strptime(today_str, "%Y/%m/%d")

    # 今日から残日数分だけ先の稼働日を完了予定日とする
    dt_end = workdays.workday(dt_today, days=int(math.ceil(float(remain_day))), holidays=dt_holidays)
    return dt_end.date().strftime("%Y/%m/%d")


def _make_project_buffer_bar(project: Dict[str, Any]) -> List[str]:
    """ベースライン情報を元に、当初のプロジェクトバッファのバーを描画する。"""
    baseline = project.get("baseline", {})
    cc_length = baseline.get("cc_length", 0)
    total_buffer = baseline.get("total_buffer", 0)
    start_str = project.get("start", "")

    if not cc_length or not total_buffer or not start_str or not workdays:
        return []

    import math
    try:
        holidays_str = project.get("holidays", [])
        dt_holidays = [datetime.strptime(h, "%Y/%m/%d") for h in holidays_str]
        dt_start = datetime.strptime(start_str, "%Y/%m/%d")
        
        # プロジェクト開始日から数えて CC長(稼働日) 経過した次の日をバッファ開始日とする
        # workdays.workday(start, 1) は翌稼働日を返すため、cc_length を指定するとちょうどCC終了の次稼働日となる
        buffer_start_dt = workdays.workday(dt_start, days=int(math.ceil(cc_length)), holidays=dt_holidays)
        buffer_start_str = buffer_start_dt.date().strftime("%Y/%m/%d")

        lines = [
            f"[当初のプロジェクトバッファ] starts {buffer_start_str} and lasts {int(math.ceil(total_buffer))} days",
            "[当初のプロジェクトバッファ] is colored in lightgray"
        ]
        return lines
    except Exception:
        return []


def make_gantt_puml(
    graph: nx.DiGraph,
    project: Dict[str, Any],
    critical_path: List[str],
    virtual_edges: Optional[List[Tuple[str, str, str]]] = None,
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
    lines.extend(_make_dependency_arrows(graph, critical_path, virtual_edges))
    lines.append("")
    lines.extend(_make_project_buffer_bar(project))
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

    CCPM 標準のフィーバーチャート:
    - X軸: CC 完了率 (%) = 完了した CC タスクの見積り日数 / CC 全体の日数
    - Y軸: バッファ消費率 (%) = 消費バッファ / 全バッファ
      - 全バッファ = プロジェクト稼働日数 - CC 長
      - 消費バッファ = 経過稼働日 - 完了した CC タスクの見積り日数

    Returns:
        {
            "progress": float,
            "buffer_used": float,
            "remaining_cc_length": float,
            "consumed_buffer": float,
            "baseline_cc_length": float,
            "baseline_total_buffer": float
        }
    """
    if not critical_path or critical_path_length <= 0:
        return {
            "progress": 0.0,
            "buffer_used": 0.0,
            "remaining_cc_length": 0.0,
            "consumed_buffer": 0.0,
            "baseline_cc_length": 0.0,
            "baseline_total_buffer": 0.0
        }

    # ベースライン情報の取得
    baseline = project.get("baseline", {})
    baseline_cc_length = baseline.get("cc_length", critical_path_length)
    baseline_total_buffer = baseline.get("total_buffer", None)

    if baseline_cc_length <= 0:
        return {
            "progress": 0.0,
            "buffer_used": 0.0,
            "remaining_cc_length": 0.0,
            "consumed_buffer": 0.0,
            "baseline_cc_length": 0.0,
            "baseline_total_buffer": 0.0
        }

    # CC 残日数の計算と、完了したCCタスク日数の算出
    remaining_cc_length = 0.0
    finished_days_equivalent = 0.0
    for task_id in critical_path:
        attrs = graph.nodes[task_id]
        days = float(attrs.get("days", 0.0))
        remains = _get_effective_days(graph, task_id)
        
        remaining_cc_length += remains
        
        # 消化済み日数 = 見積り日数 - 現在の残日数
        # ただし、完了済みの場合は remains は 0 になるため全日数消化扱いとなる
        if days > remains:
            finished_days_equivalent += (days - remains)

    # CC完了率 = 消化済み日数 / ベースラインCC長
    progress = (finished_days_equivalent / baseline_cc_length) * 100
    # 進行率が100%を超えないようにクリップ
    progress = min(100.0, max(0.0, progress))

    # バッファ消費率
    start_str = project.get("start", "")
    end_str = project.get("end", "")
    today_str = project.get("today", "")
    if not start_str or not end_str or not today_str:
        return {
            "progress": progress,
            "buffer_used": 0.0,
            "remaining_cc_length": remaining_cc_length,
            "consumed_buffer": 0.0,
            "baseline_cc_length": baseline_cc_length,
            "baseline_total_buffer": baseline_total_buffer if baseline_total_buffer is not None else 0.0
        }

    try:
        holidays_str = project.get("holidays", [])
        dt_holidays = [datetime.strptime(h, "%Y/%m/%d") for h in holidays_str]
        dt_start = datetime.strptime(start_str, "%Y/%m/%d")
        dt_end = datetime.strptime(end_str, "%Y/%m/%d")
        dt_today = datetime.strptime(today_str, "%Y/%m/%d")

        # プロジェクト全体の稼働日数
        total_workdays = workdays.networkdays(
            dt_start, dt_end, holidays=dt_holidays
        ) if workdays else (dt_end - dt_start).days

        # ベースラインが未登録の場合は稼働日数から逆算
        if baseline_total_buffer is None:
            baseline_total_buffer = total_workdays - baseline_cc_length

        if baseline_total_buffer <= 0:
            # バッファなし（CC がプロジェクト期間以上）
            return {
                "progress": progress,
                "buffer_used": 100.0 if remaining_cc_length > 0 else 0.0,
                "remaining_cc_length": remaining_cc_length,
                "consumed_buffer": 0.0,
                "baseline_cc_length": baseline_cc_length,
                "baseline_total_buffer": 0.0
            }

        # 経過稼働日
        elapsed = workdays.networkdays(
            dt_start, dt_today, holidays=dt_holidays
        ) - 1 if workdays else (dt_today - dt_start).days
        elapsed = max(0, elapsed)

        # 現在見込まれる総所要日数 = (今日までの経過稼働総日数) + (未完了のCC残日数合計)
        # 本来予定通りなら projected_total_duration は baseline_cc_length と一致するが、
        # 進捗が遅れている（remainsが増えた等）ほど、その超過分がバッファを食いつぶしたと判定する
        projected_total_duration = elapsed + remaining_cc_length
        consumed_buffer = max(0.0, projected_total_duration - baseline_cc_length)

        buffer_used = (consumed_buffer / baseline_total_buffer) * 100
    except Exception:
        consumed_buffer = 0.0
        buffer_used = 0.0

    return {
        "progress": progress,
        "buffer_used": buffer_used,
        "remaining_cc_length": remaining_cc_length,
        "consumed_buffer": consumed_buffer,
        "baseline_cc_length": baseline_cc_length,
        "baseline_total_buffer": baseline_total_buffer
    }


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
        _get_effective_days(graph, t)
        for t in critical_path[critical_path.index(first_unfinished):]
    )

    # 全タスクの情報を収集（全経路探索を避けて DP で各ノードからゴールまでの最長距離を求める）
    memo: Dict[str, float] = {}
    all_info: Dict[str, Dict[str, Any]] = {}
    
    for task in graph.nodes:
        # メモやクラウドなどの図形はスキップ
        if graph.nodes[task].get("type", "") in ["note", "cloud"]:
            continue

        is_finished = graph.nodes[task].get("finished", False)
            
        # 該当タスクから終端までの最長残パス長（自身の日数を含む）
        remain_length = _compute_remaining_path_length(graph, task, memo)
        days = _get_effective_days(graph, task)
        buffer = unfinished_cp_length - remain_length
        
        # 状態（信号色）の判定 (1/3ルールに基づいた早期警告設定)
        if is_finished:
            status = "⚫ 完了"
        elif buffer <= (unfinished_cp_length * 0.1):
            # 残バッファが残りCCの10%以下（消費率90%超）で赤
            status = "🔴 警告"
        elif buffer <= (unfinished_cp_length * 0.3):
            # 残バッファが残りCCの30%以下（消費率70%超）で黄
            status = "🟡 注意"
        else:
            status = "🟢 余裕あり"
        
        all_info[task] = {
            "task": task,
            "status": status,
            "title": graph.nodes[task].get("title", task),
            "days": days,
            "resource": graph.nodes[task].get("resource", ""),
            "total_remains": remain_length,
            "cp_remains": unfinished_cp_length,
            "buffer": buffer,
            "is_finished": is_finished,
        }

    # 未完了が先、その中でバッファが少ない順 にソート
    return sorted(all_info.values(), key=lambda x: (x["is_finished"], x["buffer"]))
