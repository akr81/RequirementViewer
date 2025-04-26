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

        from_unique_id_list = []
        for from_relation in from_relations:
            from_unique_id = from_relation["from"]
            if from_unique_id != "None":
                from_unique_id_list.append(from_unique_id)

        # 指定されたunique_idへの接続を追加・削除する
        for requirement in self.requirements:
            temp_unique_id = requirement["unique_id"]
            if temp_unique_id in from_unique_id_list:
                # 接続先にunique_idがなければ追加
                if unique_id not in [
                    rel["destination"] for rel in requirement["relations"]
                ]:
                    requirement["relations"].append({"destination": unique_id})
            else:
                # 接続先にunique_idがあれば削除
                if unique_id in [
                    rel["destination"] for rel in requirement["relations"]
                ]:
                    requirement["relations"].remove(
                        [
                            rel
                            for rel in requirement["relations"]
                            if rel["destination"] == unique_id
                        ][0]
                    )
