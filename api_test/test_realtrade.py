"""
Step 2: 국토교통부 실거래가 API 테스트

목적:
  - 아파트/빌라/상가 매매/전월세 실거래가 조회
  - 법정동코드(LAWD_CD) + 계약년월(DEAL_YMD)로 조회
  - PNU에서 추출한 코드로 연계 가능 여부 확인

API 문서: https://www.data.go.kr/data/15058747/openapi.do

체크리스트:
  [ ] API 키 발급 + 승인 완료
  [ ] XML/JSON 응답 정상 확인
  [ ] 거래금액, 전용면적, 아파트명, 층, 건축년도 필드 확인
  [ ] BD_MGT_SN 미포함 확인 → 법정동코드+지번으로 연계
  [ ] 일일 1,000회 제한 확인
"""

import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from config import (
    DATA_GO_KR_API_KEY, DEFAULT_LAWD_CD, DEFAULT_DEAL_YMD,
    save_sample, print_header, print_check, check_api_key, parse_pnu,
)


# ─── 엔드포인트 ────────────────────────────────────────────
# 아파트 매매 실거래 상세 자료
APT_TRADE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
# 아파트 전월세 실거래
APT_RENT_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"


def _fetch_xml(url: str, params: dict) -> ET.Element | None:
    """공공데이터 API 호출 (XML 응답 파싱)"""
    full_url = url + "?" + urllib.parse.urlencode(params)
    print(f"  요청 URL: {full_url[:150]}...")

    try:
        req = urllib.request.Request(full_url)
        req.add_unredirected_header("Accept-Encoding", "")
        req.add_header("Accept", "*/*")
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")

        # JSON으로도 파싱 시도 (에러 응답이 JSON일 수 있음)
        if raw.strip().startswith("{"):
            data = json.loads(raw)
            print(f"  JSON 에러 응답: {data}")
            return None

        root = ET.fromstring(raw)
        return root

    except Exception as e:
        print(f"  요청 오류: {e}")
        return None


def _xml_to_dict(element: ET.Element) -> dict:
    """XML Element를 dict로 변환"""
    result = {}
    for child in element:
        result[child.tag] = child.text
    return result


def test_apt_trade(lawd_cd: str = DEFAULT_LAWD_CD,
                   deal_ymd: str = DEFAULT_DEAL_YMD):
    """아파트 매매 실거래 조회 테스트"""
    print_header("국토교통부 아파트 매매 실거래가 API 테스트")

    if not check_api_key("공공데이터포털", DATA_GO_KR_API_KEY):
        return None

    params = {
        "serviceKey": DATA_GO_KR_API_KEY,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "pageNo": "1",
        "numOfRows": "10",
    }

    print(f"  법정동코드(LAWD_CD): {lawd_cd}")
    print(f"  계약년월(DEAL_YMD): {deal_ymd}")

    root = _fetch_xml(APT_TRADE_URL, params)
    if root is None:
        print_check("API 호출", False)
        return None

    # 응답 코드 확인
    result_code = root.findtext(".//resultCode") or ""
    result_msg = root.findtext(".//resultMsg") or ""
    total_count = root.findtext(".//totalCount") or "0"

    print_check("API 응답", result_code == "00",
                f"코드={result_code}, 메시지={result_msg}")
    print(f"  총 건수: {total_count}")

    # 아이템 파싱
    items = root.findall(".//item")
    print_check("데이터 반환", len(items) > 0,
                f"{len(items)}건 (10건 제한)")

    if not items:
        return None

    # 첫 번째 항목 분석
    item0 = _xml_to_dict(items[0])
    print(f"\n  --- 첫 번째 거래 상세 ---")
    print(f"  응답 필드: {list(item0.keys())}")

    # 주요 필드 확인
    field_checks = {
        "거래금액": ["dealAmount", "거래금액"],
        "전용면적": ["excluUseAr", "전용면적", "area"],
        "아파트명": ["aptNm", "아파트", "aptDong"],
        "층": ["floor", "층"],
        "건축년도": ["buildYear", "건축년도"],
        "법정동": ["umdNm", "법정동", "법정동명"],
        "지번": ["jibun", "지번"],
        "년": ["dealYear", "년"],
        "월": ["dealMonth", "월"],
    }

    found_fields = {}
    for label, candidates in field_checks.items():
        value = None
        used_key = None
        for c in candidates:
            if c in item0:
                value = item0[c]
                used_key = c
                break
        if value is not None:
            print_check(label, True, f"{used_key}={value}")
            found_fields[label] = value
        else:
            print_check(label, False, "필드 없음")

    # BD_MGT_SN 미포함 확인
    has_bd_mgt_sn = any(
        k.lower().replace("_", "") in ("bdmgtsn", "bdmgt_sn", "bd_mgt_sn")
        for k in item0.keys()
    )
    print_check("BD_MGT_SN 미포함 (예상대로)", not has_bd_mgt_sn,
                "포함됨!" if has_bd_mgt_sn else "확인 — PNU 기반 연계 필요")

    # 전체 필드 덤프
    print(f"\n  --- 전체 필드 ---")
    for k, v in item0.items():
        print(f"    {k}: {v}")

    # JSON으로 저장
    all_items = [_xml_to_dict(item) for item in items]
    save_data = {
        "api": "RTMSDataSvcAptTradeDev",
        "params": {"LAWD_CD": lawd_cd, "DEAL_YMD": deal_ymd},
        "totalCount": total_count,
        "items": all_items,
    }
    save_sample("realtrade_apt_trade.json", save_data)

    return save_data


