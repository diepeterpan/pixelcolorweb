import ast
import json
import threading
import time
import urllib.request
import urllib.error
from contextlib import contextmanager
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
        "track_http": True,
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
        "track_http": True,
        "code": '''def get_text():
    return "★ PIXELCOLOR 96x16 WEB MATRIX ACTIVE ★"
'''
    },
    "system_status": {
        "id": "system_status",
        "name": "Dynamic Greeting",
        "description": "Changes text greeting based on hour of the day",
        "track_http": True,
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


class ScriptMetricsStore:
    """In-memory time-windowed (last 1 hour) HTTP metrics store per script."""

    def __init__(self, window_seconds: int = 3600):
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        # script_id -> list of record dicts
        self._events: Dict[str, List[Dict[str, Any]]] = {}

    def _prune(self, script_id: Optional[str] = None):
        cutoff = time.time() - self.window_seconds
        with self._lock:
            targets = [script_id] if script_id else list(self._events.keys())
            for sid in targets:
                if sid in self._events:
                    self._events[sid] = [ev for ev in self._events[sid] if ev.get("timestamp_epoch", 0) >= cutoff]

    def record_call(
        self,
        script_id: str,
        method: str,
        url: str,
        status_code: Any,
        duration_ms: float,
        caller: str = "script",
        error: Optional[str] = None
    ):
        if not script_id:
            return
        now = time.time()
        record = {
            "timestamp_epoch": now,
            "timestamp": datetime.fromtimestamp(now).strftime("%H:%M:%S"),
            "iso_time": datetime.fromtimestamp(now).isoformat(),
            "method": method.upper() if method else "GET",
            "url": str(url),
            "status_code": status_code,
            "duration_ms": round(duration_ms, 1),
            "caller": caller,
            "error": error
        }
        with self._lock:
            if script_id not in self._events:
                self._events[script_id] = []
            self._events[script_id].append(record)
        # Prune old events for this script
        self._prune(script_id)

    def get_metrics(self, script_id: str) -> Dict[str, Any]:
        self._prune(script_id)
        with self._lock:
            records = list(self._events.get(script_id, []))

        total_calls = len(records)
        if total_calls == 0:
            return {
                "script_id": script_id,
                "window_seconds": self.window_seconds,
                "total_calls": 0,
                "success_count": 0,
                "error_count": 0,
                "avg_duration_ms": 0.0,
                "requests_per_minute": 0.0,
                "records": []
            }

        success_count = sum(
            1 for r in records
            if isinstance(r.get("status_code"), int) and 200 <= r["status_code"] < 400
        )
        error_count = total_calls - success_count
        avg_duration = sum(r.get("duration_ms", 0.0) for r in records) / total_calls
        req_per_min = round(total_calls / 60.0, 2)

        # Most recent calls first
        sorted_records = sorted(records, key=lambda x: x.get("timestamp_epoch", 0), reverse=True)

        return {
            "script_id": script_id,
            "window_seconds": self.window_seconds,
            "total_calls": total_calls,
            "success_count": success_count,
            "error_count": error_count,
            "avg_duration_ms": round(avg_duration, 1),
            "requests_per_minute": req_per_min,
            "records": sorted_records
        }

    def clear(self, script_id: str):
        with self._lock:
            if script_id in self._events:
                self._events[script_id] = []


metrics_store = ScriptMetricsStore()


@contextmanager
def track_script_http(script_id: Optional[str], caller: str = "script"):
    """
    Context manager that silently intercepts urllib.request.urlopen and requests.Session.send
    during script execution and records metrics to metrics_store.
    Does NOT output logs to console or file.
    """
    if not script_id:
        yield
        return

    orig_urlopen = urllib.request.urlopen

    def hooked_urlopen(url_or_req, *args, **kwargs):
        start = time.perf_counter()
        method = "GET"
        url = ""
        if isinstance(url_or_req, str):
            url = url_or_req
        elif hasattr(url_or_req, "full_url"):
            url = getattr(url_or_req, "full_url", "")
            method = getattr(url_or_req, "get_method", lambda: "GET")()

        try:
            resp = orig_urlopen(url_or_req, *args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            status = getattr(resp, "status", getattr(resp, "code", 200))
            metrics_store.record_call(
                script_id=script_id,
                method=method,
                url=url,
                status_code=status,
                duration_ms=duration_ms,
                caller=caller
            )
            return resp
        except urllib.error.HTTPError as e:
            duration_ms = (time.perf_counter() - start) * 1000
            metrics_store.record_call(
                script_id=script_id,
                method=method,
                url=url,
                status_code=e.code,
                duration_ms=duration_ms,
                caller=caller,
                error=f"HTTPError: {e.code} {e.reason}"
            )
            raise
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            metrics_store.record_call(
                script_id=script_id,
                method=method,
                url=url,
                status_code="ERROR",
                duration_ms=duration_ms,
                caller=caller,
                error=str(e)
            )
            raise

    urllib.request.urlopen = hooked_urlopen

    orig_requests_send = None
    try:
        import requests
        orig_requests_send = requests.Session.send

        def hooked_requests_send(session_self, request, *args, **kwargs):
            start = time.perf_counter()
            method = getattr(request, "method", "GET")
            url = getattr(request, "url", "")
            try:
                resp = orig_requests_send(session_self, request, *args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                metrics_store.record_call(
                    script_id=script_id,
                    method=method,
                    url=url,
                    status_code=resp.status_code,
                    duration_ms=duration_ms,
                    caller=caller
                )
                return resp
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                metrics_store.record_call(
                    script_id=script_id,
                    method=method,
                    url=url,
                    status_code="ERROR",
                    duration_ms=duration_ms,
                    caller=caller,
                    error=str(e)
                )
                raise

        requests.Session.send = hooked_requests_send
    except ImportError:
        pass

    try:
        yield
    finally:
        urllib.request.urlopen = orig_urlopen
        if orig_requests_send is not None:
            try:
                import requests
                requests.Session.send = orig_requests_send
            except ImportError:
                pass


class ScriptManager:
    def __init__(self):
        self._ensure_default_scripts()
        self._contexts: Dict[str, Dict[str, Any]] = {}
        self._code_hashes: Dict[str, str] = {}
        self._context_lock = threading.Lock()

    def clear_context(self, script_id: str):
        with self._context_lock:
            self._contexts.pop(script_id, None)
            self._code_hashes.pop(script_id, None)

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
                    data = json.load(f)
                    if "track_http" not in data:
                        data["track_http"] = True
                    scripts.append(data)
            except Exception as e:
                print(f"Error reading script {file}: {e}")
        return scripts

    def get_script(self, script_id: str) -> Optional[Dict[str, Any]]:
        file_path = SCRIPTS_DIR / f"{script_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "track_http" not in data:
                data["track_http"] = True
            return data

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

    def _get_base_globals(self) -> Dict[str, Any]:
        return {
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

    def execute_script(
        self,
        code: str,
        script_id: Optional[str] = None,
        caller: str = "test_run",
        track_http: Optional[bool] = None
    ) -> Tuple[bool, str]:
        valid, err = self.validate_code(code)
        if not valid:
            return False, err or "Invalid code"

        # Determine whether tracking should be active
        should_track = True
        if track_http is not None:
            should_track = track_http
        elif script_id:
            script_data = self.get_script(script_id)
            if script_data:
                should_track = script_data.get("track_http", True)

        effective_script_id = script_id if should_track else None

        try:
            with track_script_http(effective_script_id, caller=caller):
                if script_id:
                    with self._context_lock:
                        # Check if context already compiled and code is unchanged
                        if script_id in self._contexts and self._code_hashes.get(script_id) == code:
                            scope = self._contexts[script_id]
                        else:
                            # Single dictionary as both globals and locals so module-level globals persist
                            scope = self._get_base_globals()
                            exec(code, scope)
                            self._contexts[script_id] = scope
                            self._code_hashes[script_id] = code
                else:
                    scope = self._get_base_globals()
                    exec(code, scope)

                if "get_text" not in scope or not callable(scope["get_text"]):
                    return False, "Function get_text() was not found or is not callable."
                result = scope["get_text"]()
                if not isinstance(result, str):
                    result = str(result)
                return True, result
        except Exception as e:
            # If runtime error occurred during exec of a cached context, invalidate it so next run recompiles
            if script_id:
                self.clear_context(script_id)
            return False, f"Runtime Error: {str(e)}"

    def save_script(
        self,
        script_id: str,
        name: str,
        description: str,
        code: str,
        track_http: bool = True
    ) -> Tuple[bool, Optional[str]]:
        valid, err = self.validate_code(code)
        if not valid:
            return False, err

        file_path = SCRIPTS_DIR / f"{script_id}.json"
        data = {
            "id": script_id,
            "name": name,
            "description": description,
            "code": code,
            "track_http": bool(track_http),
            "updated_at": datetime.now().isoformat()
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.clear_context(script_id)
        return True, None

    def delete_script(self, script_id: str) -> bool:
        file_path = SCRIPTS_DIR / f"{script_id}.json"
        if file_path.exists():
            file_path.unlink()
            metrics_store.clear(script_id)
            self.clear_context(script_id)
            return True
        return False


script_manager = ScriptManager()
