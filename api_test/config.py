"""
API 키 설정 및 공통 유틸리티

사용법:
  1. .env 파일을 TB_multimodal/ 루트에 생성
  2. 아래 형식으로 API 키 입력:
     VWORLD_API_KEY=your_key_here
     DATA_GO_KR_API_KEY=your_key_here
     KAKAO_REST_API_KEY=your_key_here
     GOOGLE_VISION_API_KEY=your_key_here
"""

import os
import json
from pathlib import Path
from datetime import datetime

# ─── 프로젝트 경로 ──────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_SAMPLES_DIR = PROJECT_ROOT / "data_samples"
DATA_SAMPLES_DIR.mkdir(exist_ok=True)

# ─── .env 로드 (dotenv 없이 직접 파싱) ─────────────────────
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

# ─── API 키 ─────────────────────────────────────────────────
VWORLD_API_KEY = os.environ.get("VWORLD_API_KEY", "")
DATA_GO_KR_API_KEY = os.environ.get("DATA_GO_KR_API_KEY", "")
KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
GOOGLE_VISION_API_KEY = os.environ.get("GOOGLE_VISION_API_KEY", "")

# ─── 테스트용 기본 좌표 (서울시청 부근) ─────────────────────
DEFAULT_LON = 126.978
DEFAULT_LAT = 37.566

# ─── 테스트용 법정동코드 (종로구 청운효자동) ────────────────
DEFAULT_LAWD_CD = "11110"  # 서울특별시 종로구
DEFAULT_DEAL_YMD = "202501"

# ─── PNU 파서 ───────────────────────────────────────────────

def parse_pnu(pnu: str) -> dict:
    """
    PNU (19자리 필지고유번호) 파싱

    PNU 구조:
      [시도(2)] [시군구(3)] [읍면동(3)] [리(2)] [토지구분(1)] [본번(4)] [부번(4)]
      = 총 19자리

    반환:
      {
        "sido": "11",
        "sigungu": "110",
        "sigungu_cd": "11110",       # 시군구코드 5자리 (실거래가 API LAWD_CD)
        "eupmyeondong": "105",
        "ri": "00",
        "bjdong_cd": "10500",        # 법정동코드 5자리 (읍면동3+리2)
        "land_type": "1",            # 1:대지, 2:산
        "main_no": "0001",           # 본번
        "sub_no": "0000",            # 부번
        "jibun": "1",                # 지번 (본번 정수형)
        "jibun_full": "1-0",         # 지번 전체 (본번-부번)
      }
    """
    if len(pnu) != 19:
        raise ValueError(f"PNU는 19자리여야 합니다. 입력: {pnu} ({len(pnu)}자리)")

    sido = pnu[0:2]
    sigungu = pnu[2:5]
    eupmyeondong = pnu[5:8]
    ri = pnu[8:10]
    land_type = pnu[10]
    main_no = pnu[11:15]
    sub_no = pnu[15:19]

    main_int = int(main_no)
    sub_int = int(sub_no)

    return {
        "sido": sido,
        "sigungu": sigungu,
        "sigungu_cd": sido + sigungu,          # 5자리
        "eupmyeondong": eupmyeondong,
        "ri": ri,
        "bjdong_cd": eupmyeondong + ri,        # 5자리
        "land_type": land_type,
        "main_no": main_no,
        "sub_no": sub_no,
        "jibun": str(main_int),
        "jibun_full": f"{main_int}-{sub_int}" if sub_int > 0 else str(main_int),
    }


def save_sample(filename: str, data: dict) -> Path:
    """API 응답 샘플을 data_samples/에 JSON으로 저장"""
    filepath = DATA_SAMPLES_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[저장] {filepath}")
    return filepath


def print_header(title: str):
    """테스트 섹션 헤더 출력"""
    width = 60
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def print_check(label: str, passed: bool, detail: str = ""):
    """체크리스트 항목 출력"""
    icon = "[PASS]" if passed else "[FAIL]"
    msg = f"  {icon} {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def check_api_key(name: str, key: str) -> bool:
    """API 키 존재 여부 확인"""
    if key:
        masked = key[:4] + "..." + key[-4:] if len(key) > 8 else "****"
        print_check(f"{name} API 키", True, f"설정됨 ({masked})")
        return True
    else:
        print_check(f"{name} API 키", False, ".env에 키를 설정하세요")
        return False
