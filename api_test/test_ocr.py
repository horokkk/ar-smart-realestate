"""
Step 6: Google Cloud Vision API (OCR) 테스트

목적:
  - 건물 간판 텍스트 인식 → 레이캐스팅 결과 교차 검증
  - 한국어 간판 인식 정확도 확인
  - base64 이미지 → 텍스트 추출 동작 확인

API 문서: https://cloud.google.com/vision/docs/ocr

체크리스트:
  [ ] 무료 1,000건/월 (데모에 충분)
  [ ] 한국어 간판 인식률
  [ ] base64 이미지 → 텍스트 추출 동작 확인
  [ ] TEXT_DETECTION vs DOCUMENT_TEXT_DETECTION 비교
"""

import json
import base64
import urllib.request
import urllib.parse
from pathlib import Path
from config import (
    GOOGLE_VISION_API_KEY,
    save_sample, print_header, print_check, check_api_key,
)


VISION_API_URL = "https://vision.googleapis.com/v1/images:annotate"


def _create_test_image_b64() -> str:
    """
    테스트용 간단한 이미지 생성 (1x1 흰색 PNG)
    실제 테스트 시에는 건물 간판 사진 사용

    사용법:
      실제 간판 사진으로 테스트하려면:
      test_ocr_from_file("path/to/building_sign.jpg")
    """
    # 최소 1x1 흰색 PNG (89 bytes)
    png_bytes = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
        b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
        b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    return base64.b64encode(png_bytes).decode("ascii")


def test_ocr_from_base64(image_b64: str, label: str = "테스트 이미지"):
    """
    Vision API TEXT_DETECTION 호출

    Args:
      image_b64: base64 인코딩된 이미지 문자열
      label: 로그용 레이블
    """
    print_header(f"Google Vision OCR 테스트 ({label})")

    if not check_api_key("Google Vision", GOOGLE_VISION_API_KEY):
        return None

    # 요청 본문
    request_body = {
        "requests": [
            {
                "image": {"content": image_b64},
                "features": [
                    {"type": "TEXT_DETECTION", "maxResults": 10},
                ],
                "imageContext": {
                    "languageHints": ["ko", "en"],  # 한국어 우선
                },
            }
        ]
    }

    url = f"{VISION_API_URL}?key={GOOGLE_VISION_API_KEY}"
    print(f"  요청 URL: {VISION_API_URL}?key=****")
    print(f"  이미지 크기: {len(image_b64)} chars (base64)")

    try:
        data = json.dumps(request_body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        print(f"  HTTP {e.code}: {body[:300]}")
        print_check("API 호출", False)
        return None
    except Exception as e:
        print(f"  요청 오류: {e}")
        return None

    # 응답 분석
    responses = result.get("responses", [])
    if not responses:
        print_check("응답", False, "빈 응답")
        return None

    r0 = responses[0]

    # 에러 체크
    error = r0.get("error")
    if error:
        print(f"  API 에러: {error.get('message', '')}")
        print_check("OCR 성공", False, error.get("message", ""))
        return result

    # 텍스트 어노테이션
    annotations = r0.get("textAnnotations", [])
    print_check("텍스트 감지", len(annotations) > 0,
                f"{len(annotations)}개 텍스트 영역")

    if annotations:
        # 첫 번째는 전체 텍스트
        full_text = annotations[0].get("description", "")
        print(f"\n  --- 인식된 전체 텍스트 ---")
        for line in full_text.strip().split("\n"):
            print(f"    {line}")

        # 개별 단어/영역
        print(f"\n  --- 개별 텍스트 영역 (처음 5개) ---")
        for ann in annotations[1:6]:
            text = ann.get("description", "")
            locale = ann.get("locale", "")
            vertices = ann.get("boundingPoly", {}).get("vertices", [])
            pos = ""
            if vertices:
                x0 = vertices[0].get("x", 0)
                y0 = vertices[0].get("y", 0)
                pos = f" @ ({x0}, {y0})"
            lang = f" [{locale}]" if locale else ""
            print(f"    \"{text}\"{lang}{pos}")

        # 한국어 비율 확인
        full_text_decoded = full_text.strip()
        korean_chars = sum(1 for c in full_text_decoded
                          if '\uac00' <= c <= '\ud7a3')
        total_chars = len(full_text_decoded.replace(" ", "").replace("\n", ""))
        if total_chars > 0:
            ratio = korean_chars / total_chars * 100
            print(f"\n  한국어 비율: {korean_chars}/{total_chars} ({ratio:.1f}%)")

    else:
        print("  텍스트가 감지되지 않았습니다.")
        print("  (흰색 테스트 이미지는 정상 — 실제 간판 사진으로 테스트하세요)")

    # fullTextAnnotation (구조화된 텍스트)
    full_ann = r0.get("fullTextAnnotation")
    if full_ann:
        pages = full_ann.get("pages", [])
        print_check("구조화 텍스트 (fullTextAnnotation)", True,
                     f"{len(pages)}페이지")

    save_sample("ocr_result.json", result)
    return result


def test_ocr_from_file(filepath: str):
    """
    이미지 파일로 OCR 테스트

    Args:
      filepath: 이미지 파일 경로 (.jpg, .png 등)
    """
    path = Path(filepath)
    if not path.exists():
        print(f"  파일 없음: {filepath}")
        return None

    with open(path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("ascii")

    return test_ocr_from_base64(image_b64, label=path.name)


def test_ocr_from_url(image_url: str):
    """
    이미지 URL로 OCR 테스트 (GCS URI 또는 공개 URL)
    """
    print_header(f"Google Vision OCR URL 테스트")

    if not check_api_key("Google Vision", GOOGLE_VISION_API_KEY):
        return None

    request_body = {
        "requests": [
            {
                "image": {"source": {"imageUri": image_url}},
                "features": [
                    {"type": "TEXT_DETECTION", "maxResults": 10},
                ],
                "imageContext": {
                    "languageHints": ["ko", "en"],
                },
            }
        ]
    }

    url = f"{VISION_API_URL}?key={GOOGLE_VISION_API_KEY}"

    try:
        data = json.dumps(request_body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        annotations = (result.get("responses", [{}])[0]
                             .get("textAnnotations", []))
        if annotations:
            print(f"  인식 텍스트: {annotations[0].get('description', '')[:200]}")
        print_check("URL OCR", len(annotations) > 0,
                     f"{len(annotations)}개 영역")

        save_sample("ocr_url_result.json", result)
        return result

    except Exception as e:
        print(f"  오류: {e}")
        return None


if __name__ == "__main__":
    print("Google Cloud Vision OCR 테스트 시작\n")

    # 1) 기본 동작 테스트 (빈 이미지)
    test_b64 = _create_test_image_b64()
    test_ocr_from_base64(test_b64, "빈 테스트 이미지 (동작 확인용)")

    # 2) 실제 간판 사진 테스트
    #    아래 경로를 실제 간판 사진으로 변경
    #    test_ocr_from_file("sample_building_sign.jpg")

    print("\n\n테스트 완료.")
    print("참고: 무료 1,000건/월, 실제 간판 사진으로 한국어 인식률 확인 필요")
