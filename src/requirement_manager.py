from typing import Dict, List


class RequirementManager:
    def __init__(self, requirement_data: List[Dict]):
        self.requirements = requirement_data

    def remove(self, unique_id: str):
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
