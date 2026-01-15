from __future__ import annotations
import hashlib
import json
import os
import re
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

_UTILS_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def print_nested_dict(data, indent_level=0):
    spaces = "  " * indent_level
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "image_url" and isinstance(value, dict) and len(value) == 1 and "url" in value:
                print(f"{spaces}{key}: {{url: {value['url']}}}")
            elif isinstance(value, (dict, list)):
                print(f"{spaces}{key}:")
                print_nested_dict(value, indent_level + 1)
            else:
                print(f"{spaces}{key}: {value}")
    elif isinstance(data, list):
        for index, item in enumerate(data):
            if isinstance(item, (dict, list)):
                print(f"{spaces}[{index}]:")
                print_nested_dict(item, indent_level + 1)
            else:
                print(f"{spaces}[{index}]: {item}")
    else:
        print(f"{spaces}{data}")


def utils_ok_payload(extra: Optional[Dict[str, Any]] = None) -> str:
    d: Dict[str, Any] = {"ok": True}
    if extra:
        d.update(extra)
    return json.dumps(d, ensure_ascii=True, separators=(",", ":"))


def utils_err_payload(error_type: str, message: str) -> str:
    return json.dumps({"ok": False, "error": {"type": error_type, "message": message}}, ensure_ascii=True, separators=(",", ":"))


def utils_parse_args(arg_str: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if arg_str is None:
        return {}, None
    if isinstance(arg_str, dict):
        return arg_str, None
    if not isinstance(arg_str, str):
        return None, utils_err_payload("invalid_args", "arguments must be a dict or JSON string")
    try:
        val = json.loads(arg_str) if arg_str else {}
    except json.JSONDecodeError as e:
        return None, utils_err_payload("invalid_json", f"arguments must be valid JSON: {e}")
    if not isinstance(val, dict):
        return None, utils_err_payload("invalid_args", "arguments JSON must parse to an object")
    return val, None


def utils_parse_box(box: Any) -> Tuple[Optional[Tuple[float, float, float, float]], Optional[str]]:
    def clamp(v: float) -> float:
        return max(0.0, min(1000.0, v))
    try:
        if isinstance(box, list) and len(box) == 2 and all(isinstance(v, (int, float)) for v in box):
            x, y = clamp(float(box[0])), clamp(float(box[1]))
            return (x, y, x, y), None
        if isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box):
            x1, y1, x2, y2 = map(float, box)
            x1, y1, x2, y2 = clamp(x1), clamp(y1), clamp(x2), clamp(y2)
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
            return (x1, y1, x2, y2), None
        if not isinstance(box, list) or len(box) != 2:
            return None, utils_err_payload("invalid_box", "box must be [x,y], [x1,y1,x2,y2], or [[x1,y1],[x2,y2]]")
        p1, p2 = box
        if not (isinstance(p1, list) and isinstance(p2, list)) or len(p1) != 2 or len(p2) != 2:
            return None, utils_err_payload("invalid_box", "box must be [x,y], [x1,y1,x2,y2], or [[x1,y1],[x2,y2]]")
        x1, y1 = float(p1[0]), float(p1[1])
        x2, y2 = float(p2[0]), float(p2[1])
        x1, y1, x2, y2 = clamp(x1), clamp(y1), clamp(x2), clamp(y2)
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        return (x1, y1, x2, y2), None
    except (TypeError, ValueError) as e:
        return None, utils_err_payload("invalid_box", f"coordinates must be numbers: {e}")


def utils_box_center(x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float]:
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def utils_strip_think(text: str) -> str:
    if not isinstance(text, str) or not text:
        return ""
    return _UTILS_THINK_RE.sub("", text).strip()


def utils_summarize_data_image_url(url: str) -> str:
    if not isinstance(url, str) or not url.startswith("data:image/"):
        return url
    comma = url.find(",")
    if comma == -1:
        return url
    header = url[: comma + 1]
    payload = url[comma + 1:]
    if len(payload) < 100:
        return url
    sha = hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"{header}[b64 sha={sha} len={len(payload)}]"


def utils_truncate_base64_images(obj: Any) -> Any:
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == "url" and isinstance(v, str):
                obj[k] = utils_summarize_data_image_url(v)
            else:
                utils_truncate_base64_images(v)
    elif isinstance(obj, list):
        for it in obj:
            utils_truncate_base64_images(it)
    return obj


def utils_post_json(payload: Dict[str, Any], endpoint: str, timeout: int) -> Dict[str, Any]:
    logged_payload = utils_truncate_base64_images(json.loads(json.dumps(payload)))
    logged_payload["tools"] = "[TOOLS DEFINITIONS TRUNCATED FOR READABILITY]"
    logged_payload["messages"][0]["content"] = "[SYSTEM PROMPT TRUNCATED FOR READABILITY]"
    logged_payload["messages"][1]["content"] = "[INITIAL USER TASK PROMPT TRUNCATED FOR READABILITY]"
    print("REQUEST TO MODEL:")
    print_nested_dict(logged_payload)
    print()
    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        response = json.loads(resp.read().decode("utf-8"))
    print("RESPONSE FROM MODEL:")
    print_nested_dict(response)
    print("\n")
    return response


def utils_get_env_str(name: str, default: str) -> str:
    v = os.environ.get(name, "").strip()
    return v if v else default


def utils_get_env_int(name: str, default: int) -> int:
    v = os.environ.get(name, "").strip()
    return default if not v else int(v)


def utils_get_env_float(name: str, default: float) -> float:
    v = os.environ.get(name, "").strip()
    return default if not v else float(v)
