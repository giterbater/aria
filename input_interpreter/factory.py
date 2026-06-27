from importlib import import_module
from typing import Any, Dict
from .interfaces import InputInterpreterProtocol

def build_input_interpreter(config: Dict[str, Any]) -> InputInterpreterProtocol:
    """
    Expected config shape:
    {
        "type": "hybrid" | "rule_based" | "llm_based",
        "rule_based": {"module": "...", "class": "...", "args": {}},
        "llm_based": {"module": "...", "class": "...", "args": {}},
        "confidence_threshold": 0.85   # only used for hybrid
    }
    """
    interp_type = config.get("type", "hybrid")
    if interp_type == "rule_based":
        rc = config["rule_based"]
        cls = _load_class(rc["module"] + "." + rc["class"])
        return cls(**rc.get("args", {}))
    if interp_type == "llm_based":
        lc = config["llm_based"]
        cls = _load_class(lc["module"] + "." + lc["class"])
        return cls(**lc.get("args", {}))
    # hybrid (default)
    rc = config["rule_based"]
    lc = config["llm_based"]
    rule_cls = _load_class(rc["module"] + "." + rc["class"])
    llm_cls = _load_class(lc["module"] + "." + lc["class"])
    rule_inst = rule_cls(**rc.get("args", {}))
    llm_inst = llm_cls(**lc.get("args", {}))
    threshold = config.get("confidence_threshold", 0.85)
    return HybridInputInterpreter(rule_inst, llm_inst, threshold)

def _load_class(path: str):
    module_path, class_name = path.rsplit(".", 1)
    mod = import_module(module_path)
    return getattr(mod, class_name)