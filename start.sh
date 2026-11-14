#!/usr/bin/env bash
set -e

PORT=8080
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"

# Check for --debug argument or DEBUG environment variable
DEBUG_OPT=""
for arg in "$@"; do
    if [ "$arg" == "--debug" ] || [ "$arg" == "-d" ]; then
        export DEBUG=1
        DEBUG_OPT="--log-level debug"
        echo "[INFO] Debug logging mode enabled."
    fi
done

echo "=================================================="
echo "    PyPixelColor Web UI Startup Script"
echo "=================================================="

# 1. Check if port is in use and prompt to kill if needed
check_port() {
    local target_port=$1
    # Check using lsof or ss/fuser
    local pid=""
    if command -v lsof >/dev/null 2>&1; then
        pid=$(lsof -ti tcp:"${target_port}" 2>/dev/null || true)
    elif command -v fuser >/dev/null 2>&1; then
        pid=$(fuser "${target_port}"/tcp 2>/dev/null | tr -d ' ' || true)
    fi

    if [ -n "${pid}" ]; then
        echo ""
        echo "[WARNING] Port ${target_port} is currently in use!"
        echo "--------------------------------------------------"
        echo "Process Information:"
        ps -p "${pid}" -o pid,user,comm,args || true
        echo "--------------------------------------------------"
        read -r -p "Would you like to terminate PID ${pid} to free port ${target_port}? [y/N]: " choice
        case "$choice" in
            [yY][eE][sS]|[yY])
                echo "Terminating process ${pid}..."
                kill -9 "${pid}" 2>/dev/null || true
                sleep 1
                echo "Port ${target_port} is now free."
                ;;
            *)
                echo "Cannot start server on port ${target_port} while it is occupied. Exiting."
                exit 1
                ;;
        esac
    fi
}

check_port "${PORT}"

# 2. Check whether a venv is available, create if not
if [ ! -d "${VENV_DIR}" ] || [ ! -f "${VENV_DIR}/bin/activate" ]; then
    echo ""
    echo "[INFO] No existing virtual environment found at ${VENV_DIR}."
    echo "[INFO] Creating virtual environment (.venv)..."
    python3 -m venv "${VENV_DIR}"
    
    echo "[INFO] Upgrading pip and installing required dependencies from requirements.txt..."
    "${VENV_DIR}/bin/pip" install --upgrade pip
    "${VENV_DIR}/bin/pip" install -r "${PROJECT_DIR}/requirements.txt"
else
    echo "[INFO] Found existing virtual environment at ${VENV_DIR}."
fi

# 3. Activate venv
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

# 4. Launch PyPixelColor Web Application
echo ""
echo "=================================================="
echo " Starting PyPixelColor Web UI on http://localhost:${PORT}"
echo " Press Ctrl+C to stop the server."
echo "=================================================="
echo ""

exec uvicorn src.pixelweb.main:app --host 0.0.0.0 --port "${PORT}" ${DEBUG_OPT}

