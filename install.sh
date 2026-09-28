#!/usr/bin/env bash
# BobBurn Installer for macOS / Linux
# Installs Bob Shell + Python dependencies, then prints run instructions.

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${CYAN}  BobBurn Installer${NC}"
echo -e "${CYAN}  Real-time Bobcoin metering for IBM Bob${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Check Python
echo -e "${YELLOW}Checking Python...${NC}"
PY=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null && "$cmd" --version 2>&1 | grep -q "Python 3"; then
        PY="$cmd"
        break
    fi
done
if [ -z "$PY" ]; then
    echo -e "${RED}ERROR: Python 3 not found. Install from https://python.org${NC}"
    exit 1
fi
echo -e "${GREEN}  Found: $($PY --version)${NC}"

# 2. Install Python deps
echo ""
echo -e "${YELLOW}Installing Python dependencies...${NC}"
$PY -m pip install -r "$SCRIPT_DIR/requirements.txt" -q
echo -e "${GREEN}  rich, python-dotenv, requests installed.${NC}"

# 3. Install Bob Shell
echo ""
echo -e "${YELLOW}Installing Bob Shell...${NC}"
if command -v bob &>/dev/null; then
    echo -e "${GREEN}  Bob Shell already installed: $(bob --version)${NC}"
else
    curl -fsSL https://bob.ibm.com/download/bobshell.sh | bash
    echo -e "${GREEN}  Bob Shell installed successfully.${NC}"
fi

# 4. Done
echo ""
echo -e "${CYAN}All done! To run BobBurn:${NC}"
echo ""
echo -e "  export BOB_API_KEY=\"bob_prod_bob-apikey_...\""
echo -e "  $PY \"$SCRIPT_DIR/bob_terminal.py\""
echo ""
echo -e "${CYAN}Get your Inference API key at: https://bob.ibm.com/admin/api-keys${NC}"
echo ""
