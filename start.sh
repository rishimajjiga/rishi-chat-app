#!/usr/bin/env bash
# ── RealChat Quick Start (macOS / Linux) ──────────────────────────────────────
set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo -e "${GREEN}🚀 Starting RealChat...${NC}"

# 1. Python check
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}✗ Python 3 not found. Install from https://python.org${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Python 3 found: $(python3 --version)${NC}"

# 2. Virtual environment
if [ ! -d "venv" ]; then
  echo -e "${YELLOW}→ Creating virtual environment...${NC}"
  python3 -m venv venv
fi
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment active${NC}"

# 3. Dependencies
echo -e "${YELLOW}→ Installing dependencies...${NC}"
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# 4. .env setup
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo -e "${YELLOW}→ Created .env from template (edit SECRET_KEY for production)${NC}"
fi

# 5. Launch
echo -e "${GREEN}✓ All set! Opening http://localhost:5000${NC}"
echo ""
python3 app.py
