// 영상의 한 구간을 한 장에 모아 본다(장면 넘김·끊김·흐림을 눈으로 확인할 때).
// 쓰는 법: node contact.mjs <영상.mp4> <시작 초> <끝 초> [칸 수=8]  → <영상 폴더>/contact-<시작>-<끝>.png
import { execFileSync } from "node:child_process";
import { basename, dirname, join } from "node:path";

const [video, a, b, n = "8"] = process.argv.slice(2);
if (!video || a === undefined || b === undefined) {
  console.error("쓰는 법: node contact.mjs <영상.mp4> <시작 초> <끝 초> [칸 수]");
  process.exit(1);
}
const count = Number(n), from = Number(a), to = Number(b);
const cols = count <= 4 ? count : 4, rows = Math.ceil(count / cols);
const out = join(dirname(video), `contact-${basename(video, ".mp4")}-${from}-${to}.png`);
const rate = count / Math.max(0.01, to - from);
execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-ss", String(from), "-to", String(to), "-i", video, "-vf", `fps=${rate},scale=640:-1,tile=${cols}x${rows}:padding=6:color=white`, "-frames:v", "1", out]);
// 칸 순서대로의 시각(왼쪽 위부터 줄마다).
console.log(out);
console.log("칸 시각:", Array.from({ length: count }, (_, i) => (from + (i + 0.5) / rate).toFixed(2)).join(" "));
