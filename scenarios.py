from __future__ import annotations
import base64
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from winapi import winapi_capture_screenshot_png, winapi_norm_to_screen_px, winapi_move_mouse_to_pixel, winapi_click_mouse, winapi_type_text, winapi_press_key, winapi_scroll_down
from utils import utils_ok_payload, utils_err_payload, utils_parse_args, utils_parse_box, utils_box_center

SYSTEM_PROMPT = """
You are a desktop automation agent. You have no memory between turns.

YOUR SITUATION:
Each time you run, you are a fresh instance. You only know what you receive:
- A screenshot of the current desktop
- A 'plan' message from the previous version of yourself (if this is not the first turn)

YOUR GOAL:
Complete the user's original request exactly as stated.

HOW YOU OPERATE (every turn):
1. Look at the screenshot carefully
2. Read the plan from your previous self (if provided)
3. Check if the last action worked: does the screen match what the plan expected?
4. Take ONE action toward the goal (click, type, press key, scroll, or observe)
5. Call observe_screen with a detailed plan for your next self

ACTION RULES:
- Execute only ONE action per turn
- After every action, call observe_screen
- Use observe_screen as your only way to send information forward
- Do not write plans or reports as text responses

COORDINATES:
Use normalized values 0-1000 where (0,0) is top-left corner of screen.
Example: Middle of screen is approximately (500, 500).

ERROR DETECTION AND CORRECTION:
Your previous self may have made mistakes. This is normal.
- If screen does not match what plan said should happen: previous action failed
- When you detect failure: state it clearly in your new plan
- Propose a different approach: try another UI element, different search terms, etc.
- Trust the screenshot, not the plan's expectations

YOUR PLAN (what to write in observe_screen):
Your plan is a message to your future self. That version of you will have no memory except this message.
Give complete information (aim for 1500-2000 tokens):

**USER REQUEST**
[State exactly what the user asked for]

**WHAT HAPPENED SO FAR**
[List every action taken, turn by turn:
- Turn 1: Observed initial desktop, saw taskbar at bottom
- Turn 2: Clicked Windows search at position (185, 991) to find browser
- Turn 3: Typed "chrome" into search box
... continue for all turns]

**CURRENT SCREEN STATE**
[Describe what you see in detail:
- Which applications/windows are visible
- What UI elements are present (buttons, search boxes, menus)
- Any text content visible
- Where key elements are located (rough positions like "top-left", "center", "taskbar")]

**LAST ACTION RESULT**
[Assess what just happened:
- What action was taken: [describe]
- Expected result: [what should have appeared on screen]
- Actual result: [what you see on screen now]
- Judgment: [SUCCESS / FAILED / PARTIAL]
- If failed: why it failed and what to try instead]

**NEXT ACTION**
[Either:
A) Describe next action: "Click [element description] at position (x, y) because [reasoning]"
   OR
B) "GOAL ACHIEVED: [describe evidence on screen proving user's request is complete]"]

COMPLETION:
When you see evidence that the user's goal is achieved, write "GOAL ACHIEVED" in your next action section.
Your next self will verify. If they also see goal achieved, write plain text response: "Mission accomplished."

That plain text response is the ONLY time you respond without using observe_screen.
"""


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "observe_screen",
            "description": (
                "Captures a screenshot of the desktop and transmits your operational plan to the next agent instance. "
                "This is your ONLY way to pass information forward. "
                "The 'plan' parameter must contain complete information: user request, action history, current screen description, "
                "last action assessment, and next action recommendation. "
                "Aim for 1500-2000 tokens of detailed information. Your successor has no memory except what you provide here."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plan": {
                        "type": "string",
                        "description": (
                            "Your complete message to the next agent instance. Structure your plan with these sections: "
                            "USER REQUEST (exact user goal), "
                            "WHAT HAPPENED SO FAR (chronological action list), "
                            "CURRENT SCREEN STATE (detailed visual description), "
                            "LAST ACTION RESULT (success/failure analysis with evidence), "
                            "NEXT ACTION (recommended step with reasoning OR goal achievement declaration). "
                            "Provide thorough detail - target 1500-2000 tokens."
                        )
                    }
                },
                "required": ["plan"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click_element",
            "description": (
                "Executes a mouse click at specified coordinates. "
                "Use normalized coordinate system (0-1000, where 0,0 is top-left). "
                "Provide coordinates as box=[x,y] for a point click (recommended), "
                "or box=[x1,y1,x2,y2] for bounding box (center will be clicked). "
                "After clicking, always call observe_screen to verify result."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Brief description of target element (for logging purposes)"
                    },
                    "box": {
                        "description": "Click coordinates in 0-1000 normalized system. Format: [x,y] or [x1,y1,x2,y2]",
                        "anyOf": [
                            {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 2,
                                "maxItems": 2
                            },
                            {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 4,
                                "maxItems": 4
                            },
                            {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 2,
                                    "maxItems": 2
                                },
                                "minItems": 2,
                                "maxItems": 2
                            }
                        ]
                    }
                },
                "required": ["label", "box"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": (
                "Types text into the currently focused input field. "
                "PREREQUISITE: You must click the input field FIRST to focus it. "
                "Only ASCII characters are supported. "
                "This function types text only - it does not press Enter (use press_key for that)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to type (ASCII characters only)"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": (
                "Presses a keyboard key or key combination. "
                "Supported keys: 'enter', 'tab', 'esc'/'escape', 'win'/'windows', 'ctrl', 'alt', 'shift', "
                "'f4', 'c', 'v', 't', 'w', 'f', 'l'. "
                "For combinations, use '+' separator: 'ctrl+c', 'alt+f4', 'ctrl+shift+esc'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Key or key combination to press (examples: 'enter', 'ctrl+l', 'alt+tab')"
                    }
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_at_position",
            "description": (
                "Scrolls down at a specific screen position. "
                "Optional: provide target coordinates as box=[x,y] or box=[x1,y1,x2,y2]. "
                "If no coordinates provided, scrolls at screen center (500,500). "
                "Normalized coordinate system: 0-1000."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "box": {
                        "description": "Optional scroll position in 0-1000 coordinates. Format: [x,y] or [x1,y1,x2,y2]. Defaults to center if omitted.",
                        "anyOf": [
                            {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 2,
                                "maxItems": 2
                            },
                            {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 4,
                                "maxItems": 4
                            },
                            {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 2,
                                    "maxItems": 2
                                },
                                "minItems": 2,
                                "maxItems": 2
                            }
                        ]
                    }
                },
                "required": []
            }
        }
    },
]

