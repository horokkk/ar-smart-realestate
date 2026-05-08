"""
Step 3: 건축물대장 API 테스트

목적:
  - 건물의 법적 정보 조회 (용도, 면적, 위반건축물 여부, 사용승인일)
  - PNU(시군구코드 + 법정동코드 + 번 + 지) 기반 연계 테스트
  - 집합건물(아파트) 1필지 다동 매칭 문제 확인

API 문서: https://www.data.go.kr/data/15044713/openapi.do

체크리스트:
  [ ] mgmBldrgstPk (건축물대장 자체 PK) 확인
  [ ] BD_MGT_SN 미포함 확인 → PNU로 간접 연계
  [ ] 위반건축물 이력 조회 가능 여부
  [ ] 아파트(집합건물) 1필지 다동 → 1:N 매칭 문제 확인
  [ ] 일일 1,000회 제한 확인
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
# 건축물대장 기본개요 (표제부)
TITLE_URL = "http://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
# 건축물대장 총괄표제부
RECAP_URL = "http://apis.data.go.kr/1613000/BldRgstHubService/getBrRecapTitleInfo"
# 건축물대장 전유공용면적
AREA_URL = "http://apis.data.go.kr/1613000/BldRgstHubService/getBrExposPubuseAreaInfo"


def _fetch_xml(url: str, params: dict) -> ET.Element | None:
    """공공데이터 API 호출 (XML 파싱)"""
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
    """XML Element → dict"""
    return {child.tag: child.text for child in element}


def test_title_info(sigungu_cd: str, bjdong_cd: str,
                    bun: str = "", ji: str = ""):
    """
    건축물대장 표제부 조회

    파라미터:
      sigungu_cd: 시군구코드 5자리
      bjdong_cd:  법정동코드 5자리
      bun:        본번 (4자리, 0 패딩)
      ji:         부번 (4자리, 0 패딩)
    """
    print_header("건축물대장 표제부 조회 테스트")

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

    print(f"  시군구코드: {sigungu_cd}")
    print(f"  법정동코드: {bjdong_cd}")
    print(f"  본번: {bun or '(전체)'}")
    print(f"  부번: {ji or '(전체)'}")

    root = _fetch_xml(TITLE_URL, params)
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
        return None

    item0 = _xml_to_dict(items[0])
    print(f"\n  --- 첫 번째 건물 상세 ---")
    print(f"  응답 필드: {list(item0.keys())}")

    # 핵심 필드 확인
    field_checks = {
        "건축물대장PK": ["mgmBldrgstPk"],
        "건물명": ["bldNm"],
        "주용도코드명": ["mainPurpsCdNm"],
        "기타용도": ["etcPurps"],
        "대지면적": ["platArea"],
        "건축면적": ["archArea"],
        "연면적": ["totArea"],
        "용적률": ["vlRat"],
        "건폐율": ["bcRat"],
        "층수(지상)": ["grndFlrCnt"],
        "층수(지하)": ["ugrndFlrCnt"],
        "사용승인일": ["useAprDay"],
        "건축년도": ["archGbCdNm"],
        "위반건축물여부": ["bylotCnt", "vltnBldYn"],
        "동명칭": ["dongNm"],
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

    # 전체 필드 덤프
    print(f"\n  --- 전체 필드 ---")
    for k, v in item0.items():
        print(f"    {k}: {v}")

    # 집합건물(아파트) 1:N 문제 확인
    if int(total_count) > 1:
        dong_names = set()
        for item in items:
            d = _xml_to_dict(item)
            dong_nm = d.get("dongNm", "")
            if dong_nm:
                dong_names.add(dong_nm)
        if dong_names:
            print(f"\n  --- 1필지 다동 현황 (집합건물) ---")
            print(f"  동 이름 목록: {sorted(dong_names)}")
            print(f"  동 수: {len(dong_names)}개")
            print_check("집합건물 1:N 매칭 문제", True,
                        "동 이름 텍스트 매칭 필요 (~90% 매칭률)")

    # 저장
    all_items = [_xml_to_dict(item) for item in items]
    save_data = {
        "api": "BldRgstHubService/getBrTitleInfo",
        "params": {
            "sigunguCd": sigungu_cd,
            "bjdongCd": bjdong_cd,
            "bun": bun,
            "ji": ji,
        },
        "totalCount": total_count,
        "items": all_items,
    }
    save_sample("building_registry_title.json", save_data)

    return save_data


def test_from_pnu(pnu: str):
    """PNU에서 파라미터 추출 → 건축물대장 조회"""
    print_header("PNU → 건축물대장 연계 테스트")

    parsed = parse_pnu(pnu)
    print(f"  PNU: {pnu}")
    print(f"  → sigunguCd: {parsed['sigungu_cd']}")
    print(f"  → bjdongCd:  {parsed['bjdong_cd']}")
    print(f"  → bun:       {parsed['main_no']}")
    print(f"  → ji:        {parsed['sub_no']}")

    return test_title_info(
        sigungu_cd=parsed["sigungu_cd"],
        bjdong_cd=parsed["bjdong_cd"],
        bun=parsed["main_no"],
        ji=parsed["sub_no"],
    )


if __name__ == "__main__":
    print("건축물대장 API 테스트 시작\n")

    # 1) 종로구 기본 테스트
    test_title_info(sigungu_cd="11110", bjdong_cd="10100")

    # 2) PNU 연계 테스트
    sample_pnu = "1111010100100010000"
    print(f"\n\n--- PNU 연계 테스트 (샘플: {sample_pnu}) ---")
    test_from_pnu(sample_pnu)

    print("\n\n테스트 완료.")
