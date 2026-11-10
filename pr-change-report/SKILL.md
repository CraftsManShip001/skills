---
name: pr-change-report
description: "Use when explaining a PR or code change as an HTML report. 변경 리포트: 흐름 상자, 시퀀스, ERD, 이전·이후 스니펫."
---

# PR 변경 리포트 (HTML)

PR 이나 코드 변경을 처음 보는 팀원이 5분 안에 이해하도록 돕는 HTML 리포트를 만든다.
리뷰가 아니다. 결함을 찾지 않고, 무엇이 어떻게 바뀌는지를 그림·표·이전/이후 비교로 보여 준다.

## 언제 쓰나
- "이 PR 리포트 만들어 줘", "변경 내용 문서로 정리해 줘", "이 수정 이해되게 설명해 줘 (HTML)"
- 리뷰어에게 넘기기 전에 변경의 흐름·쿼리·테이블을 한 장으로 보여 주고 싶을 때

## 만드는 순서
1. **변경 읽기.** `gh pr view <번호> --json title,body,baseRefName,files` 와 `gh pr diff <번호>` (PR 이 없으면 `git diff <base>...HEAD`). diff 를 끝까지 읽고, 바뀐 함수의 호출처와 관련 모델(`models.py` 의 `db_table`, 필드, FK, 인덱스)을 직접 읽는다.
2. **무엇을 넣을지 고르기.** `references/writing-rules.md` 의 표를 따른다. 정해진 목차는 없다. 작은 변경은 절 하나로 끝낸다.
3. **`report.json` 쓰기.** 형식은 `references/report-format.md`. 작은 예시 `templates/example-small.json`, 큰 예시 `templates/example-large.json`.
4. **검사.** `python3 ~/.claude/skills/pr-change-report/scripts/check.py report.json` 을 돌려 "고칠 곳"이 나오면 고치고 다시 돌린다. "통과"가 나올 때까지 반복한다. 금지 표현이 걸리면 다른 말로 바꾸기 전에 그 문장이 필요한지부터 본다.
5. **HTML 만들기.**
   ```bash
   python3 ~/.claude/skills/pr-change-report/scripts/check.py report.json --out report.html \
     --meta repo=<owner/repo> pr=<번호> "pr_title=<제목>" head=<커밋> base_ref=<대상 브랜치> date=$(date +%F) [team=<머리말 이름>]
   ```
   머리말에는 `team` 이 있으면 그 이름, 없으면 `repo` 의 저장소 이름이 들어간다.
   HTML 한 파일로 나온다. 브라우저로 열어 그림의 글자 겹침과 화살표를 확인한 뒤 전달한다.

`scripts/check.py` 는 파이썬 표준 라이브러리만 쓴다. 저장소에 `.github/pr-report/check.py` 가 있으면 그 파일이 최신이니 그쪽을 쓴다.

## 지킬 것
- **구조는 문단이 아니라 그림으로.** 호출 순서·반복·재시도 같은 복잡한 흐름은 `sequence`(시퀀스 다이어그램)나 `flow`(화살표로 잇는 흐름 상자)로 그린다. "그다음", "그 뒤"로 단계를 이어 가는 문단은 그림으로 바꾼다.
- **바뀐 것은 명사로, 한 줄에 하나.** 예: "잔액 SUM 3번 → 1번", "알림 발송을 celery 태스크로 이동". 문장은 도입부와 그림을 읽는 데 필요한 한두 줄에만 쓴다.
- **비유 없이 직설로.** 코드가 실제로 하는 일을 쓴다. "DB 를 붙잡던" 대신 "배치가 도는 동안 DB CPU 90% 이상".
- **AI 가 쓴 티가 나는 표현을 쓰지 않는다.** 예고("정리했습니다"), 강조 수사("핵심은"), 꾸미는 말("대폭", "효율적으로"), 결산 문장("~인 셈입니다"), 문장형 제목, 짧은 단정문 연타, 줄표. `check.py` 가 잡아 준다.
- **짧게.** 절 6개, 절마다 블록 4개, 코드·표를 뺀 글 2,200자까지. diff 만 봐도 아는 것(파일 목록, 이름 변경)은 넣지 않는다.
- **이전·이후는 한 블록에서 나란히.** 코드와 쿼리는 스니펫으로 나오고 바뀐 줄에 `-` `+` 가 붙는다.
- **쿼리 변경은 ORM 코드가 아니라 생성되는 SQL 로 비교한다.** 로컬 DB 가 있으면 `CaptureQueriesContext` 로 실제 SQL 을 잡아 `sql_source: captured` 로 쓰고, 코드를 읽고 옮겼으면 `derived` 로 둔다.
- **관련 테이블은 ERD 로.** 표마다 이 변경이 읽고 쓰는 필드와 쓰는 방식을 적고, FK·JSON 키·복사 관계를 선으로 잇는다.
- **숫자는 측정한 값만.** PR 본문·테스트·코드에 실제로 있는 값만 쓴다. 없으면 `kpis`·`bars` 를 뺀다.
- **확인하지 못한 것은 쓰지 않는다.** PR 본문과 코드가 다르면 코드를 따른다.

## 블록 한눈에
| 블록 | 쓰는 곳 |
|---|---|
| `flow` | 배치·요청 전체가 하는 일. 번호 상자를 화살표로 잇고 바꾼 단계를 표시 |
| `sequence` | 호출 순서. 2개를 주면 이전·이후로 나란히 |
| `tables` | 관련 테이블 ERD |
| `compare` | 이전·이후 코드 또는 SQL 스니펫 |
| `table`, `bullets` | 달라지는 동작, 테스트 근거 |
| `kpis`, `bars` | 측정값 |
| `callout` | 배포 순서처럼 놓치면 안 되는 한 가지 |

자세한 필드는 `references/report-format.md`.
