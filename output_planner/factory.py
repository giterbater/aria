from importlib import import_module
from typing import Any, Dict
from .interfaces import OutputPlannerProtocol

def build_output_planner(config: Dict[str, Any]) -> OutputPlannerProtocol:
    """
    Expected config shape:
    {
        "type": "rule_based" | "llm_based",
        "rule_based": {"module": "...", "class": "...", "args": {}},
        "llm_based": {"module": "...", "class": "...", "args": {}}
    }
    """
    planner_type = config.get("type", "rule_based")
    if planner_type == "rule_based":
        rc = config["rule_based"]
        cls = _load_class(rc["module"] + "." + rc["class"])
        return cls(**rc.get("args", {}))
    if planner_type == "llm_based":
        lc = config["llm_based"]
        cls = _load_class(lc["module"] + "." + lc["class"])
        return cls(**lc.get("args", {}))
    # default to rule_based
    rb = config.get("rule_based", {})
    if rb:
        cls = _load_class(rb["module"] + "." + rb["class"])
        return cls(**rb.get("args", {}))
    # fallback to a simple default (should not happen)
    raise ValueError("Invalid output_planner config")

def _load_class(path: str):
    module_path, class_name = path.rsplit(".", 1)
    mod = import_module(module_path)
    return getattr(mod, class_name)