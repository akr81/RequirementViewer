from typing import List, Dict
import networkx as nx
import copy


class RequirementGraph:
    def __init__(self, entities: List[Dict], title):
        self.entities = entities

        # 要求図全体のグラフ
        self.graph = nx.DiGraph()

        # フィルタリングされたサブグラフ
        self.subgraph = nx.DiGraph()

        # グラフの構築
        if title == "Requirement Diagram Viewer":
            self._convert_requirements()
        elif title == "Strategy and Tactics Tree Viewer":
            self._convert_strategy_and_tactics()
        elif title == "Current Reality Tree Viewer":
            self._convert_current_reality()
        elif title == "Process Flow Diagram Viewer":
            self._convert_process_flow()
        elif title == "Evaporating Cloud Viewer":
            self._convert_evaporating_cloud()
        else:
            raise ValueError("Invalid title specified.")

    def _convert_evaporating_cloud(self):
        for entity in self.entities["nodes"]:
            entity.setdefault("color", "None")  # colorがない場合はNoneを設定
            self.graph.add_node(entity["unique_id"], **entity)

        for edge in self.entities["edges"]:
            edge.setdefault("type", "arrow")  # typeがない場合はarrowを設定
            self.graph.add_edge(edge["source"], edge["destination"], **edge)

    def _convert_strategy_and_tactics(self):
        for node in self.entities["nodes"]:
            self.graph.add_node(node["unique_id"], **node)

        for edge in self.entities["edges"]:
            edge.setdefault("color", "None")  # colorがない場合はNoneを設定
            self.graph.add_edge(edge["source"], edge["destination"], **edge)

    def _convert_process_flow(self):
        for node in self.entities["nodes"]:
            self.graph.add_node(node["unique_id"], **node)
        for edge in self.entities["edges"]:
            edge.setdefault("type", "arrow")
            if self.graph.nodes[edge["source"]]["type"] == "note":
                modified_edge = copy.deepcopy(edge)
                modified_edge["type"] = "flat_long"
                self.graph.add_edge(
                    modified_edge["source"],
                    modified_edge["destination"],
                    **modified_edge,
                )
            else:
                self.graph.add_edge(edge["source"], edge["destination"], **edge)

    def _convert_requirements(self):
        """Convert requirements to graph."""
        for node in self.entities["nodes"]:
            self.graph.add_node(node["unique_id"], **node)
        for edge in self.entities["edges"]:
            edge.setdefault("color", "None")  # colorがない場合はNoneを設定
            self.graph.add_edge(
                edge["source"],
                edge["destination"],
                **edge,  # edgeの情報をそのまま渡す
            )

    def _add_note_edge(self, entity, relation):
        """Add edge for note type entity.
        Note type entity is connected to destination with flat or flat_long edge.
        """
        if len(entity["relations"]) > 1:
            self.graph.add_edge(
                entity["unique_id"],
                relation["destination"],
                type="flat_long",
            )
        else:
            self.graph.add_edge(
                entity["unique_id"], relation["destination"], type="flat_long"
            )

    def _convert_current_reality(self):
        """Convert current reality tree to graph."""
        for node in self.entities["nodes"]:
            node.setdefault("color", "None")  # colorがない場合はNoneを設定
            self.graph.add_node(node["unique_id"], **node)
        for edge in self.entities["edges"]:
            edge.setdefault("type", "arrow")  # typeがない場合はarrowを設定
            self.graph.add_edge(edge["source"], edge["destination"], **edge)

    def extract_subgraph(
        self,
        target_node: str,
        upstream_distance: int,
        downstream_distance: int,
        detail: bool = True,
    ):
        """Extract subgraph from graph with target node.

        Args:
            target_node (str): Target node to extract subgraph
            upstream_distance (int): Distance of upstream nodes
            downstream_distance (int): Distance of downstream nodes

        """
        # Store graph itself as subgraph if target_node is None
        if target_node is None or target_node == "None":
            if not detail:
                # ノードの詳細情報がnoteの場合はreachable_nodesから除外する
                reachable_nodes = {
                    node
                    for node in self.graph.nodes()
                    if self.graph.nodes[node]["type"] != "note"
                }

                # これらのノードを含むサブグラフを作成
                self.subgraph = self.graph.subgraph(reachable_nodes).copy()
            else:
                self.subgraph = self.graph.copy()
            return

        reachable_upper_nodes = None
        reachable_lower_nodes = None
        reachable_nodes = None

        # Downstream
        lengths = nx.single_source_shortest_path_length(self.graph, target_node)
        reachable_lower_nodes = {
            node
            for node, length in lengths.items()
            if upstream_distance == -1 or length <= upstream_distance
        }

        # Upstream
        lengths_reverse = nx.single_source_shortest_path_length(
            self.graph.reverse(), target_node
        )
        reachable_upper_nodes = {
            node
            for node, length in lengths_reverse.items()
            if downstream_distance == -1 or length <= downstream_distance
        }
        reachable_nodes = reachable_upper_nodes.union(reachable_lower_nodes)

        if not detail:
            # ノードの詳細情報がnoteの場合はreachable_nodesから除外する
            reachable_nodes = {
                node
                for node in reachable_nodes
                if self.graph.nodes[node]["type"] != "note"
            }

        # これらのノードを含むサブグラフを作成
        self.subgraph = self.graph.subgraph(reachable_nodes).copy()
        return
