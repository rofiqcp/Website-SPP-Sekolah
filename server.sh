#!/bin/bash
#
# Website SPP Sekolah Manager
# 1=start(skip) 2=build+start 3=stop 4=status 5=syntax 6=backup
#

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; GRAY='\033[0;37m'; NC='\033[0m'

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_NAME="spp_sekolah"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
BACKEND_LOG_DIR="$BACKEND_DIR/log"
FRONTEND_LOG_DIR="$FRONTEND_DIR/log"
FRONTEND_PORT=5100
BACKEND_PORT=5101
PUBLIC_URL="https://sekolah.otomasi.app"
FRONTEND_NAME="spp-sekolah-frontend"
BACKEND_NAME="spp-sekolah-backend"

print_header() {
    echo ""; echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║      Website SPP Sekolah Manager       ║${NC}"
    echo -e "${CYAN}║    Backend:5101 • Frontend:5100        ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"; echo ""
}

port_listening() { ss -tlnp 2>/dev/null | grep -q ":$1 "; }
pm2_required() { command -v pm2 &>/dev/null || { echo -e "   ${RED}ERROR${NC} - pm2 tidak ditemukan"; exit 1; }; }

is_running() { port_listening $FRONTEND_PORT && port_listening $BACKEND_PORT; }

stop_all() {
    echo -e "${YELLOW}Menghentikan service SPP Sekolah...${NC}"; echo ""
    pm2_required
    pm2 delete "$FRONTEND_NAME" 2>/dev/null && echo -e "   ${GREEN}✓${NC} Frontend dihentikan" || echo -e "   ${GRAY}○${NC} Frontend tidak berjalan"
    pm2 delete "$BACKEND_NAME" 2>/dev/null && echo -e "   ${GREEN}✓${NC} Backend dihentikan" || echo -e "   ${GRAY}○${NC} Backend tidak berjalan"
    echo ""; echo -e "${GREEN}Selesai stop.${NC}"; echo ""
}

clean_orphan_port() {
    local port="$1" name="$2" pid
    pid=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -oP 'pid=\K[0-9]+' | head -1)
    [ -z "$pid" ] && return 0
    if pm2 list 2>/dev/null | grep -q "$name.*online"; then
        echo -e "   ${GREEN}○${NC} Port $port sudah dipegang PM2 $name"
        return 0
    fi
    echo -e "   ${YELLOW}⚠${NC} Orphan process PID=$pid di port $port — dibersihkan..."
    kill -TERM "$pid" 2>/dev/null || true
    sleep 2
    kill -KILL "$pid" 2>/dev/null || true
}

check_python_syntax() {
    echo -e "${YELLOW}Memeriksa sintaks Python...${NC}"
    python3 -m py_compile "$BACKEND_DIR/app.py" && echo -e "   ${GREEN}✓${NC} Backend Python OK"
}

install_backend() {
    cd "$BACKEND_DIR"
    createdb spp_sekolah 2>/dev/null || true
    [ -d .venv ] || python3 -m venv .venv
    . .venv/bin/activate
    pip install -r requirements.txt >/tmp/spp-sekolah-pip.log
}

build_frontend() {
    echo -e "${YELLOW}Building Frontend...${NC}"
    cd "$FRONTEND_DIR"
    [ -d node_modules ] || npm install
    npm run build
    echo -e "   ${GREEN}✓${NC} Frontend build berhasil"
}

