import { mkdir, rm, writeFile } from "node:fs/promises";
import type { BrowserContext, Locator, Page } from "@playwright/test";

// 홍보 영상 촬영 도구. 프로젝트의 Playwright 폴더(e2e 등)에 복사해 쓴다. 시험이 아니라 촬영용이다.
// 장면마다 <OUT>/<장면>/raw/*.jpg, list.txt(프레임마다 걸린 시간), marks.json(띄울 자리와 시각)을 남긴다.
// 그다음 footage.mjs가 고른 간격의 프레임으로 편다.

export const OUT = process.env.PROMO_FOOTAGE ?? "promo/footage";
export const SIZE = { width: 1920, height: 1080 };
// SCENES=a,b 로 일부 장면만 다시 찍는다.
export const SCENES = process.env.SCENES?.split(",");

// 화면 녹화에는 마우스가 안 찍히므로 화살표와 누른 자리 물결을 화면에 그린다.
const POINTER = () => {
  const draw = () => {
    if (document.getElementById("__pointer") || !document.body) return;
    document.body.insertAdjacentHTML(
      "beforeend",
      `<div id="__pointer" style="position:fixed;left:-60px;top:-60px;z-index:2147483647;pointer-events:none;width:30px;height:30px"><svg width="30" height="30" viewBox="0 0 24 24"><path d="M5 3l14 8-6 1.6L10 19z" fill="#151515" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg></div><div id="__ripple" style="position:fixed;z-index:2147483646;pointer-events:none;width:36px;height:36px;margin:-18px 0 0 -18px;border-radius:50%;background:rgba(0,0,0,.18);opacity:0"></div>`,
    );
  };
  addEventListener("mousemove", (event) => {
    draw();
    const pointer = document.getElementById("__pointer")!;
    pointer.style.left = event.clientX - 5 + "px";
    pointer.style.top = event.clientY - 3 + "px";
  }, true);
  addEventListener("mousedown", (event) => {
    draw();
    const ripple = document.getElementById("__ripple")!;
    ripple.style.left = event.clientX + "px";
    ripple.style.top = event.clientY + "px";
    ripple.animate([{ opacity: 1, transform: "scale(.4)" }, { opacity: 0, transform: "scale(1.6)" }], { duration: 450, easing: "ease-out" });
  }, true);
};

// 촬영용 창. 로그인·데이터 넣기는 프로젝트마다 다르니 여기서 하지 않는다(받은 context로 직접).
export async function stage(context: BrowserContext, pointer = true) {
  if (pointer) await context.addInitScript(POINTER);
  return context.newPage();
}

// 사람 손처럼: 가속했다 멈추고, 살짝 휘어 간다.
export async function glide(page: Page, x: number, y: number, ms = 600) {
  const from = await page.evaluate(() => {
    const pointer = document.getElementById("__pointer");
    return pointer && pointer.style.left ? { x: parseFloat(pointer.style.left) + 5, y: parseFloat(pointer.style.top) + 3 } : { x: 1500, y: 900 };
  });
  const steps = Math.max(8, Math.round(ms / 16));
  for (let i = 1; i <= steps; i += 1) {
    const k = 1 - Math.pow(1 - i / steps, 3);
    await page.mouse.move(from.x + (x - from.x) * k, from.y + (y - from.y) * k - Math.sin(k * Math.PI) * 40);
    await page.waitForTimeout(ms / steps);
  }
}
export async function glideTo(page: Page, target: Locator, ms = 600, dx = 0.5, dy = 0.5) {
  const box = (await target.boundingBox())!;
  await glide(page, box.x + box.width * dx, box.y + box.height * dy, ms);
}
export async function click(page: Page) {
  await page.mouse.down();
  await page.mouse.up();
}
// 누른 채 천천히 끈다(끄는 모습이 녹화에 보이게).
export async function drag(page: Page, from: { x: number; y: number }, to: { x: number; y: number }, ms = 700) {
  await glide(page, from.x, from.y, 500);
  await page.mouse.down();
  const steps = Math.round(ms / 25);
  for (let i = 1; i <= steps; i += 1) {
    const k = 1 - Math.pow(1 - i / steps, 2);
    await page.mouse.move(from.x + (to.x - from.x) * k, from.y + (to.y - from.y) * k);
    await page.waitForTimeout(25);
  }
  await page.waitForTimeout(150);
  await page.mouse.up();
}
// 사람이 치는 속도. 한글은 page.keyboard.type이 글자 단위로 넣는다.
export const typeSlow = (page: Page, text: string, delay = 90) => page.keyboard.type(text, { delay });

export type Mark = { name: string; t: number; x: number; y: number; w: number; h: number };
// 한 장면을 찍는다. act 안에서 화면을 조작하고, mark(이름, 대상)로 나중에 쓸 자리와 시각을 적는다.
export async function film(page: Page, name: string, act: (mark: (label: string, target: Locator, pad?: number) => Promise<void>) => Promise<void>) {
  if (SCENES && !SCENES.includes(name)) return;
  const dir = `${OUT}/${name}`;
  await rm(dir, { recursive: true, force: true });
  await mkdir(`${dir}/raw`, { recursive: true });
  const cdp = await page.context().newCDPSession(page);
  const frames: { t: number; data: string }[] = [];
  cdp.on("Page.screencastFrame", (frame) => {
    frames.push({ t: frame.metadata.timestamp ?? Date.now() / 1000, data: frame.data });
    void cdp.send("Page.screencastFrameAck", { sessionId: frame.sessionId }).catch(() => {});
  });
  const marks: Mark[] = [];
  const mark = async (label: string, target: Locator, pad = 10) => {
    const box = (await target.boundingBox())!;
    marks.push({ name: label, t: Date.now() / 1000, x: box.x - pad, y: box.y - pad, w: box.width + pad * 2, h: box.height + pad * 2 });
  };
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: SIZE.width, maxHeight: SIZE.height });
  await page.waitForTimeout(400);
  await act(mark);
  await page.waitForTimeout(500);
  await cdp.send("Page.stopScreencast");
  await cdp.detach();
  // 화면이 안 바뀌면 프레임이 안 오므로, 프레임마다 다음 프레임까지 걸린 시간을 적어 둔다.
  const t0 = frames[0]!.t;
  const lines: string[] = [];
  for (let i = 0; i < frames.length; i += 1) {
    const file = `${String(i).padStart(5, "0")}.jpg`;
    await writeFile(`${dir}/raw/${file}`, Buffer.from(frames[i]!.data, "base64"));
    const next = frames[i + 1]?.t ?? frames[i]!.t + 0.5;
    lines.push(`file 'raw/${file}'`, `duration ${Math.max(0.001, next - frames[i]!.t).toFixed(4)}`);
  }
  lines.push(`file 'raw/${String(frames.length - 1).padStart(5, "0")}.jpg'`);
  await writeFile(`${dir}/list.txt`, lines.join("\n"));
  await writeFile(`${dir}/marks.json`, JSON.stringify(marks.map((item) => ({ ...item, t: Math.round((item.t - t0) * 100) / 100 })), null, 2));
}
