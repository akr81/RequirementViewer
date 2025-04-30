from typing import Dict, List
import uuid


class RequirementManager:
    def __init__(self, requirement_data: List[Dict]):
        self.requirements = requirement_data

    def add(self, requirement: Dict, update_unique_id=True) -> str:
        """Add new requirement to requirements.

        Args:
            requirement (Dict): New requirement to add

        Returns:
            str: Unique ID of added requirement
        """
        if update_unique_id:
            # ユニークIDを振り直す
            requirement["unique_id"] = f"{uuid.uuid4()}".replace("-", "")

        # 接続先が無効なrelationを削除する
        requirement["relations"] = [
            rel for rel in requirement["relations"] if rel["destination"] != "None"
        ]

        # 新しい要求を追加する
        self.requirements.append(requirement)

        # 選択状態とするためにユニークIDを返す
        return requirement["unique_id"]

    def remove(self, unique_id: str, remove_relations=True):
        """Remove requirement with specified unique_id.

        Args:
            unique_id (str): Unique ID of requirement to remove
        """
        # 指定されたunique_idの要求を削除する
        self.requirements.remove(
            [d for d in self.requirements if d["unique_id"] == unique_id][0]
        )

        if remove_relations:
            # 指定されたunique_idをもつ関連を削除する
            for requirement in self.requirements:
                requirement["relations"] = [
                    rel
                    for rel in requirement["relations"]
                    if rel["destination"] != unique_id
                ]

    def update(self, requirement: Dict):
        """Update requirement with specified unique_id.

        Args:
            requirement (Dict): Requirement to update
        """
        # 指定されたunique_idの要求を削除する
        self.remove(requirement["unique_id"], remove_relations=False)

        # 新しい要求を追加する
        self.add(requirement, update_unique_id=False)

    def update_reverse_relations(self, unique_id: str, from_relations: List):
        """Update reverse relations for requirement with specified unique_id.

        Args:
            unique_id (str): Unique ID of requirement to update
            from_relations (List): List of relations to update
        """
        if from_relations is None:
            return

        # 元のrequirementsで、unique_idに対して接続しているノードを取得
        connected_to_unique_id = []
        for requirement in self.requirements:
            for relation in requirement["relations"]:
                if relation["destination"] == unique_id:
                    connected_to_unique_id.append(requirement["unique_id"])

        # 操作結果から取得したunique_idに対する接続関係
        from_unique_id_list = []
        for from_relation in from_relations:
            from_unique_id = from_relation["from"]
            if from_unique_id != "None":
                from_unique_id_list.append(from_unique_id)

        print(connected_to_unique_id)
        print(from_unique_id_list)
        old_set = set(connected_to_unique_id)
        new_set = set(from_unique_id_list)

        added_list = list(new_set - old_set)
        removed_list = list(old_set - new_set)
        remains_list = list(old_set & new_set)

        # 新規追加のものはそのまま追加
        print(f"added: {added_list}")
        for added in added_list:
            # 接続先にunique_idがなければ追加
            for requirement in self.requirements:
                if requirement["unique_id"] == added:
                    requirement["relations"].append(
                        {
                            "destination": unique_id,
                            "and": [
                                d for d in from_relations if d.get("from") == added
                            ][0]["and"],
                        }
                    )

        # 削除されたものは接続を削除
        print(f"removed: {removed_list}")
        for removed in removed_list:
            # 接続先にunique_idがあれば削除
            for requirement in self.requirements:
                if requirement["unique_id"] == removed:
                    requirement["relations"] = [
                        rel
                        for rel in requirement["relations"]
                        if rel["destination"] != unique_id
                    ]

        # それ以外のものは"and"関係をアップデート(上書きする)
        print(f"remains: {remains_list}")
        for remains in remains_list:
            for requirement in self.requirements:
                if requirement["unique_id"] == remains:
                    for relation in requirement["relations"]:
                        relation.setdefault("and", "None")
                        if relation["destination"] == unique_id:
                            relation["and"] = [
                                d for d in from_relations if d.get("from") == remains
                            ][0]["and"]
