# report.json 형식

`scripts/check.py` 가 이 형식을 검사하고 HTML 로 그립니다.

## 전체 구조
```json
{
  "title": "30자 이하 이름",
  "lead": "무엇을 왜 바꿨는지 2문장, 140자 이하",
  "kpis": [{"label": "배치 1회 쿼리 수", "value": "18,240 → 152", "note": "로컬 측정"}],
  "sections": [{"heading": "22자 이하 명사", "blocks": []}],
  "sources": [{"label": "테스트", "text": "`tests/points/test_x.py`"}]
}
```
`sections` 는 1~6개, 절마다 `blocks` 1~4개입니다. `kpis` 는 0~3개, `sources` 는 선택입니다.

## 블록
- `{"type":"text","text":"..."}` 200자 이하
- `{"type":"bullets","items":[{"label":"처리 순서","text":"..."}]}` 항목 1~6개, `label` 선택
- `{"type":"table","headers":[],"rows":[[]],"numeric":[2],"highlight":[0],"caption":""}` 10행 이하. `numeric` 은 오른쪽 정렬할 열, `highlight` 는 강조할 행
- `{"type":"compare","lang":"python|sql|text","sql_source":"derived|captured","before":{"title":"","code":""},"after":{"title":"","code":""},"caption":""}` 한 줄 62칸 이하(한글은 2칸), 40줄 이하. 줄 번호와 문법 색이 붙은 스니펫으로 그려집니다. `!` 로 시작하는 줄은 이전 쪽에서 빨간 `-`, 이후 쪽에서 초록 `+` 로 표시되니, 이전에서 없어지거나 바뀐 줄과 이후에서 새로 생기거나 바뀐 줄에만 붙입니다. 이전·이후 표시는 자동으로 붙으니 `title` 은 그 코드의 이름을 씁니다
- `{"type":"code","lang":"python|sql|text","title":"","code":"","caption":""}` 비교가 아닌 스니펫 한 개. 한 줄 84칸 이하. `!` 로 시작하는 줄은 강조. `title` 은 파일 경로나 함수 이름
- `{"type":"flow","steps":[{"title":"적립금 지급","lines":["리뷰 1건 500 (사진 1,000)","한도 초과면 지급 보류"],"changed":true}],"caption":""}` 번호 상자를 화살표로 이은 그림입니다. 2~6단계, `title` 16자 이하, `lines` 는 그 단계가 하는 일 1~2줄(한 줄 한글 16자 이하). 이 PR 이 바꾼 단계에 `changed`
- `{"type":"sequence","diagrams":[{"title":"","lanes":[{"key":"svc","label":"서비스","sub":"services.py"}],"steps":[]}],"caption":""}` `diagrams` 가 2개면 이전·이후로 나란히 놓이고 이전·이후 표시가 자동으로 붙습니다. `title` 은 그 방식의 이름입니다(예: "리뷰마다 지급"). `lanes` 2~4개(`label` 16칸, `sub` 는 파일 이름만 18칸 이하), `steps` 14개 이하
  - `{"kind":"msg","from":"svc","to":"db","label":"잔액 SUM","note":"리뷰마다","hot":true}` `hot` 은 비용이 큰 호출, `ret` 은 응답(점선)
  - `{"kind":"self","at":"svc","label":"메모리에서 지급 계산"}`
  - `{"kind":"loop_start","label":"리뷰마다 반복"}` … `{"kind":"loop_end"}`
- `{"type":"tables","tables":[{"key":"grant","model":"PointGrantRecord","table":"point_pointgrantrecord","group":"적립금","changed":true,"fields":[{"name":"id","badge":"PK"},{"name":"related_data","badge":"IDX","note":"리뷰 id, 지급일 JSON"}],"use":["오늘 지급 여부 IN 조회 1번","bulk INSERT"]}],"relations":[{"from":"grant","field":"related_data","to":"review","to_field":"id","kind":"json"}],"caption":""}` 관련 테이블 ERD 입니다. 표 1~14개
  - 표는 읽는 순서대로 적습니다. FK·복사로 이어진 표끼리 한 줄로 놓이고(가리키는 표가 오른쪽), 다른 묶음은 그 아래 줄에 놓입니다.
  - `group` 은 앱·DB 단위 이름이고 머리 색으로 구분됩니다(예: "리뷰", "적립금", "집계 DB").
  - `fields` 는 PK, 관계에 쓰는 필드, 이 변경이 읽고 쓰는 필드만 8개 이하. `badge` 는 PK·FK·IDX, `note` 는 짧은 뜻(36칸 이하)
  - `use` 는 이 변경 뒤 그 표를 읽고 쓰는 방식 1~3줄(한 줄 한글 20자 이하)
  - `relations` 는 표 사이의 선입니다. `kind` 는 `fk`(실선), `json`(FK 없이 JSON 키로 가리킴, 점선), `copy`(다른 DB·표에서 복사, 점선). `field`·`to_field` 는 그 표의 `fields` 에 있는 이름이고, 비우면 표 머리에 붙습니다. `label` 은 선택(예: "매일 복사")
  - `member` 처럼 여러 표가 가리키는 표는 그리지 않고 필드 `note` 에 "→ member" 로 적습니다.
  - `caption` 에는 이 변경을 이해하는 데 필요한 데이터 모델의 사실을 씁니다. 예: "지급 기록은 리뷰를 FK 가 아니라 `related_data` JSON 키로 가리킴"
- `{"type":"bars","source":"PR 본문의 로컬 측정","items":[{"label":"전체","sub":"배치 1회","before":{"value":21.4,"text":"21.4초"},"after":{"value":0.92,"text":"0.92초"}}]}`
- `{"type":"callout","kind":"note|warn","text":""}` 배포 순서처럼 놓치면 안 되는 한 가지에만 씁니다