_scenarios_screen_dimensions = {"width": 1920, "height": 1080}


def scenarios_execute_tool(tool_name: str, arg_str: Any, call_id: str, dump_cfg: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    global _scenarios_screen_dimensions
    
    if tool_name == "observe_screen":
        args, err = utils_parse_args(arg_str)
        if err:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": err}, None
        
        plan = str(args.get("plan", "")).strip()
        
        png_bytes, screen_w, screen_h = winapi_capture_screenshot_png(dump_cfg["target_w"], dump_cfg["target_h"])
        _scenarios_screen_dimensions["width"] = screen_w
        _scenarios_screen_dimensions["height"] = screen_h
        
        os.makedirs(dump_cfg["dump_dir"], exist_ok=True)
        fn = os.path.join(dump_cfg["dump_dir"], f"{dump_cfg['dump_prefix']}{dump_cfg['dump_idx']:04d}.png")
        with open(fn, "wb") as f:
            f.write(png_bytes)
        dump_cfg["dump_idx"] += 1
        
        b64 = base64.b64encode(png_bytes).decode("ascii")
        
        # OPTIMIZED: Minimal technical confirmation
        tool_msg = {
            "role": "tool",
            "tool_call_id": call_id,
            "name": tool_name,
            "content": utils_ok_payload({
                "status": "captured",
                "resolution": f"{dump_cfg['target_w']}x{dump_cfg['target_h']}",
                "saved": fn
            })
        }
        
        # OPTIMIZED: Clearer plan handoff formatting
        content_parts = []
        if plan:
            content_parts.append({
                "type": "text",
                "text": f"PREVIOUS AGENT PLAN:\n{plan}\n\n---\nCURRENT SCREEN:"
            })
        else:
            content_parts.append({
                "type": "text",
                "text": "CURRENT SCREEN (first observation):"
            })
        
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64," + b64}
        })
        
        user_msg = {"role": "user", "content": content_parts}
        
        return tool_msg, user_msg
    
    if tool_name == "click_element":
        args, err = utils_parse_args(arg_str)
        if err:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": err}, None
        label = str(args.get("label", "")).strip()
        box = args.get("box")
        if not label:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": utils_err_payload("missing_label", "label required")}, None
        if box is None:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": utils_err_payload("missing_box", "box required")}, None
        bbox, box_err = utils_parse_box(box)
        if box_err:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": box_err}, None
        x1, y1, x2, y2 = bbox
        cx, cy = utils_box_center(x1, y1, x2, y2)
        px, py = winapi_norm_to_screen_px(cx, cy, _scenarios_screen_dimensions["width"], _scenarios_screen_dimensions["height"])
        winapi_move_mouse_to_pixel(px, py)
        time.sleep(0.08)
        winapi_click_mouse()
        time.sleep(0.12)
        
        # OPTIMIZED: Factual confirmation only, no instructions
        return {"role": "tool", "tool_call_id": call_id, "name": tool_name,
                "content": utils_ok_payload({
                    "action": "click_executed",
                    "target": label,
                    "normalized_coords": f"({cx:.1f}, {cy:.1f})",
                    "screen_pixels": f"({px}, {py})"
                })}, None
    
    if tool_name == "type_text":
        args, err = utils_parse_args(arg_str)
        if err:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": err}, None
        text = str(args.get("text", ""))
        text_ascii = text.encode("ascii", "ignore").decode("ascii")
        if not text_ascii:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": utils_err_payload("empty_text", "text empty or no ASCII chars")}, None
        winapi_type_text(text_ascii)
        time.sleep(0.08)
        
        # OPTIMIZED: Echo what was typed, no additional messages
        return {"role": "tool", "tool_call_id": call_id, "name": tool_name,
                "content": utils_ok_payload({
                    "action": "text_typed",
                    "text": text_ascii,
                    "length": len(text_ascii)
                })}, None
    
    if tool_name == "press_key":
        args, err = utils_parse_args(arg_str)
        if err:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": err}, None
        key = str(args.get("key", "")).strip().lower()
        if not key:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": utils_err_payload("missing_key", "key required")}, None
        try:
            winapi_press_key(key)
            time.sleep(0.08)
            
            # OPTIMIZED: Simple confirmation
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name,
                    "content": utils_ok_payload({
                        "action": "key_pressed",
                        "key": key
                    })}, None
        except ValueError as e:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": utils_err_payload("invalid_key", str(e))}, None
    
    if tool_name == "scroll_at_position":
        args, err = utils_parse_args(arg_str)
        if err:
            return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": err}, None
        box = args.get("box")
        if box is not None:
            bbox, box_err = utils_parse_box(box)
            if box_err:
                return {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": box_err}, None
            cx, cy = utils_box_center(*bbox)
        else:
            cx, cy = 500.0, 500.0
        px, py = winapi_norm_to_screen_px(cx, cy, _scenarios_screen_dimensions["width"], _scenarios_screen_dimensions["height"])
        winapi_move_mouse_to_pixel(px, py)
        time.sleep(0.06)
        winapi_scroll_down()
        time.sleep(0.08)
        
        # OPTIMIZED: Factual report
        return {"role": "tool", "tool_call_id": call_id, "name": tool_name,
                "content": utils_ok_payload({
                    "action": "scrolled_down",
                    "normalized_position": f"({cx:.1f}, {cy:.1f})",
                    "amount": 120
                })}, None
    
    return {"role": "tool", "tool_call_id": call_id, "name": tool_name,
            "content": utils_err_payload("unknown_tool", f"Unknown tool: {tool_name}")}, None