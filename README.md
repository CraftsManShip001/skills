# skills

Claude Code 에서 쓰는 스킬 모음.

| 스킬 | 하는 일 |
|---|---|
| [design-flow](design-flow) | 질문으로 정하고, 시안 4개(A~D)를 캔버스에 나란히 그려 고르고 다듬는 디자인 흐름. AI 티 안 나게 하는 규칙 포함 |
| [pr-change-report](pr-change-report) | PR 이나 코드 변경을 흐름 상자, 시퀀스, ERD, 이전·이후 스니펫으로 보여 주는 HTML 리포트 |
| [promo-film](promo-film) | 서비스 홍보 영상을 글자 없이 모션 그래픽으로. 질문 → prompt-motion.com 참고 시안 4개 → 실제 앱 화면 녹화 → 원하는 길이(6초~2분)의 60fps 본편. 렌더러·녹화 도구·영상 틀 포함 |

## 설치
스킬 폴더를 `~/.claude/skills/` 아래에 복사한다.

```bash
git clone https://github.com/CraftsManShip001/skills.git
cp -R skills/<스킬 이름> ~/.claude/skills/
```

`promo-film`은 node, ffmpeg, 프로젝트에 깔린 Playwright(`@playwright/test`)가 있어야 한다.
