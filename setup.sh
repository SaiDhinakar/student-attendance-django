# This script checks for OS, Python 3.12, uv, dependencies, and checkpoints.


WHITE='\033[1;37m'
RED='\033[1;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

GREEN='\033[1;32m'
print_success() {
    echo -e "${GREEN}$1${NC}"
}
print_failure() {
    echo -e "${RED}$1${NC}"
}
print_process() {
    echo -e "${YELLOW}$1${NC}"
}
print_text() {
    echo -e "${WHITE}$1${NC}"
}


print_text "\n===================================="
print_text "   STUDENT ATTENDANCE PROJECT SETUP   "
print_text "====================================\n"

# Step 1: Check OS
OS_NAME=$(uname -s)
if [[ "$OS_NAME" != "Linux" ]]; then
    print_failure "[X] This script is intended for Linux systems. Detected: $OS_NAME"
    exit 1
else
    print_success "[OK] OS: Linux detected."
fi

# Step 2: Check for Python 3.12


if command -v python3.12 &> /dev/null; then
    PY_VER=$(python3.12 --version)
    print_success "[OK] $PY_VER found."
else
    print_failure "[X] Python 3.12 is not installed. Please install it and rerun this script."
    exit 1
fi

# Step 3: Check for uv


if command -v uv &> /dev/null; then
    UV_VER=$(uv --version)
    print_success "[OK] uv ($UV_VER) is installed."
else
    print_process "[..] uv is not installed. Installing uv..."
    python3.12 -m pip install uv || { print_failure "[X] Failed to install uv."; exit 1; }
    print_success "[OK] uv installed."
fi

# Step 4: Install dependencies with uv sync


if [ -f "pyproject.toml" ] && [ -f "uv.lock" ]; then
    print_process "[>>] Syncing dependencies with uv..."
    uv sync && print_success "[OK] Dependencies are up to date!" || { print_failure "[X] Failed to sync dependencies."; exit 1; }
else
    print_failure "[X] pyproject.toml or uv.lock not found."
    exit 1
fi

# Step 5: Check for checkpoints


if [ -d "prediction_backend/checkpoints" ] && [ "$(ls -A prediction_backend/checkpoints)" ]; then
    print_success "[OK] Checkpoints found in prediction_backend/checkpoints."
else
    print_failure "[X] Required checkpoints missing in prediction_backend/checkpoints. Please add them."
    exit 1
fi


print_text "\n\n[✓] SETUP COMPLETE! Your environment is ready."
