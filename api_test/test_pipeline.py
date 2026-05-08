"""
Step 7: 데이터 연계 가능성 종합 검증 — 풀 파이프라인 테스트

목적:
  실제 건물 1개로 전체 데이터 파이프라인을 테스트:
    Vworld(폴리곤+PNU) → 실거래가 → 건축물대장 → 에너지

핵심 발견:
  BD_MGT_SN은 만능 공통키가 아니다.
  PNU를 분해하여 각 API에 맞는 파라미터로 변환해야 한다.

  Vworld GIS건물통합정보 (BD_MGT_SN + PNU + 폴리곤)
       │
       ├── PNU 분해 → 시군구코드(5) + 법정동코드(5) + 번 + 지
       │       │
       │       ├──→ 실거래가 API (법정동코드 5자리 + 지번)
       │       ├──→ 건축물대장 API (시군구코드 + 법정동코드 + 번 + 지)
       │       └──→ 건물에너지 API (시군구코드 + 법정동코드 + 번 + 지)
       │
       └── BD_MGT_SN → 도로명주소 추출 → 카카오맵 보조 검증

테스트 시나리오:
  1) 아파트(집합건물) 케이스
  2) 단독건물 케이스
"""

import json
import sys
import traceback
from config import (
    parse_pnu, save_sample, print_header, print_check,
    VWORLD_API_KEY, DATA_GO_KR_API_KEY, KAKAO_REST_API_KEY,
    DEFAULT_LON, DEFAULT_LAT, DEFAULT_DEAL_YMD,
)

# 각 테스트 모듈 임포트
from test_vworld import test_get_buildings
from test_realtrade import test_apt_trade
from test_building_registry import test_title_info
from test_energy import test_energy_usage
from test_kakao import test_coord_to_address


