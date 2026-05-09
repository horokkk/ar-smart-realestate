# 내일 이어서 할 것 (데이터 수집 조사)

## ~~1순위: Vworld 건물 폴리곤 확인~~ — PASS

- [x] Vworld 인증 문제 해결 — `Referer: http://localhost` 헤더 추가
- [x] 레이어 수정 — `LT_C_AISRESC`(항공장애물) → `LT_C_SPBD`(도로명주소 건물)
- [x] `python test_vworld.py` 재실행 → **10건 반환**
- [x] bd_mgt_sn (25자리) → `1111012000100050004000007`
- [x] PNU = bd_mgt_sn[:19] → `1111012000100050004`
- [x] MultiPolygon 좌표 확인
- [x] 도로명: 새문안로 102-2, 시군구: 종로구

## ~~2순위: 건축HUB API 참고문서 확인~~ — PASS

### 건축물대장 — PASS
- [x] 오퍼레이션명 확인: `getBrTitleInfo` (기존과 동일, 문제 아니었음)
- [x] **실제 원인**: Python urllib의 `Accept-Encoding: identity` 헤더 → 서버가 빈 응답 반환
- [x] **수정**: `req.add_unredirected_header("Accept-Encoding", "")` 추가
- [x] `python test_building_registry.py` → **358건 반환 (청운벽산빌리지 등)**

### 건물에너지 — PASS
- [x] 오퍼레이션명 확인: `getBeElctyUsgInfo` (전기), `getBeGasUsgInfo` (가스)
- [x] **실제 원인**: (1) Accept-Encoding 헤더 동일 문제, (2) 필수 파라미터 `platGbCd` 누락, (3) `useYmd` → `useYm` 수정
- [x] `python test_energy.py` → **전기 57,873 kWh / 가스 477,322 kWh 반환**

## 3순위: Google Vision OCR

- [ ] Google Cloud Console → 결제 → 결제 계정 연결 (카드 등록)
- [ ] `python test_ocr.py` 재실행
- [ ] 실제 건물 간판 사진으로 한국어 인식 테스트

## 4순위: 풀 파이프라인 테스트

> Vworld + 건축물대장 + 에너지 다 되면 실행

- [ ] `python test_pipeline.py`
- [ ] 단독건물 케이스 결과 확인
- [ ] 아파트(집합건물) 케이스 — 1필지 다동 매칭 문제 확인
- [ ] 매칭 실패 케이스 기록

## 5순위: 보완

- [ ] 실거래가 전월세 API 활용신청 (data.go.kr에서 `RTMSDataSvcAptRent` 검색)
- [ ] 테스트 결과 README.md 체크리스트 업데이트
- [ ] 깃허브 push
- [ ] 팀 카톡에 최종 보고
