import ast
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPTS_DIR = Path("data/scripts")
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SCRIPTS = {
    "default_clock": {
        "id": "default_clock",
        "name": "Live Digital Clock & Date",
        "description": "Displays current local time with seconds and date",
        "code": '''def get_text():
    # Returns formatted date and time for 96x16 matrix
    now = datetime.now()
    return now.strftime("%H:%M:%S  •  %a %d %b")
'''
    },
    "rainbow_welcome": {
        "id": "rainbow_welcome",
        "name": "Rainbow Welcome Banner",
        "description": "Vibrant marquee text suitable for 96x16 display",
        "code": '''def get_text():
    return "★ PIXELCOLOR 96x16 WEB MATRIX ACTIVE ★"
'''
    },
    "system_status": {
        "id": "system_status",
        "name": "Dynamic Greeting",
        "description": "Changes text greeting based on hour of the day",
        "code": '''def get_text():
    hour = datetime.now().hour
    if hour < 12:
        greeting = "GOOD MORNING!"
    elif hour < 18:
        greeting = "GOOD AFTERNOON!"
    else:
        greeting = "GOOD EVENING!"
    return f"{greeting}  |  {datetime.now().strftime('%H:%M')}"
'''
    }
}

class ScriptManager:
    def __init__(self):
        self._ensure_default_scripts()

    def _ensure_default_scripts(self):
        for script_id, data in DEFAULT_SCRIPTS.items():
            file_path = SCRIPTS_DIR / f"{script_id}.json"
            if not file_path.exists():
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

    def list_scripts(self) -> List[Dict[str, Any]]:
        scripts = []
        for file in SCRIPTS_DIR.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    scripts.append(json.load(f))
            except Exception as e:
                print(f"Error reading script {file}: {e}")
        return scripts

    def get_script(self, script_id: str) -> Optional[Dict[str, Any]]:
        file_path = SCRIPTS_DIR / f"{script_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def validate_code(self, code: str) -> Tuple[bool, Optional[str]]:
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax Error: {e.msg} at line {e.lineno}, col {e.offset}"
        except Exception as e:
            return False, f"Parse Error: {str(e)}"

        # Check for banned constructs (subprocess, os.system, file deletion)
        BANNED = {"os", "sys", "subprocess", "shutil", "socket", "builtins", "__import__"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in BANNED:
                        return False, f"Importing '{alias.name}' is restricted for safety."
            elif isinstance(node, ast.ImportFrom):
                if node.module in BANNED:
                    return False, f"Importing from '{node.module}' is restricted for safety."
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "open"}:
                    return False, f"Function '{node.func.id}()' is prohibited."

        # Verify that get_text function exists
        has_get_text = any(isinstance(n, ast.FunctionDef) and n.name == "get_text" for n in tree.body)
        if not has_get_text:
            return False, "Code must define a function named 'get_text()' that returns text."

        return True, None

    def check_syntax(self, code: str) -> Tuple[bool, str]:
        try:
            ast.parse(code)
            return True, "Syntax OK: No syntax errors detected."
        except SyntaxError as e:
            text_snippet = f" -> {e.text.strip()}" if e.text else ""
            return False, f"Syntax Error on line {e.lineno}, col {e.offset}: {e.msg}{text_snippet}"
        except Exception as e:
            return False, f"Syntax Parse Error: {str(e)}"

    def fix_indentation(self, code: str) -> Tuple[bool, str, str]:
        lines = code.split("\n")
        fixed_lines = []
        changes = 0
        has_mixed = False
        for line in lines:
            stripped = line.lstrip(" \t")
            if not stripped:
                fixed_lines.append("")
                continue
            indent = line[: len(line) - len(stripped)]
            if "\t" in indent and " " in indent:
                has_mixed = True
            if "\t" in indent:
                # Standardize 1 tab -> 4 spaces
                new_indent = indent.replace("\t", "    ")
                fixed_lines.append(new_indent + stripped)
                changes += 1
            else:
                fixed_lines.append(line)

        fixed_code = "\n".join(fixed_lines)
        ok, msg = self.check_syntax(fixed_code)
        report = f"Fixed {changes} lines containing tabs/mixed indentations to 4-space indentations."
        if has_mixed:
            report += " Converted mixed spaces and tabs."
        if not ok:
            report += f" Note: {msg}"
        else:
            report += " Syntax verified successfully."
        return True, fixed_code, report

    def execute_script(self, code: str) -> Tuple[bool, str]:
        valid, err = self.validate_code(code)
        if not valid:
            return False, err or "Invalid code"

        safe_globals = {
            "datetime": datetime,
            "time": time,
            "str": str,
            "int": int,
            "float": float,
            "len": len,
            "range": range,
            "list": list,
            "dict": dict,
            "min": min,
            "max": max,
            "round": round
        }
        local_scope = {}
        try:
            exec(code, safe_globals, local_scope)
            if "get_text" not in local_scope or not callable(local_scope["get_text"]):
                return False, "Function get_text() was not found or is not callable."
            result = local_scope["get_text"]()
            if not isinstance(result, str):
                result = str(result)
            return True, result
        except Exception as e:
            return False, f"Runtime Error: {str(e)}"

    def save_script(self, script_id: str, name: str, description: str, code: str) -> Tuple[bool, Optional[str]]:
        valid, err = self.validate_code(code)
        if not valid:
            return False, err

        file_path = SCRIPTS_DIR / f"{script_id}.json"
        data = {
            "id": script_id,
            "name": name,
            "description": description,
            "code": code,
            "updated_at": datetime.now().isoformat()
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True, None

    def delete_script(self, script_id: str) -> bool:
        file_path = SCRIPTS_DIR / f"{script_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

script_manager = ScriptManager()

