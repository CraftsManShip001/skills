// 녹화한 화면(<footage>/<장면>/raw/*.jpg + list.txt)을 고른 간격의 프레임(<footage>/<장면>/60/f00001.jpg …)으로 편다.
// 쓰는 법: node footage.mjs <footage 폴더> <장면> [<장면> …]   (FPS=60 기본)
// 끝나면 <footage>/frames.js에 장면마다 프레임 수를 적는다. 영상 HTML이 <script src="footage/frames.js">로 읽는다.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const FPS = Number(process.env.FPS ?? 60);
const [root, ...names] = process.argv.slice(2);
if (!root || !names.length) {
  console.error("쓰는 법: node footage.mjs <footage 폴더> <장면> …");
  process.exit(1);
}
const base = resolve(root);
const index = join(base, "frames.js");
const frames = existsSync(index) ? JSON.parse(readFileSync(index, "utf8").replace(/^window\.FRAMES\s*=\s*/, "").replace(/;\s*$/, "")) : {};
for (const name of names) {
  const src = join(base, name);
  const dir = join(src, String(FPS));
  mkdirSync(dir, { recursive: true });
  for (const file of readdirSync(dir)) if (/^f\d+\.jpg$/.test(file)) rmSync(join(dir, file));
  execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", join(src, "list.txt"), "-vf", `fps=${FPS}`, "-q:v", "2", join(dir, "f%05d.jpg")], { cwd: src });
  const count = readdirSync(dir).filter((file) => /^f\d+\.jpg$/.test(file)).length;
  frames[name] = count;
  console.log(`${name}: ${count} frames (${(count / FPS).toFixed(1)}s)`);
}
writeFileSync(index, `window.FRAMES = ${JSON.stringify(frames, null, 2)};\n`);
