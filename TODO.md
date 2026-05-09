# 내일 이어서 할 것 (데이터 수집 조사)

## 1순위: Vworld 건물 폴리곤 확인

- [x] Vworld 인증 문제 해결 — `Referer: http://localhost` 헤더 추가
- [x] 레이어 수정 — `LT_C_AISRESC`(항공장애물) → `LT_C_SPBD`(도로명주소 건물)
- [ ] `python test_vworld.py` 재실행
- [ ] bd_mgt_sn (25자리 건물관리번호) 반환 확인
- [ ] PNU = bd_mgt_sn[:19] 추출 확인
- [ ] 건물 폴리곤 (MultiPolygon) 좌표 확인
- [ ] 건물명(buld_nm), 도로명(rd_nm), 층수(gro_flo_co) 확인

## 2순위: 건축HUB API 참고문서 확인

### 건축물대장
- [ ] data.go.kr → 건축HUB_건축물대장정보 서비스 → **참고문서** "OpenAPI활용가이드- 건축HUB 건축물대장 1.0.zip" 다운로드
- [ ] zip 안의 문서에서 **정확한 오퍼레이션명**과 **파라미터** 확인
- [ ] `test_building_registry.py`의 `TITLE_URL` 수정
- [ ] `python test_building_registry.py` 재실행

### 건물에너지
- [ ] data.go.kr → 건축HUB_건물에너지정보 서비스 → **참고문서** "OpenAPI활용가이드- 건축HUB 건물에너지 1.0.hwp" 다운로드
- [ ] hwp 안에서 **정확한 오퍼레이션명**과 **파라미터** 확인 (현재 `getBldEngyInfo` → 404)
- [ ] `test_energy.py`의 `ENERGY_URL` 수정
- [ ] `python test_energy.py` 재실행

### 그래도 안 되면
- [ ] data.go.kr "오류신고 및 문의"에 문의: "승인 완료됐으나 빈 응답/404 반환"
- [ ] 전화 문의도 고려 (건축문화경관과 02-2187-4164)

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