def run_full_pipeline(lon: float, lat: float, label: str = "테스트 건물",
                      deal_ymd: str = DEFAULT_DEAL_YMD):
    """
    전체 파이프라인 실행:
      1. Vworld → 건물 폴리곤 + PNU 획득
      2. PNU 파싱 → 시군구코드, 법정동코드, 번, 지 추출
      3. 실거래가 API 조회
      4. 건축물대장 API 조회
      5. 에너지 API 조회
      6. 카카오맵 교차 검증
    """
    print_header(f"풀 파이프라인 테스트: {label}")
    print(f"  좌표: ({lon}, {lat})")
    print(f"  계약년월: {deal_ymd}")

    pipeline_result = {
        "label": label,
        "input": {"lon": lon, "lat": lat, "deal_ymd": deal_ymd},
        "steps": {},
        "errors": [],
        "linkage": {},
    }

    # ─── Step 1: Vworld 건물 폴리곤 ────────────────────
    print_header("Pipeline Step 1/6: Vworld 건물 폴리곤 조회")

    pnu = None
    bd_mgt_sn = None

    if not VWORLD_API_KEY:
        print("  [SKIP] VWORLD_API_KEY 미설정")
        pipeline_result["steps"]["vworld"] = "SKIPPED"
    else:
        try:
            vworld_data = test_get_buildings(lon, lat, buffer=200)
            if vworld_data:
                features = (vworld_data.get("response", {})
                                       .get("result", {})
                                       .get("featureCollection", {})
                                       .get("features", []))
                if features:
                    props = features[0].get("properties", {})
                    pnu = (props.get("PNU") or props.get("pnu") or "")
                    bd_mgt_sn = (props.get("BD_MGT_SN")
                                 or props.get("bd_mgt_sn") or "")

                    pipeline_result["steps"]["vworld"] = {
                        "status": "OK",
                        "feature_count": len(features),
                        "pnu": pnu,
                        "bd_mgt_sn": bd_mgt_sn,
                    }
                else:
                    pipeline_result["steps"]["vworld"] = "NO_FEATURES"
            else:
                pipeline_result["steps"]["vworld"] = "FAILED"
        except Exception as e:
            pipeline_result["steps"]["vworld"] = f"ERROR: {e}"
            pipeline_result["errors"].append(f"vworld: {e}")
            traceback.print_exc()

    # ─── Step 2: PNU 파싱 ──────────────────────────────
    print_header("Pipeline Step 2/6: PNU 파싱")

    parsed = None
    if pnu and len(pnu) == 19:
        parsed = parse_pnu(pnu)
        print(f"  PNU:         {pnu}")
        print(f"  시군구코드:  {parsed['sigungu_cd']}")
        print(f"  법정동코드:  {parsed['bjdong_cd']}")
        print(f"  본번:        {parsed['main_no']}")
        print(f"  부번:        {parsed['sub_no']}")
        print(f"  지번:        {parsed['jibun_full']}")
        pipeline_result["linkage"]["parsed_pnu"] = parsed
        print_check("PNU 파싱 성공", True)
    elif pnu:
        print(f"  PNU 길이 비정상: {pnu} ({len(pnu)}자리)")
        print_check("PNU 파싱", False, f"19자리 아님: {len(pnu)}자리")
    else:
        print("  PNU 없음 — Vworld에서 획득 실패")
        print("  → 수동 테스트 파라미터로 진행")
        # 폴백: 종로구 기본값
        parsed = {
            "sigungu_cd": "11110",
            "bjdong_cd": "10100",
            "main_no": "0001",
            "sub_no": "0000",
            "jibun_full": "1",
        }
        pipeline_result["linkage"]["parsed_pnu"] = parsed
        pipeline_result["linkage"]["note"] = "PNU 수동 폴백 (종로구 기본값)"
        print_check("수동 폴백 파라미터 사용", True, "종로구 11110/10100")

    # ─── Step 3: 실거래가 ──────────────────────────────
    print_header("Pipeline Step 3/6: 실거래가 API 조회")

    if not DATA_GO_KR_API_KEY:
        print("  [SKIP] DATA_GO_KR_API_KEY 미설정")
        pipeline_result["steps"]["realtrade"] = "SKIPPED"
    elif parsed:
        try:
            trade_data = test_apt_trade(
                lawd_cd=parsed["sigungu_cd"],
                deal_ymd=deal_ymd,
            )
            if trade_data and trade_data.get("items"):
                pipeline_result["steps"]["realtrade"] = {
                    "status": "OK",
                    "total_count": trade_data.get("totalCount", "0"),
                    "sample_item": trade_data["items"][0] if trade_data["items"] else {},
                }
            else:
                pipeline_result["steps"]["realtrade"] = "NO_DATA"
        except Exception as e:
            pipeline_result["steps"]["realtrade"] = f"ERROR: {e}"
            pipeline_result["errors"].append(f"realtrade: {e}")
            traceback.print_exc()

    # ─── Step 4: 건축물대장 ────────────────────────────
    print_header("Pipeline Step 4/6: 건축물대장 API 조회")

    if not DATA_GO_KR_API_KEY:
        print("  [SKIP] DATA_GO_KR_API_KEY 미설정")
        pipeline_result["steps"]["building_registry"] = "SKIPPED"
    elif parsed:
        try:
            bldg_data = test_title_info(
                sigungu_cd=parsed["sigungu_cd"],
                bjdong_cd=parsed["bjdong_cd"],
                bun=parsed["main_no"],
                ji=parsed["sub_no"],
            )
            if bldg_data and bldg_data.get("items"):
                pipeline_result["steps"]["building_registry"] = {
                    "status": "OK",
                    "total_count": bldg_data.get("totalCount", "0"),
                    "multi_dong": int(bldg_data.get("totalCount", "0")) > 1,
                }
            else:
                pipeline_result["steps"]["building_registry"] = "NO_DATA"
        except Exception as e:
            pipeline_result["steps"]["building_registry"] = f"ERROR: {e}"
            pipeline_result["errors"].append(f"building_registry: {e}")
            traceback.print_exc()

    # ─── Step 5: 에너지 ────────────────────────────────
    print_header("Pipeline Step 5/6: 건물에너지 API 조회")

    if not DATA_GO_KR_API_KEY:
        print("  [SKIP] DATA_GO_KR_API_KEY 미설정")
        pipeline_result["steps"]["energy"] = "SKIPPED"
    elif parsed:
        try:
            energy_data = test_energy_usage(
                sigungu_cd=parsed["sigungu_cd"],
                bjdong_cd=parsed["bjdong_cd"],
                bun=parsed["main_no"],
                ji=parsed["sub_no"],
                use_ymd="202401",
            )
            if energy_data and energy_data.get("items"):
                pipeline_result["steps"]["energy"] = {
                    "status": "OK",
                    "total_count": energy_data.get("totalCount", "0"),
                }
            else:
                pipeline_result["steps"]["energy"] = "NO_DATA"
        except Exception as e:
            pipeline_result["steps"]["energy"] = f"ERROR: {e}"
            pipeline_result["errors"].append(f"energy: {e}")
            traceback.print_exc()

    # ─── Step 6: 카카오맵 교차 검증 ────────────────────
    print_header("Pipeline Step 6/6: 카카오맵 교차 검증")

    if not KAKAO_REST_API_KEY:
        print("  [SKIP] KAKAO_REST_API_KEY 미설정")
        pipeline_result["steps"]["kakao"] = "SKIPPED"
    else:
        try:
            kakao_data = test_coord_to_address(lon, lat)
            if kakao_data and kakao_data.get("documents"):
                doc = kakao_data["documents"][0]
                road = doc.get("road_address", {}) or {}
                addr = doc.get("address", {}) or {}
                pipeline_result["steps"]["kakao"] = {
                    "status": "OK",
                    "road_address": road.get("address_name", ""),
                    "jibun_address": addr.get("address_name", ""),
                    "building_name": road.get("building_name", ""),
                }
            else:
                pipeline_result["steps"]["kakao"] = "NO_DATA"
        except Exception as e:
            pipeline_result["steps"]["kakao"] = f"ERROR: {e}"
            pipeline_result["errors"].append(f"kakao: {e}")
            traceback.print_exc()

    # ─── 종합 결과 ──────────────────────────────────────
    print_header("파이프라인 종합 결과")

    print(f"  건물: {label}")
    print(f"  좌표: ({lon}, {lat})")
    print()

    for step, result in pipeline_result["steps"].items():
        if isinstance(result, dict):
            status = result.get("status", "UNKNOWN")
        else:
            status = str(result)
        icon = "O" if status == "OK" else "X" if "ERROR" in status else "-"
        print(f"  [{icon}] {step:25s} → {status}")

    if pipeline_result["errors"]:
        print(f"\n  에러 목록:")
        for err in pipeline_result["errors"]:
            print(f"    - {err}")

    print(f"\n  연계 키: PNU 기반 (BD_MGT_SN은 Vworld 전용)")

    save_sample(f"pipeline_{label.replace(' ', '_')}.json", pipeline_result)
    return pipeline_result


