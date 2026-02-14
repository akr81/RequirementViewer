from typing import Dict, List
import uuid


class RequirementManager:
    def __init__(self, requirement_data: List[Dict]):
        self.requirements = requirement_data
    
    def update_edge(self, source: str, destination: str, defaults: dict = None):
        """Update (add or remove) edge to requirements(only for link_mode)
        
        Args:
            source (str): Source node unique ID
            destination (str): Destination node unique ID
            defaults (dict): Default edge attributes
        """
        existing_edge = [e for e in self.requirements["edges"] if e["source"] == source and e["destination"] == destination]
        if existing_edge:
            # 該当エッジを除外（pop+ループはインデックスずれのバグがあるため内包表記で除外）
            self.requirements["edges"] = [e for e in self.requirements["edges"] if not (e["source"] == source and e["destination"] == destination)]
        else:
            new_edge = defaults.copy()
            new_edge["source"] = source
            new_edge["destination"] = destination
            self.requirements["edges"].append(new_edge)


    def add(self, requirement: Dict, tmp_edges: List, new_edges: List) -> str:
        """Add new requirement to requirements.

        Args:
            requirement (Dict): New requirement to add
            tmp_edges (List): List of temporary edges include invalid (removed)

        Returns:
            str: Unique ID of added requirement
        """
        requirement.setdefault("title", "")
        # 新しい要求を追加する
        self.requirements["nodes"].append(requirement)

        # 有効な新規edgeを追加する
        if new_edges is not None:
            for new_edge in new_edges:
                if (
                    new_edge["source"] != "None"
                    and new_edge["destination"] != "None"
                    and new_edge["source"] != None
                    and new_edge["destination"] != None
                ):
                    self.requirements["edges"].append(new_edge)

        # 選択状態とするためにユニークIDを返す
        return requirement["unique_id"]

    def remove(self, unique_id: str, remove_relations=True):
        """Remove requirement with specified unique_id.

        Args:
            unique_id (str): Unique ID of requirement to remove
        """
        # 指定されたunique_idの要求を削除する
        self.requirements["nodes"].remove(
            [d for d in self.requirements["nodes"] if d["unique_id"] == unique_id][0]
        )

        if remove_relations:
            # 指定されたunique_idをもつ関連を削除する
            self.requirements["edges"] = [
                edge
                for edge in self.requirements["edges"]
                if edge["source"] != unique_id and edge["destination"] != unique_id
            ]

    def update(
        self,
        selected_unique_id: str,
        requirement: Dict,
        tmp_edges: List,
        new_edges: List,
    ):
        """Update requirement with specified unique_id.

        Args:
            selected_unique_id (str): Unique ID of requirement to update
            requirement (Dict): Requirement to update
            tmp_edges (List): List of edges include invalid (removed)
        """
        requirement.setdefault("title", "")
        # 渡されるrequirementは、暫定的にユニークIDを振り直しているので、元のユニークIDで上書きする
        # edgeの上書き
        all_edges = None
        if tmp_edges is not None and new_edges is not None:
            all_edges = tmp_edges + new_edges
            if all_edges is not None:
                for tmp_edge in all_edges:
                    if tmp_edge["source"] == requirement["unique_id"]:
                        tmp_edge["source"] = selected_unique_id
                    if tmp_edge["destination"] == requirement["unique_id"]:
                        tmp_edge["destination"] = selected_unique_id

        # requirementの上書き
        requirement["unique_id"] = selected_unique_id

        # 指定されたunique_idの要求を削除する
        self.remove(requirement["unique_id"], remove_relations=False)
        # 要求を追加する
        self.requirements["nodes"].append(requirement)

        # 有効な接続関係(source, destinationがともに有効)を追加する
        if all_edges is not None:
            # 一旦すべての接続関係を削除
            self.requirements["edges"].clear()
            for edge in all_edges:
                if (
                    edge["source"] != "None"
                    and edge["destination"] != "None"
                    and edge["source"] != None
                    and edge["destination"] != None
                ):
                    self.requirements["edges"].append(edge)
