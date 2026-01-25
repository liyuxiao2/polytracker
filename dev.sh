#!/bin/bash
# Start both backend and frontend in development mode

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting PolyTracker Development Servers...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}\n"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

# Start backend in background
echo -e "${BLUE}[Backend]${NC} Starting Python backend on http://localhost:8000"
(cd backend && python3 run.py) &
BACKEND_PID=$!

# Give backend a moment to start
sleep 2

# Start frontend in background
echo -e "${BLUE}[Frontend]${NC} Starting Next.js frontend on http://localhost:3000"
(cd frontend && npm run dev) &
FRONTEND_PID=$!

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