start_services() {
    pm2_required
    mkdir -p "$BACKEND_LOG_DIR" "$FRONTEND_LOG_DIR"

    echo -e "${YELLOW}Starting Backend...${NC}"
    install_backend
    clean_orphan_port $BACKEND_PORT "$BACKEND_NAME"
    cd "$BACKEND_DIR"
    pm2 start .venv/bin/python --name "$BACKEND_NAME" \
        --log "$BACKEND_LOG_DIR/backend-out.log" \
        --error "$BACKEND_LOG_DIR/backend-error.log" \
        -- -m gunicorn app:app --bind "0.0.0.0:$BACKEND_PORT" --workers 2
    for i in $(seq 1 15); do curl -sf "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null && break; sleep 1; done
    curl -sf "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null && echo -e "   ${GREEN}✓${NC} Backend started on port $BACKEND_PORT" || echo -e "   ${RED}✗${NC} Backend health gagal"
    echo ""

    echo -e "${YELLOW}Starting Frontend...${NC}"
    cd "$FRONTEND_DIR"
    [ -d node_modules ] || npm install
    clean_orphan_port $FRONTEND_PORT "$FRONTEND_NAME"
    pm2 start npm --name "$FRONTEND_NAME" \
        --log "$FRONTEND_LOG_DIR/frontend-out.log" \
        --error "$FRONTEND_LOG_DIR/frontend-error.log" \
        -- start
    for i in $(seq 1 15); do curl -sf "http://127.0.0.1:$FRONTEND_PORT" >/dev/null && break; sleep 1; done
    curl -sf "http://127.0.0.1:$FRONTEND_PORT" >/dev/null && echo -e "   ${GREEN}✓${NC} Frontend started on port $FRONTEND_PORT" || echo -e "   ${RED}✗${NC} Frontend health gagal"
    echo ""

    pm2 save
    echo -e "${GREEN}Services Started!${NC}"
    echo -e "   Local:  ${CYAN}http://localhost:$FRONTEND_PORT${NC}"
    echo -e "   Public: ${CYAN}$PUBLIC_URL${NC}"
    echo -e "   API:    ${CYAN}http://localhost:$BACKEND_PORT${NC}"
    echo ""
}

db_backup() {
    local script="$APP_DIR/scripts/backup-db.sh"
    [ -x "$script" ] || chmod +x "$script"
    echo -e "${YELLOW}Backup PostgreSQL $DB_NAME...${NC}"
    bash "$script" && echo -e "   ${GREEN}✓${NC} Backup selesai" || echo -e "   ${RED}✗${NC} Backup gagal"
    echo ""
}

do_start() {
    if is_running; then echo -e "   ${GREEN}✓${NC} SPP Sekolah sudah aktif — dilewati"; echo ""; return 0; fi
    stop_all
    echo -e "${GRAY}(Lewati build — pakai source/dev server Vite)${NC}"; echo ""
    start_services
}

build_and_start() { stop_all; check_python_syntax; echo ""; build_frontend; echo ""; start_services; }

check_status() {
    echo -e "${YELLOW}PM2 Processes:${NC}"
    pm2 list 2>/dev/null | grep "spp-sekolah" || echo -e "   ${GRAY}○${NC} Tidak ada proses SPP Sekolah"
    echo ""; echo -e "${YELLOW}Port Status:${NC}"
    port_listening $FRONTEND_PORT && echo -e "   ${GREEN}✓${NC} Port $FRONTEND_PORT (Frontend): LISTENING" || echo -e "   ${RED}✗${NC} Port $FRONTEND_PORT (Frontend): NOT LISTENING"
    port_listening $BACKEND_PORT && echo -e "   ${GREEN}✓${NC} Port $BACKEND_PORT (Backend): LISTENING" || echo -e "   ${RED}✗${NC} Port $BACKEND_PORT (Backend): NOT LISTENING"
    echo -e "   Public URL: ${CYAN}$PUBLIC_URL${NC}"
    echo ""
}

show_menu() {
    echo -e "${CYAN}Pilih opsi:${NC}"; echo ""
    echo "  1) Start (skip kalau sudah jalan)"
    echo "  2) Build + Start (cek Python + build frontend)"
    echo "  3) Stop semua service"
    echo "  4) Cek status"
    echo "  5) Cek sintaks Python saja"
    echo "  6) Backup database PostgreSQL"
    echo ""; read -rp "Masukkan pilihan [1-6]: " choice
    case $choice in
        1) do_start ;; 2) build_and_start ;; 3) stop_all ;; 4) check_status ;; 5) check_python_syntax ;; 6) db_backup ;;
        *) echo -e "${RED}Pilihan tidak valid${NC}" ;;
    esac
}

print_header
case "$1" in
    1|start) do_start ;;
    2|build) build_and_start ;;
    3|stop) stop_all ;;
    4|status) check_status ;;
    5|syntax) check_python_syntax ;;
    6|backup) db_backup ;;
    *) show_menu ;;
esac
