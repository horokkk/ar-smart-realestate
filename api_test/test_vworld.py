"""
Step 1: Vworld GIS건물통합정보 API 테스트

목적:
  - 건물 폴리곤(다각형 좌표) 획득
  - BD_MGT_SN(건물관리번호) + PNU(필지고유번호) 확인
  - 반경 기반 건물 검색 가능 여부 확인

API 문서: https://www.vworld.kr/dev/v4dv_2ddataguide2_s001.do

체크리스트:
  [ ] API 키 발급 성공
  [ ] GeoJSON 형태로 폴리곤 좌표 반환
  [ ] BD_MGT_SN (25자리 건물관리번호) 포함
  [ ] PNU (19자리 필지고유번호) 포함
  [ ] 반경 기반 검색 가능 (geomFilter + buffer)
  [ ] 일일 호출 제한 확인
"""

import json
import urllib.request
import urllib.parse
from config import (
    VWORLD_API_KEY, DEFAULT_LON, DEFAULT_LAT,
    save_sample, print_header, print_check, check_api_key,
)


def test_get_buildings(lon: float = DEFAULT_LON, lat: float = DEFAULT_LAT,
                       buffer: int = 500):
    """
    GIS건물통합정보 조회 — 특정 좌표 반경 내 건물 폴리곤

    Vworld 2D 데이터 API 사용
    레이어: LT_C_AISRESC (GIS건물통합정보)
    ※ 레이어명이 다를 경우 아래 대안도 테스트:
       - LT_C_AISRESC
       - LT_C_UISRESC
       - LT_C_SPBD (공간정보 건물)
    """
    print_header("Vworld GIS건물통합정보 API 테스트")

    if not check_api_key("Vworld", VWORLD_API_KEY):
        return None

    # ─── 메인 요청: GIS건물통합정보 ─────────────────────
    # 여러 레이어명 후보를 시도
    layer_candidates = [
        "LT_C_AISRESC",     # GIS건물통합정보 (가장 유력)
        "LT_C_SPBD",        # 공간정보 건물
        "LT_C_UISRESC",     # 도시지역건물정보
    ]

    result = None
    used_layer = None

    for layer in layer_candidates:
        print(f"\n  레이어 시도: {layer}")
        params = {
            "key": VWORLD_API_KEY,
            "service": "data",
            "request": "GetFeature",
            "data": layer,
            "geomFilter": f"POINT({lon} {lat})",
            "buffer": str(buffer),
            "crs": "EPSG:4326",
            "size": "10",           # 최대 반환 수
            "format": "json",
            "geometry": "true",     # 폴리곤 좌표 포함
            "attribute": "true",    # 속성 정보 포함
        }

        url = "http://api.vworld.kr/req/data?" + urllib.parse.urlencode(params)
        print(f"  요청 URL: {url[:120]}...")

        try:
            req = urllib.request.Request(url)
            req.add_header("Referer", "http://localhost")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            status = data.get("response", {}).get("status", "UNKNOWN")
            print(f"  응답 상태: {status}")

            if status == "OK":
                result = data
                used_layer = layer
                break
            else:
                error_msg = data.get("response", {}).get("error", {}).get("text", "")
                print(f"  실패 사유: {error_msg}")

        except Exception as e:
            print(f"  요청 오류: {e}")

    if result is None:
        print_check("건물 폴리곤 조회", False, "모든 레이어 후보 실패")
        return None

    # ─── 응답 분석 ──────────────────────────────────────
    print(f"\n  사용된 레이어: {used_layer}")

    features = (result.get("response", {})
                      .get("result", {})
                      .get("featureCollection", {})
                      .get("features", []))

    print_check("건물 조회 성공", len(features) > 0,
                f"{len(features)}개 건물 반환")

    if not features:
        save_sample("vworld_empty_response.json", result)
        return result

    # 첫 번째 건물 분석
    f0 = features[0]
    props = f0.get("properties", {})
    geom = f0.get("geometry", {})

    print(f"\n  --- 첫 번째 건물 상세 ---")
    print(f"  속성 필드: {list(props.keys())}")

    # BD_MGT_SN 확인 (여러 필드명 후보)
    bd_mgt_sn = (props.get("BD_MGT_SN")
                 or props.get("bd_mgt_sn")
                 or props.get("BDMGT_SN")
                 or props.get("bdMgtSn")
                 or "")
    print_check("BD_MGT_SN 포함", bool(bd_mgt_sn),
                f"값: {bd_mgt_sn}" if bd_mgt_sn else "필드 없음")
    if bd_mgt_sn:
        print_check("BD_MGT_SN 25자리", len(bd_mgt_sn) == 25,
                     f"{len(bd_mgt_sn)}자리")

    # PNU 확인
    pnu = props.get("PNU") or props.get("pnu") or ""
    print_check("PNU 포함", bool(pnu),
                f"값: {pnu}" if pnu else "필드 없음")
    if pnu:
        print_check("PNU 19자리", len(pnu) == 19,
                     f"{len(pnu)}자리")

    # 건물명
    bld_nm = (props.get("BLD_NM") or props.get("buld_nm")
              or props.get("BULD_NM") or "")
    print(f"  건물명: {bld_nm or '(없음)'}")

    # geometry 타입
    geom_type = geom.get("type", "")
    print_check("폴리곤 geometry", geom_type in ("Polygon", "MultiPolygon"),
                f"type={geom_type}")

    if geom.get("coordinates"):
        coord_sample = str(geom["coordinates"])[:200]
        print(f"  좌표 샘플: {coord_sample}...")

    # ─── 전체 속성 필드 덤프 ────────────────────────────
    print(f"\n  --- 전체 속성 값 ---")
    for k, v in props.items():
        print(f"    {k}: {v}")

    # ─── 저장 ──────────────────────────────────────────
    save_sample("vworld_buildings.json", result)

    # ─── 요약 ──────────────────────────────────────────
    print_header("Vworld 테스트 요약")
    print(f"  레이어: {used_layer}")
    print(f"  반환 건물 수: {len(features)}")
    print(f"  BD_MGT_SN 존재: {'O' if bd_mgt_sn else 'X'}")
    print(f"  PNU 존재: {'O' if pnu else 'X'}")
    print(f"  Geometry 타입: {geom_type}")
    print(f"  참고: 일일 호출 제한은 Vworld 마이페이지에서 확인")

    return result


def test_layer_list():
    """Vworld에서 사용 가능한 레이어 목록 조회"""
    print_header("Vworld 레이어 목록 조회")

    if not check_api_key("Vworld", VWORLD_API_KEY):
        return None

    params = {
        "key": VWORLD_API_KEY,
        "service": "data",
        "request": "GetLayerList",
        "category": "건물",
        "format": "json",
    }

    url = "http://api.vworld.kr/req/data?" + urllib.parse.urlencode(params)
    print(f"  요청 URL: {url[:120]}...")

    try:
        req = urllib.request.Request(url)
        req.add_header("Referer", "http://localhost")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        save_sample("vworld_layer_list.json", data)
        print(f"  응답: {json.dumps(data, ensure_ascii=False)[:500]}")
        return data
    except Exception as e:
        print(f"  오류: {e}")
        return None


if __name__ == "__main__":
    print("Vworld GIS건물통합정보 API 테스트 시작\n")
    print(f"테스트 좌표: ({DEFAULT_LON}, {DEFAULT_LAT}) — 서울시청 부근")
    print(f"검색 반경: 500m")

    test_layer_list()
    test_get_buildings()

    print("\n\n테스트 완료. data_samples/ 폴더에서 응답 JSON을 확인하세요.")
