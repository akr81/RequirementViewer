import uuid
from typing import Dict, List
from src.constants import AppName, NodeType, Color


def get_crt_default_entity() -> Dict:
    """Get default entity data.

    Returns:
        entity_types: Entity data list
    """
    return {
        "id": "",
        "color": Color.NONE,
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
        "type": NodeType.DELIVERABLE,
        "id": "",
        "color": Color.NONE,
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
        "color": Color.NONE,
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
    AppName.CURRENT_REALITY: get_crt_default_entity,
    AppName.EVAPORATING_CLOUD: get_ec_default_entity,
    AppName.PROCESS_FLOW: get_pfd_default_entity,
    AppName.REQUIREMENT: get_req_default_entity,
    AppName.STRATEGY_TACTICS: get_st_default_entity,
}
