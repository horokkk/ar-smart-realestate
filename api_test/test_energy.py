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
ELEC_URL = "https://apis.data.go.kr/1613000/BldEngyHubService/getBeElctyUsgInfo"
GAS_URL = "https://apis.data.go.kr/1613000/BldEngyHubService/getBeGasUsgInfo"


def _fetch_xml(url: str, params: dict) -> ET.Element | None:
    """공공데이터 API 호출"""
    full_url = url + "?" + urllib.parse.urlencode(params)
    print(f"  요청 URL: {full_url[:150]}...")

    try:
        req = urllib.request.Request(full_url)
        req.add_unredirected_header("Accept-Encoding", "")
        req.add_header("Accept", "*/*")
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


def _test_one_energy(label: str, url: str, sigungu_cd: str, bjdong_cd: str,
                     bun: str, ji: str, use_ym: str,
                     plat_gb_cd: str = "0") -> dict | None:
    """전기 또는 가스 단일 조회"""
    print_header(f"{label} 조회")

    params = {
        "serviceKey": DATA_GO_KR_API_KEY,
        "sigunguCd": sigungu_cd,
        "bjdongCd": bjdong_cd,
        "platGbCd": plat_gb_cd,
        "pageNo": "1",
        "numOfRows": "10",
    }
    if bun:
        params["bun"] = bun
    if ji:
        params["ji"] = ji
    if use_ym:
        params["useYm"] = use_ym

    root = _fetch_xml(url, params)
    if root is None:
        print_check(f"{label} 호출", False)
        return None

    result_code = root.findtext(".//resultCode") or ""
    result_msg = root.findtext(".//resultMsg") or ""
    total_count = root.findtext(".//totalCount") or "0"

    print_check("API 응답", result_code == "00",
                f"코드={result_code}, 메시지={result_msg}")
    print(f"  총 건수: {total_count}")

    items = root.findall(".//item")
    print_check("데이터 반환", len(items) > 0, f"{len(items)}건")

    if not items:
        return None

    item0 = _xml_to_dict(items[0])
    print(f"\n  응답 필드: {list(item0.keys())}")

    # 전체 필드 덤프
    for k, v in item0.items():
        print(f"    {k}: {v}")

    all_items = [_xml_to_dict(item) for item in items]
    return {"totalCount": total_count, "items": all_items}


def test_energy_usage(sigungu_cd: str, bjdong_cd: str,
                      bun: str = "", ji: str = "",
                      use_ym: str = "202401"):
    """
    건물에너지사용량 조회 (전기 + 가스)

    파라미터:
      sigungu_cd: 시군구코드 5자리
      bjdong_cd:  법정동코드 5자리
      bun:        본번
      ji:         부번
      use_ym:     사용년월 (YYYYMM)
    """
    print_header("건물에너지사용량 API 테스트")

    if not check_api_key("공공데이터포털", DATA_GO_KR_API_KEY):
        return None

    print(f"  시군구코드: {sigungu_cd}")
    print(f"  법정동코드: {bjdong_cd}")
    print(f"  본번: {bun or '(전체)'}")
    print(f"  부번: {ji or '(전체)'}")
    print(f"  사용년월: {use_ym}")

    # 전기사용량 조회
    elec_result = _test_one_energy(
        "전기사용량 (getBeElctyUsgInfo)", ELEC_URL,
        sigungu_cd, bjdong_cd, bun, ji, use_ym)

    # 가스사용량 조회
    gas_result = _test_one_energy(
        "가스사용량 (getBeGasUsgInfo)", GAS_URL,
        sigungu_cd, bjdong_cd, bun, ji, use_ym)

    # 탄소 배출량 간접 계산
    if elec_result and elec_result["items"]:
        item0 = elec_result["items"][0]
        for key in ["useQty", "elecUsgQty", "elctrgUseQty", "elecUseQty"]:
            if key in item0 and item0[key]:
                try:
                    elec_val = float(item0[key])
                    co2_kg = elec_val * 0.0004747
                    print(f"\n  [ESG 계산 예시]")
                    print(f"    전기 {elec_val} kWh × 0.4747 tCO2/MWh")
                    print(f"    = 약 {co2_kg:.2f} kg CO2")
                except ValueError:
                    pass
                break

    # 저장
    save_data = {
        "api": "BldEngyHubService",
        "params": {
            "sigunguCd": sigungu_cd, "bjdongCd": bjdong_cd,
            "bun": bun, "ji": ji, "useYm": use_ym,
        },
        "electricity": elec_result,
        "gas": gas_result,
    }
    save_sample("energy_usage.json", save_data)

    return save_data


def test_from_pnu(pnu: str, use_ym: str = "202401"):
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
        use_ym=use_ym,
    )


def test_coverage():
    """
    커버리지 테스트 — 여러 지역 / 건물 유형으로 데이터 존재 확인

    소규모 건물, 비주거 등에서 데이터 누락 가능
    """
    print_header("에너지 데이터 커버리지 테스트")

    test_cases = [
        ("서울 종로구 청운동 1 (아파트)", "11110", "10100", "0001", "0000"),
        ("서울 강남구 역삼동 830 (오피스)", "11680", "10300", "0830", "0000"),
        ("서울 마포구 아현동 618 (주거)", "11440", "10100", "0618", "0000"),
    ]

    results = {}
    for label, sigungu, bjdong, bun, ji in test_cases:
        print(f"\n  [{label}]")
        params = {
            "serviceKey": DATA_GO_KR_API_KEY,
            "sigunguCd": sigungu,
            "bjdongCd": bjdong,
            "platGbCd": "0",
            "bun": bun,
            "ji": ji,
            "useYm": "202401",
            "pageNo": "1",
            "numOfRows": "1",
        }
        root = _fetch_xml(ELEC_URL, params)
        if root is not None:
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

    # 1) 특정 건물 조회 (서울 종로구 청운동 1번지)
    test_energy_usage(sigungu_cd="11110", bjdong_cd="10100",
                      bun="0001", ji="0000")

    # 2) PNU 연계 테스트
    sample_pnu = "1111010100100010000"
    test_from_pnu(sample_pnu)

    # 3) 커버리지 테스트
    test_coverage()

    print("\n\n테스트 완료.")
