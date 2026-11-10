# 실제 화면 녹화

`scripts/record.ts`를 프로젝트의 Playwright 폴더(예: `e2e/promo/record.ts`)에 복사하고, 장면 스크립트(`e2e/promo/footage.spec.ts`)를 만들어 `npx playwright test e2e/promo/footage.spec.ts --project=chromium`으로 돌린다. 기본 설정이 이 폴더를 무시하게 해 두면(`testIgnore`) 일반 시험에 섞이지 않는다. 출력 폴더는 `PROMO_FOOTAGE=../../design/promo/footage`처럼 준다(Playwright 실행 폴더 기준).

## 장면 스크립트의 모양

```ts
import { expect, test } from "@playwright/test";
import { click, drag, film, glide, glideTo, stage, typeSlow } from "./record";

test("홍보 영상 화면", async ({ browser }) => {
  test.setTimeout(10 * 60_000);
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await stage(context);          // 화살표·누름 물결을 그리는 창
  // 1) 데이터 준비: 로그인, 예시 문서 만들기, 이름 바꾸기 — 프로젝트의 시험 도우미를 쓴다.
  // 2) 찍기 전 자리 잡기: 마우스를 화면 구석으로, 저장 끝날 때까지 기다리기.
  await page.mouse.move(1500, 950);
  await film(page, "tools", async (mark) => {
    const dock = page.getByRole("toolbar", { name: "도구" });
    await glideTo(page, dock.getByRole("button", { name: "표 넣기" }), 800);
    await click(page);
    await page.waitForTimeout(500);             // 보는 사람이 따라올 틈
    await drag(page, { x: 700, y: 600 }, { x: 900, y: 700 }, 900);
    await mark("table", page.locator("table").last(), 12);   // 나중에 카메라를 맞출 자리
    await typeSlow(page, "영상 시안 고르기");
  });
});
```

- 장면 하나 = `film()` 하나. 다시 찍을 땐 `SCENES=tools,sheet npx playwright test …`.
- `marks.json`에 적힌 자리(x, y, w, h)와 시각(t)으로 영상 틀의 카메라 키프레임을 정한다.
- 찍은 뒤 `node scripts/footage.mjs design/promo/footage tools sheet …`. 출력의 초 수를 보고 컷 길이를 정한다.

## 잘 찍는 요령

- **사람 속도**: 마우스는 `glide`(500~900ms), 글자는 80~120ms 간격, 누른 뒤 250~500ms 쉼. 녹화는 실제 시간이라 나중에 빨리 감을 수는 있어도 느리게 펼 수는 없다. 넉넉히 천천히 찍는다.
- **도구를 고르는 동작부터**: 결과만 찍지 말고 도구 막대에서 고르고 → 놓을 자리로 가고 → 끌어서 만드는 것까지.
- **데이터는 진짜처럼**: 회의록, 가계부, 발표 같은 그럴듯한 내용. 서비스 언어로(한국어 서비스면 한국어). 사람 이름은 지어낸 이름. 이메일에 한글을 넣으면 가입이 실패한다(ASCII로).
- **두 사람**: 두 번째 `browser.newContext()`로 다른 사람을 로그인시켜 같은 문서를 연다. 녹화는 한 쪽 창에서만 하고, 다른 쪽은 화살표 없이(`stage(context, false)`) 조작한다. 남의 커서는 앱이 그려 준다.
- **테마**: 컨텍스트마다 `addInitScript`로 테마를 심는데, 매 페이지 로드마다 덮어쓰면 장면 중간에 테마를 바꿀 수 없다. "값이 없을 때만" 심는다. 분위기 장면(밤·어두운 테마)은 찍기 직전에 localStorage를 바꾸고 다시 연다.
- **시간이 필요한 기능**: 타이머·리허설·"3분 전" 같은 것은 `await page.clock.install()` 뒤 `page.clock.runFor(1000)`을 짧은 대기와 번갈아 불러 몇 분을 몇 초에 담는다.
- **2배 해상도는 안 된다**: CDP 화면 녹화는 뷰포트(1920px)보다 크게 찍지 못한다. 크게 보여야 할 작은 UI는 녹화를 당기지 말고 영상에서 다시 그린다.
- **로컬 서비스**: 녹화에 로컬 DB·서버를 켰다면 끝나고 끈다(프로젝트 규칙 확인).
- 첫 프레임은 화면이 안정된 뒤 시작되게 `film()` 안 맨 앞에 300~400ms 기다린다(틀이 이미 400ms 둔다).

## 정지 그림

여는 장면에서 "펼쳐진 뒤 화면"으로 쓸 그림은 녹화 프레임 하나(`footage/<장면>/60/f00046.jpg` 같은)를 그대로 쓴다. 그래야 다음 컷(같은 녹화)으로 넘어갈 때 그림이 같아 이음매가 안 보인다.
