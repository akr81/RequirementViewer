from typing import Dict, List


class RequirementManager:
    def __init__(self, requirement_data: List[Dict]):
        self.requirements = requirement_data
    
    def update_edge(self, source: str, destination: str, defaults: dict = None):
        """(link_mode専用) 接続を更新（追加・削除）する
        
        Args:
            source (str): 接続元エンティティのユニークID
            destination (str): 接続先エンティティのユニークID
            defaults (dict): デフォルトの接続属性
        """
        existing_edge = [e for e in self.requirements["edges"] if e["source"] == source and e["destination"] == destination]
        if existing_edge:
            # 該当接続を除外（pop+ループはインデックスずれのバグがあるため内包表記で除外）
            self.requirements["edges"] = [e for e in self.requirements["edges"] if not (e["source"] == source and e["destination"] == destination)]
        else:
            new_edge = defaults.copy()
            new_edge["source"] = source
            new_edge["destination"] = destination
            self.requirements["edges"].append(new_edge)


    def add(self, requirement: Dict, tmp_edges: List, new_edges: List) -> str:
        """新しい要求を requirements に追加する。

        Args:
            requirement (Dict): 追加する新しい要求データ
            tmp_edges (List): 無効な（削除された）ものを含む一時的な接続のリスト
            new_edges (List): 新たに追加する接続のリスト

        Returns:
            str: 追加された要求のユニークID
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
        """指定された unique_id の要求を削除する。

        Args:
            unique_id (str): 削除する要求のユニークID
            remove_relations (bool): 依存する関連も削除するかどうか
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
        """指定された unique_id の要求を更新する。

        Args:
            selected_unique_id (str): 更新対象の要求のユニークID
            requirement (Dict): 更新する要求データ
            tmp_edges (List): 無効な（削除された）ものを含む一時的な接続のリスト
            new_edges (List): 新規追加接続のリスト
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