if __name__ == "__main__":
    print("=" * 60)
    print("  데이터 연계 가능성 종합 검증 — 풀 파이프라인 테스트")
    print("=" * 60)

    # ─── 테스트 케이스 1: 서울시청 부근 (관공서/단독) ───
    print("\n\n" + "=" * 60)
    print("  케이스 1: 서울시청 부근 (관공서/상업시설)")
    print("=" * 60)
    run_full_pipeline(
        lon=126.978, lat=37.566,
        label="서울시청 부근",
    )

    # ─── 테스트 케이스 2: 강남 아파트 (집합건물) ────────
    print("\n\n" + "=" * 60)
    print("  케이스 2: 강남구 아파트 (집합건물 다동 매칭 테스트)")
    print("=" * 60)
    run_full_pipeline(
        lon=127.028, lat=37.498,
        label="강남 아파트",
    )

    # ─── PNU 파싱 단위 테스트 ──────────────────────────
    print_header("PNU 파싱 단위 테스트")

    test_pnus = [
        ("종로구 청운동 1번지",    "1111010100100010000"),
        ("강남구 역삼동 123-4",   "1168010300101230004"),
        ("마포구 합정동 100",     "1144010100100100000"),
    ]

    for label, pnu in test_pnus:
        try:
            parsed = parse_pnu(pnu)
            print(f"\n  [{label}] PNU={pnu}")
            print(f"    시군구코드: {parsed['sigungu_cd']}")
            print(f"    법정동코드: {parsed['bjdong_cd']}")
            print(f"    지번: {parsed['jibun_full']}")
            print_check(f"PNU 파싱 ({label})", True)
        except Exception as e:
            print_check(f"PNU 파싱 ({label})", False, str(e))

    print("\n\n" + "=" * 60)
    print("  전체 파이프라인 테스트 완료")
    print("=" * 60)
    print("\n  결과 파일: data_samples/pipeline_*.json")
    print("  다음 단계: 매칭 실패 케이스를 기록하여 팀에 보고")
