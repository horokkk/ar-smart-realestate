"""
Step 4: 건물에너지사용량 API 테스트

목적:
  - ESG 지표 조회 — 에너지 효율 등급, 전기/가스 사용량
  - 간접 탄소 배출량 산출 가능 여부 확인
  - PNU(시군구코드 + 법정동코드 + 번 + 지) 기반 연계 테스트

API 문서: https://www.data.go.kr/data/15073203/openapi.do

체크리스트:
  [ ] 에너지 사용량 (kWh) 반환 확인
  [ ] BD_MGT_SN 미포함 → PNU 구성요소로 연계
  [ ] 데이터 갱신 주기 (월별 집계)
  [ ] 모든 건물에 데이터가 있는지 (커버리지)
"""

import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from config import (
    DATA_GO_KR_API_KEY,
    save_sample, print_header, print_check, check_api_key, parse_pnu,
)


# ─── 엔드포인트 ────────────────────────────────────────────
# 건축HUB 건물에너지정보 서비스
ENERGY_URL = "https://apis.data.go.kr/1613000/BldEngyHubService/getBldEngyInfo"


def _fetch_xml(url: str, params: dict) -> ET.Element | None:
    """공공데이터 API 호출"""
    full_url = url + "?" + urllib.parse.urlencode(params)
    print(f"  요청 URL: {full_url[:150]}...")

    try:
        req = urllib.request.Request(full_url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")

        if raw.strip().startswith("{"):
            data = json.loads(raw)
            print(f"  JSON 에러 응답: {data}")
            return None

        return ET.fromstring(raw)

    except Exception as e:
        print(f"  요청 오류: {e}")
        return None


def _xml_to_dict(element: ET.Element) -> dict:
    return {child.tag: child.text for child in element}


def test_energy_usage(sigungu_cd: str, bjdong_cd: str,
                      bun: str = "", ji: str = "",
                      use_ymd: str = "202401"):
    """
    건물에너지사용량 조회

    파라미터:
      sigungu_cd: 시군구코드 5자리
      bjdong_cd:  법정동코드 5자리
      bun:        본번
      ji:         부번
      use_ymd:    사용년월 (YYYYMM)
    """
    print_header("건물에너지사용량 API 테스트")

    if not check_api_key("공공데이터포털", DATA_GO_KR_API_KEY):
        return None

    params = {
        "serviceKey": DATA_GO_KR_API_KEY,
        "sigunguCd": sigungu_cd,
        "bjdongCd": bjdong_cd,
        "pageNo": "1",
        "numOfRows": "10",
    }
    if bun:
        params["bun"] = bun
    if ji:
        params["ji"] = ji
    if use_ymd:
        params["useYmd"] = use_ymd

    print(f"  시군구코드: {sigungu_cd}")
    print(f"  법정동코드: {bjdong_cd}")
    print(f"  본번: {bun or '(전체)'}")
    print(f"  부번: {ji or '(전체)'}")
    print(f"  사용년월: {use_ymd}")

    root = _fetch_xml(ENERGY_URL, params)
    if root is None:
        print_check("API 호출", False)
        return None

    result_code = root.findtext(".//resultCode") or ""
    result_msg = root.findtext(".//resultMsg") or ""
    total_count = root.findtext(".//totalCount") or "0"

    print_check("API 응답", result_code == "00",
                f"코드={result_code}, 메시지={result_msg}")
    print(f"  총 건수: {total_count}")

    items = root.findall(".//item")
    print_check("데이터 반환", len(items) > 0,
                f"{len(items)}건")

    if not items:
        print("\n  [참고] 에너지 데이터가 없을 수 있는 이유:")
        print("    - 소규모 건물은 데이터 미집계")
        print("    - 사용년월이 아직 집계 안 된 기간")
        print("    - 해당 필지에 에너지 보고 의무 건물 없음")
        return None

    item0 = _xml_to_dict(items[0])
    print(f"\n  --- 첫 번째 건물 에너지 데이터 ---")
    print(f"  응답 필드: {list(item0.keys())}")

    # 핵심 필드 확인
    field_checks = {
        "전기사용량(kWh)": ["elecUsgQty", "elctrgUseQty", "elecUseQty"],
        "가스사용량(m³)": ["gasUsgQty", "gasUseQty"],
        "에너지합계": ["totUsgQty", "totEnergyUseQty"],
        "건물명": ["bldNm"],
        "사용년월": ["useYmd", "useYm"],
        "시군구코드": ["sigunguCd"],
        "법정동코드": ["bjdongCd"],
    }

    found_fields = {}
    for label, candidates in field_checks.items():
        value = None
        used_key = None
        for c in candidates:
            if c in item0 and item0[c]:
                value = item0[c]
                used_key = c
                break
        if value is not None:
            print_check(label, True, f"{used_key}={value}")
            found_fields[label] = value
        else:
            print_check(label, False, "필드 없음 또는 null")

    # BD_MGT_SN 미포함 확인
    has_bd_mgt_sn = any(
        "bdmgt" in k.lower().replace("_", "")
        for k in item0.keys()
    )
    print_check("BD_MGT_SN 미포함 (예상대로)", not has_bd_mgt_sn,
                "포함됨!" if has_bd_mgt_sn else "확인 — PNU 기반 연계 필요")

    # 탄소 배출량 간접 계산 가능성
    elec = found_fields.get("전기사용량(kWh)")
    if elec:
        try:
            elec_val = float(elec)
            # 전기 탄소배출계수: 0.4747 tCO2/MWh (한국, 2023)
            co2_kg = elec_val * 0.0004747
            print(f"\n  [ESG 계산 예시]")
            print(f"    전기 {elec_val} kWh × 0.4747 tCO2/MWh")
            print(f"    = 약 {co2_kg:.2f} kg CO2")
        except ValueError:
            pass

    # 전체 필드 덤프
    print(f"\n  --- 전체 필드 ---")
    for k, v in item0.items():
        print(f"    {k}: {v}")

    # 저장
    all_items = [_xml_to_dict(item) for item in items]
    save_data = {
        "api": "BldEngyService/getBldEngyInfo",
        "params": {
            "sigunguCd": sigungu_cd,
            "bjdongCd": bjdong_cd,
            "bun": bun,
            "ji": ji,
            "useYmd": use_ymd,
        },
        "totalCount": total_count,
        "items": all_items,
    }
    save_sample("energy_usage.json", save_data)

    return save_data


def test_from_pnu(pnu: str, use_ymd: str = "202401"):
    """PNU → 에너지 조회 연계 테스트"""
    print_header("PNU → 에너지 사용량 연계 테스트")

    parsed = parse_pnu(pnu)
    print(f"  PNU: {pnu}")
    print(f"  → sigunguCd: {parsed['sigungu_cd']}")
    print(f"  → bjdongCd:  {parsed['bjdong_cd']}")
    print(f"  → bun:       {parsed['main_no']}")
    print(f"  → ji:        {parsed['sub_no']}")

    return test_energy_usage(
        sigungu_cd=parsed["sigungu_cd"],
        bjdong_cd=parsed["bjdong_cd"],
        bun=parsed["main_no"],
        ji=parsed["sub_no"],
        use_ymd=use_ymd,
    )


def test_coverage():
    """
    커버리지 테스트 — 여러 지역 / 건물 유형으로 데이터 존재 확인

    소규모 건물, 비주거 등에서 데이터 누락 가능
    """
    print_header("에너지 데이터 커버리지 테스트")

    test_cases = [
        ("서울 종로구 (아파트 밀집)", "11110", "10100"),
        ("서울 강남구 (상업 빌딩)", "11680", "10300"),
        ("서울 마포구 (주거+상업)", "11440", "10100"),
    ]

    results = {}
    for label, sigungu, bjdong in test_cases:
        print(f"\n  [{label}]")
        params = {
            "serviceKey": DATA_GO_KR_API_KEY,
            "sigunguCd": sigungu,
            "bjdongCd": bjdong,
            "useYmd": "202401",
            "pageNo": "1",
            "numOfRows": "1",
        }
        root = _fetch_xml(ENERGY_URL, params)
        if root:
            count = root.findtext(".//totalCount") or "0"
            print_check(label, int(count) > 0, f"{count}건")
            results[label] = count
        else:
            print_check(label, False, "조회 실패")
            results[label] = "ERROR"

    save_sample("energy_coverage.json", results)
    return results


if __name__ == "__main__":
    print("건물에너지사용량 API 테스트 시작\n")

    # 1) 기본 조회 (서울 종로구)
    test_energy_usage(sigungu_cd="11110", bjdong_cd="10100")

    # 2) PNU 연계 테스트
    sample_pnu = "1111010100100010000"
    test_from_pnu(sample_pnu)

    # 3) 커버리지 테스트
    test_coverage()

    print("\n\n테스트 완료.")
