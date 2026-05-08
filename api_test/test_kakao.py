"""
Step 5: 카카오맵 API 테스트

목적:
  - 좌표 ↔ 주소 변환 (보조 역할)
  - POI(키워드) 검색
  - BD_MGT_SN → 도로명주소 추출 후 카카오맵으로 교차 검증

API 문서: https://developers.kakao.com/docs/latest/ko/local/dev-guide

체크리스트:
  [ ] Authorization: KakaoAK {KEY} 인증 동작
  [ ] 좌표 → 도로명주소/지번주소 반환
  [ ] 키워드 검색 → 건물명 매칭
  [ ] 무료 쿼터: 30만건/일
  [ ] 테스트 앱 100건/일 제한 주의
"""

import json
import urllib.request
import urllib.parse
from config import (
    KAKAO_REST_API_KEY, DEFAULT_LON, DEFAULT_LAT,
    save_sample, print_header, print_check, check_api_key,
)


# ─── 엔드포인트 ────────────────────────────────────────────
COORD_TO_ADDR_URL = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
COORD_TO_REGION_URL = "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json"
KEYWORD_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
ADDR_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/address.json"


def _kakao_request(url: str, params: dict) -> dict | None:
    """카카오 API 호출"""
    if not KAKAO_REST_API_KEY:
        print_check("카카오 API 키", False, ".env에 설정 필요")
        return None

    full_url = url + "?" + urllib.parse.urlencode(params)
    print(f"  요청 URL: {full_url[:150]}...")

    req = urllib.request.Request(full_url)
    req.add_header("Authorization", f"KakaoAK {KAKAO_REST_API_KEY}")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        print(f"  HTTP {e.code}: {body[:200]}")
        return None
    except Exception as e:
        print(f"  요청 오류: {e}")
        return None


def test_coord_to_address(lon: float = DEFAULT_LON, lat: float = DEFAULT_LAT):
    """좌표 → 주소 변환 테스트"""
    print_header("카카오 좌표→주소 변환 테스트")

    if not check_api_key("카카오", KAKAO_REST_API_KEY):
        return None

    print(f"  입력 좌표: ({lon}, {lat})")

    data = _kakao_request(COORD_TO_ADDR_URL, {"x": str(lon), "y": str(lat)})
    if data is None:
        print_check("API 호출", False)
        return None

    documents = data.get("documents", [])
    print_check("주소 반환", len(documents) > 0,
                f"{len(documents)}개 결과")

    if documents:
        doc = documents[0]

        # 도로명주소
        road = doc.get("road_address")
        if road:
            road_addr = road.get("address_name", "")
            print_check("도로명주소", True, road_addr)
            print(f"    빌딩명: {road.get('building_name', '')}")
            print(f"    우편번호: {road.get('zone_no', '')}")
        else:
            print_check("도로명주소", False, "없음")

        # 지번주소
        addr = doc.get("address")
        if addr:
            addr_name = addr.get("address_name", "")
            print_check("지번주소", True, addr_name)

            # 법정동코드 확인 (region_3depth 등)
            region1 = addr.get("region_1depth_name", "")
            region2 = addr.get("region_2depth_name", "")
            region3 = addr.get("region_3depth_name", "")
            print(f"    시도: {region1}, 시군구: {region2}, 법정동: {region3}")
        else:
            print_check("지번주소", False, "없음")

    save_sample("kakao_coord_to_addr.json", data)
    return data


def test_coord_to_region(lon: float = DEFAULT_LON, lat: float = DEFAULT_LAT):
    """좌표 → 행정구역 코드 변환 (법정동코드 포함)"""
    print_header("카카오 좌표→행정구역코드 변환 테스트")

    if not check_api_key("카카오", KAKAO_REST_API_KEY):
        return None

    data = _kakao_request(COORD_TO_REGION_URL, {"x": str(lon), "y": str(lat)})
    if data is None:
        return None

    documents = data.get("documents", [])
    for doc in documents:
        region_type = doc.get("region_type", "")
        code = doc.get("code", "")
        addr_name = doc.get("address_name", "")
        print(f"  {region_type}: {addr_name} (코드: {code})")

    print_check("행정구역코드 반환", len(documents) > 0)
    save_sample("kakao_coord_to_region.json", data)
    return data


def test_keyword_search(query: str = "서울시청"):
    """키워드(POI) 검색 테스트"""
    print_header("카카오 키워드 검색 테스트")

    if not check_api_key("카카오", KAKAO_REST_API_KEY):
        return None

    print(f"  검색어: {query}")

    data = _kakao_request(KEYWORD_SEARCH_URL, {"query": query, "size": "5"})
    if data is None:
        return None

    documents = data.get("documents", [])
    print_check("검색 결과", len(documents) > 0,
                f"{len(documents)}건")

    for i, doc in enumerate(documents[:3]):
        print(f"\n  [{i+1}] {doc.get('place_name', '')}")
        print(f"      카테고리: {doc.get('category_name', '')}")
        print(f"      주소: {doc.get('address_name', '')}")
        print(f"      도로명: {doc.get('road_address_name', '')}")
        print(f"      좌표: ({doc.get('x', '')}, {doc.get('y', '')})")
        print(f"      전화: {doc.get('phone', '')}")

    save_sample("kakao_keyword_search.json", data)
    return data


def test_address_search(address: str = "서울 종로구 세종대로 110"):
    """주소 검색 테스트 (도로명/지번 → 좌표)"""
    print_header("카카오 주소 검색 테스트")

    if not check_api_key("카카오", KAKAO_REST_API_KEY):
        return None

    print(f"  검색 주소: {address}")

    data = _kakao_request(ADDR_SEARCH_URL, {"query": address})
    if data is None:
        return None

    documents = data.get("documents", [])
    print_check("검색 결과", len(documents) > 0,
                f"{len(documents)}건")

    if documents:
        doc = documents[0]
        print(f"  주소명: {doc.get('address_name', '')}")
        print(f"  좌표: ({doc.get('x', '')}, {doc.get('y', '')})")

        road = doc.get("road_address")
        if road:
            print(f"  빌딩명: {road.get('building_name', '')}")
            print(f"  우편번호: {road.get('zone_no', '')}")

    save_sample("kakao_address_search.json", data)
    return data


if __name__ == "__main__":
    print("카카오맵 API 테스트 시작\n")

    # 1) 좌표 → 주소
    test_coord_to_address()

    # 2) 좌표 → 행정구역코드
    test_coord_to_region()

    # 3) 키워드 검색
    test_keyword_search("광화문 교보빌딩")

    # 4) 주소 검색
    test_address_search("서울 종로구 세종대로 110")

    print("\n\n테스트 완료.")
    print("참고: 무료 쿼터 30만건/일, 테스트 앱 100건/일 제한")
