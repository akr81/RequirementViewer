from typing import Dict, List
import uuid


class RequirementManager:
    def __init__(self, requirement_data: List[Dict]):
        self.requirements = requirement_data

    def add(self, requirement: Dict) -> str:
        """Add new requirement to requirements.

        Args:
            requirement (Dict): New requirement to add

        Returns:
            str: Unique ID of added requirement
        """
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

    def remove(self, unique_id: str):
        """Remove requirement with specified unique_id.

        Args:
            unique_id (str): Unique ID of requirement to remove
        """
        # 指定されたunique_idの要求を削除する
        self.requirements.remove(
            [d for d in self.requirements if d["unique_id"] == unique_id][0]
        )

        # 指定されたunique_idをもつ関連を削除する
        for requirement in self.requirements:
            requirement["relations"] = [
                rel
                for rel in requirement["relations"]
                if rel["destination"] != unique_id
            ]