def test_apt_rent(lawd_cd: str = DEFAULT_LAWD_CD,
                  deal_ymd: str = DEFAULT_DEAL_YMD):
    """아파트 전월세 실거래 조회 테스트"""
    print_header("국토교통부 아파트 전월세 API 테스트")

    if not check_api_key("공공데이터포털", DATA_GO_KR_API_KEY):
        return None

    params = {
        "serviceKey": DATA_GO_KR_API_KEY,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "pageNo": "1",
        "numOfRows": "5",
    }

    root = _fetch_xml(APT_RENT_URL, params)
    if root is None:
        print_check("전월세 API 호출", False)
        return None

    result_code = root.findtext(".//resultCode") or ""
    items = root.findall(".//item")
    print_check("전월세 API 응답", result_code == "00",
                f"{len(items)}건 반환")

    if items:
        item0 = _xml_to_dict(items[0])
        print(f"  필드: {list(item0.keys())}")
        all_items = [_xml_to_dict(item) for item in items]
        save_sample("realtrade_apt_rent.json", {
            "api": "RTMSDataSvcAptRent",
            "items": all_items,
        })

    return items


def test_linkage_from_pnu(pnu: str):
    """
    PNU에서 LAWD_CD 추출 → 실거래가 조회 연계 테스트

    Vworld에서 받은 PNU로 실거래가 API를 조회할 수 있는지 확인
    """
    print_header("PNU → 실거래가 연계 테스트")

    parsed = parse_pnu(pnu)
    print(f"  PNU: {pnu}")
    print(f"  시군구코드(LAWD_CD): {parsed['sigungu_cd']}")
    print(f"  법정동코드: {parsed['bjdong_cd']}")
    print(f"  지번: {parsed['jibun_full']}")
    print()
    print("  연계 방법:")
    print(f"    1. LAWD_CD={parsed['sigungu_cd']} 로 실거래가 API 조회")
    print(f"    2. 응답에서 법정동+지번으로 필터링")
    print(f"    → 법정동 텍스트매칭 + 지번 비교 필요")

    result = test_apt_trade(
        lawd_cd=parsed["sigungu_cd"],
        deal_ymd=DEFAULT_DEAL_YMD,
    )
    return result


if __name__ == "__main__":
    print("국토교통부 실거래가 API 테스트 시작\n")

    # 1) 기본 매매 조회
    test_apt_trade()

    # 2) 전월세 조회
    test_apt_rent()

    # 3) PNU 연계 테스트 (서울 종로구 샘플 PNU)
    # 실제 테스트 시 Vworld에서 받은 PNU로 교체
    sample_pnu = "1111010100100010000"  # 종로구 청운동 1번지
    print(f"\n\n--- PNU 연계 테스트 (샘플: {sample_pnu}) ---")
    test_linkage_from_pnu(sample_pnu)

    print("\n\n테스트 완료.")
