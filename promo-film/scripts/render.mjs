// 영상 HTML을 프레임마다 찍어 mp4로 만든다.
// 쓰는 법: node render.mjs <영상.html>[?v=30] [<영상.html>?v=60 …]
//   결과: <영상 폴더>/out/<이름>[-30].mp4
//   크기: HTML의 window.SIZE(없으면 1920×1080) · FPS=60(기본) · RANGE=12-16(그 구간만 찍어 빨리 확인) · SCALE=0.5(작게 찍어 빨리 확인)
// HTML은 window.DURATION(초)과 window.render(t)를 둔다. 실시간 재생이 아니라 t를 하나씩 정해 찍으므로 프레임이 빠지지 않는다.
// render(t)가 Promise를 돌려주면(그림 디코드 대기) 끝날 때까지 기다린 뒤 찍는다.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { basename, dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

// Playwright는 프로젝트에 깔린 것을 쓴다(현재 폴더부터 위로, 또는 PLAYWRIGHT_FROM=패키지 폴더).
function loadPlaywright() {
  const roots = [process.env.PLAYWRIGHT_FROM, process.cwd()].filter(Boolean);
  for (const root of roots) {
    let dir = resolve(root);
    for (;;) {
      for (const name of ["@playwright/test", "playwright"]) {
        try {
          return createRequire(join(dir, "noop.js"))(name);
        } catch {}
      }
      // 모노레포면 apps/*/node_modules에만 있을 수 있다.
      for (const sub of ["apps/web", "web", "app"]) {
        if (existsSync(join(dir, sub, "node_modules"))) {
          try {
            return createRequire(join(dir, sub, "noop.js"))("@playwright/test");
          } catch {}
        }
      }
      const up = dirname(dir);
      if (up === dir) break;
      dir = up;
    }
  }
  throw new Error("Playwright를 못 찾았어요. 프로젝트 폴더에서 실행하거나 PLAYWRIGHT_FROM=<node_modules가 있는 폴더>를 주세요.");
}
const { chromium } = loadPlaywright();

const FPS = Number(process.env.FPS ?? 60);
const SCALE = Number(process.env.SCALE ?? 1);
const [r0, r1] = process.env.RANGE ? process.env.RANGE.split("-").map(Number) : [NaN, NaN];
const targets = process.argv.slice(2);
if (!targets.length) {
  console.error("쓰는 법: node render.mjs <영상.html>[?v=30] …");
  process.exit(1);
}
const browser = await chromium.launch();

for (const target of targets) {
  const [file, query = ""] = target.split("?");
  const html = resolve(file);
  const name = basename(html, ".html");
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: SCALE });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(pathToFileURL(html).href + (query ? `?${query}` : ""));
  // 정사각·세로 영상은 HTML이 window.SIZE = { w: 1080, h: 1920 }처럼 크기를 알린다(없으면 1920×1080).
  const size = await page.evaluate(() => window.SIZE);
  if (size) await page.setViewportSize({ width: size.w, height: size.h });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  if (errors.length) throw new Error(`${name}: 페이지 오류 — ${errors.join(" / ")}`);
  const duration = await page.evaluate(() => window.DURATION);
  const from = Number.isFinite(r0) ? r0 : 0;
  const to = Number.isFinite(r1) ? Math.min(r1, duration) : duration;
  const outDir = join(dirname(html), "out");
  mkdirSync(outDir, { recursive: true });
  const tag = query ? "-" + query.replace(/^v=/, "") : "";
  const part = Number.isFinite(r0) ? `-part${from}-${to}` : "";
  const out = join(outDir, `${name}${tag}${part}.mp4`);
  const ffmpeg = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "png", "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], { stdio: ["pipe", "inherit", "inherit"] });
  const first = Math.round(from * FPS), last = Math.round(to * FPS);
  const started = Date.now();
  for (let i = first; i < last; i += 1) {
    await page.evaluate((t) => window.render(t), i / FPS);
    const png = await page.screenshot({ type: "png" });
    if (!ffmpeg.stdin.write(png)) await new Promise((done) => ffmpeg.stdin.once("drain", done));
    if ((i - first) % (FPS * 5) === 0) console.log(`${name}${tag}: ${(i / FPS).toFixed(1)}s / ${to.toFixed(1)}s`);
  }
  ffmpeg.stdin.end();
  await new Promise((done) => ffmpeg.on("close", done));
  if (errors.length) console.warn(`${name}: 찍는 동안 페이지 오류 — ${errors.join(" / ")}`);
  console.log(`${name}${tag}: ${last - first} frames, ${((Date.now() - started) / 1000).toFixed(0)}s → ${out}`);
  await page.close();
}
await browser.close();
