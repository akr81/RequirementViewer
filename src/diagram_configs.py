import uuid
from typing import Dict, List


def get_crt_default_entity() -> Dict:
    """Get default entity data.

    Returns:
        entity_types: Entity data list
    """
    return {
        "id": "",
        "color": "None",
        "unique_id": f"{uuid.uuid4()}".replace("-", ""),
    }


def get_ec_default_entity() -> Dict:
    """Get default entity data.

    Returns:
        entity_types: Entity data list
    """
    return {
        "id": "",
        "title": "",
        "unique_id": f"{uuid.uuid4()}".replace("-", ""),
    }


def get_pfd_default_entity() -> Dict:
    """Get default entity data.

    Returns:
        entity_types: Entity data list
    """
    return {
        "type": "deliverable",
        "id": "",
        "color": "None",
        "unique_id": f"{uuid.uuid4()}".replace("-", ""),
    }


def get_req_default_entity(entity_types: List[str]) -> Dict:
    """Get default entity data.

    Returns:
        entity_types: Entity data list
    """
    default_type = ""
    if len(entity_types) > 0:
        default_type = entity_types[0]
    return {
        "type": default_type,
        "id": "",
        "title": "",
        "text": "",
        "color": "None",
        "unique_id": f"{uuid.uuid4()}".replace("-", ""),
    }


def get_st_default_entity() -> Dict:
    """Get default entity data.

    Returns:
        entity_types: Entity data list
    """
    return {
        "id": "",
        "necessary_assumption": "",
        "strategy": "",
        "parallel_assumption": "",
        "tactics": "",
        "sufficient_assumption": "",
        "unique_id": f"{uuid.uuid4()}".replace("-", ""),
    }


DEFAULT_ENTITY_GETTERS = {
    "Current Reality Tree Viewer": get_crt_default_entity,
    "Evaporating Cloud Viewer": get_ec_default_entity,
    "Process Flow Diagram Viewer": get_pfd_default_entity,
    "Requirement Diagram Viewer": get_req_default_entity,
    "Strategy and Tactics Tree Viewer": get_st_default_entity,
}

# CRT向けのエンティティフィールド
CRT_ENTITY_FIELDS = [
    {
        "name": "type",
        "label": "タイプ",
        "widget": "selectbox",
        "options_key": "entity_list_for_crt",
    },  # entity_list_for_crt は別途定義または渡す
    {"name": "id", "label": "課題・状況", "widget": "text_area"},
    {
        "name": "color",
        "label": "色",
        "widget": "selectbox",
        "options_key": "color_list",
    },
]
