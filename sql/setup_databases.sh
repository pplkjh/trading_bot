#!/bin/bash
# =============================================================================
# JackBot Trading Bot Database Setup Script
# =============================================================================
# 이 스크립트는 JackBot 트레이딩 봇의 모든 데이터베이스를 자동으로 설정합니다.
#
# 사용법:
#   chmod +x sql/setup_databases.sh
#   ./sql/setup_databases.sh
# =============================================================================

set -e  # 오류 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로고 출력
echo -e "${BLUE}"
echo "============================================================================="
echo "   ___           _    ____        _     ____  ____    ____       _               "
echo "  |_  |         | |  |  _ \\      | |   |  _ \\|  _ \\  / ___|  ___| |_ _   _ _ __  "
echo "    | | __ _  __| |  | |_) | ___ | |_  | | | | |_) | \\___ \\ / _ \\ __| | | | '_ \\ "
echo "/\\__| |/ _\` |/ _\` |  |  _ < / _ \\| __| | |_| |  _ <   ___) |  __/ |_| |_| | |_) |"
echo "\\____/ \\__,_|\\__,_|  |_| \\_\\___/|_|   |____/|_| \\_\\ |____/ \\___|\\__|\\__,_| .__/ "
echo "                                                                           |_|    "
echo "============================================================================="
echo -e "${NC}"

# 현재 디렉토리 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}프로젝트 디렉토리: $PROJECT_DIR${NC}"
echo ""

# MySQL 사용자 정보 입력
echo -e "${YELLOW}MySQL 접속 정보를 입력하세요:${NC}"
read -p "MySQL 사용자명 [root]: " MYSQL_USER
MYSQL_USER=${MYSQL_USER:-root}

read -sp "MySQL 비밀번호: " MYSQL_PASSWORD
echo ""

# MySQL 연결 테스트
echo -e "\n${BLUE}MySQL 연결 테스트 중...${NC}"
if ! mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" -e "SELECT 1;" &> /dev/null; then
    echo -e "${RED}오류: MySQL 접속에 실패했습니다. 사용자명과 비밀번호를 확인하세요.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ MySQL 연결 성공${NC}"

# Step 1: 데이터베이스 생성
echo -e "\n${BLUE}[Step 1/4] 데이터베이스 생성 중...${NC}"
mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" << EOF
CREATE DATABASE IF NOT EXISTS JackBot1_imi1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS daily_buy_list CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS daily_craw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EOF

echo -e "${GREEN}✓ 데이터베이스 생성 완료${NC}"
echo -e "  - JackBot1_imi1"
echo -e "  - daily_buy_list"
echo -e "  - daily_craw"

# Step 2: JackBot1_imi1 스키마 적용
echo -e "\n${BLUE}[Step 2/4] JackBot1_imi1 스키마 적용 중...${NC}"
if [ -f "$SCRIPT_DIR/jackbot_schema.sql" ]; then
    mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" JackBot1_imi1 < "$SCRIPT_DIR/jackbot_schema.sql" | grep -v "^index"
    echo -e "${GREEN}✓ JackBot1_imi1 스키마 적용 완료${NC}"
else
    echo -e "${RED}오류: jackbot_schema.sql 파일을 찾을 수 없습니다.${NC}"
    exit 1
fi

# Step 3: daily_buy_list 스키마 적용
echo -e "\n${BLUE}[Step 3/4] daily_buy_list 스키마 적용 중...${NC}"
if [ -f "$SCRIPT_DIR/daily_buy_list_schema.sql" ]; then
    mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" daily_buy_list < "$SCRIPT_DIR/daily_buy_list_schema.sql" | grep -v "^index"
    echo -e "${GREEN}✓ daily_buy_list 기본 스키마 적용 완료${NC}"
else
    echo -e "${RED}오류: daily_buy_list_schema.sql 파일을 찾을 수 없습니다.${NC}"
    exit 1
fi

if [ -f "$SCRIPT_DIR/pred_signal.sql" ]; then
    mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" daily_buy_list < "$SCRIPT_DIR/pred_signal.sql"
    echo -e "${GREEN}✓ pred_signal 테이블 생성 완료${NC}"
else
    echo -e "${YELLOW}경고: pred_signal.sql 파일을 찾을 수 없습니다.${NC}"
fi

# Step 4: 설정 확인
echo -e "\n${BLUE}[Step 4/4] 데이터베이스 설정 확인 중...${NC}"

echo -e "\n${YELLOW}JackBot1_imi1 테이블 목록:${NC}"
mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" JackBot1_imi1 -e "SHOW TABLES;" | tail -n +2 | while read table; do
    echo -e "  ${GREEN}✓${NC} $table"
done

echo -e "\n${YELLOW}daily_buy_list 테이블 목록:${NC}"
mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" daily_buy_list -e "SHOW TABLES;" | tail -n +2 | while read table; do
    echo -e "  ${GREEN}✓${NC} $table"
done

echo -e "\n${YELLOW}daily_craw 데이터베이스:${NC}"
TABLE_COUNT=$(mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" daily_craw -e "SHOW TABLES;" | tail -n +2 | wc -l)
echo -e "  ${GREEN}✓${NC} 생성됨 (현재 테이블 수: $TABLE_COUNT)"
echo -e "  ${BLUE}ℹ${NC}  종목별 테이블은 collector 실행 시 자동 생성됩니다."

# 완료 메시지
echo -e "\n${GREEN}============================================================================="
echo -e "                    데이터베이스 설정이 완료되었습니다!"
echo -e "=============================================================================${NC}"
echo ""
echo -e "${YELLOW}다음 단계:${NC}"
echo -e "  1. library/cf.py 파일의 DB 설정을 확인하세요"
echo -e "     - db_id: MySQL 사용자명"
echo -e "     - db_passwd: MySQL 비밀번호"
echo -e "     - db_ip: MySQL 서버 IP (기본값: localhost)"
echo -e "     - db_port: MySQL 포트 (기본값: 3306)"
echo ""
echo -e "  2. collector를 실행하여 종목 데이터를 수집하세요"
echo -e "     ${BLUE}python collector_v3.py${NC}"
echo ""
echo -e "  3. trader를 실행하여 자동매매를 시작하세요"
echo -e "     ${BLUE}python trader.py${NC}"
echo ""
echo -e "자세한 정보는 ${BLUE}sql/DATABASE_SETUP.md${NC} 파일을 참조하세요."
echo ""
