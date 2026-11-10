// 영상 공통 도구. 영상은 window.render(t)로 t초의 화면을 그리고, render.mjs가 프레임마다 찍는다.
// 시간에 따라 바뀌는 것은 모두 t에서 계산한다(재생 속도·순서와 상관없이 같은 프레임이 나오게). Date.now·CSS 애니메이션·setTimeout을 쓰지 않는다.

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const ease = {
  in: (x) => x * x * x,
  out: (x) => 1 - Math.pow(1 - x, 3),
  inOut: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  expo: (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x)),
  back: (x) => {
    const c = 1.70158;
    return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2);
  },
  // 통통 튀며 멈춤(말풍선·손이 튀어나올 때).
  spring: (x) => (x >= 1 ? 1 : 1 - Math.exp(-6 * x) * Math.cos(10 * x)),
  linear: (x) => x,
};
// a~b초 사이의 진행(0~1).
const p = (t, a, b, e = ease.out) => e(clamp((t - a) / (b - a)));
// 들어왔다(a~b) 나가는(c~d) 값.
const show = (t, a, b, c = Infinity, d = Infinity) => Math.min(p(t, a, b), 1 - p(t, c, d));
// 한 번 튀었다 돌아오는 값(0→1→0).
const pulse = (t, a, b) => Math.sin(Math.PI * clamp((t - a) / (b - a)));
const bezier = (a, c, b, u) => [lerp(lerp(a[0], c[0], u), lerp(c[0], b[0], u), u), lerp(lerp(a[1], c[1], u), lerp(c[1], b[1], u), u)];

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
function set(el, styles) {
  const node = typeof el === "string" ? $(el) : el;
  for (const key in styles) node.style[key] = styles[key];
}

// 시각 지도: [[컷 안 초, 장면 안 초], …]를 지나는 단조 3차 곡선. 빨리 감기 속도가 갑자기 바뀌지 않는다. 범위 밖은 끝 기울기로 늘인다.
function smoothMap(pts) {
  const n = pts.length, xs = pts.map((q) => q[0]), ys = pts.map((q) => q[1]);
  if (n === 1) return (x) => ys[0] + (x - xs[0]);
  const d = xs.slice(0, -1).map((x, i) => (ys[i + 1] - ys[i]) / (xs[i + 1] - x));
  const m = xs.map((_, i) => (i === 0 ? d[0] : i === n - 1 ? d[n - 2] : d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2));
  for (let i = 0; i < n - 1; i += 1) {
    if (d[i] === 0) { m[i] = m[i + 1] = 0; continue; }
    const a = m[i] / d[i], b = m[i + 1] / d[i], h = Math.hypot(a, b);
    if (h > 3) { m[i] = (3 * a * d[i]) / h; m[i + 1] = (3 * b * d[i]) / h; }
  }
  return (x) => {
    if (x <= xs[0]) return ys[0] + (x - xs[0]) * m[0];
    if (x >= xs[n - 1]) return ys[n - 1] + (x - xs[n - 1]) * m[n - 1];
    let i = 0;
    while (x >= xs[i + 1]) i += 1;
    const h = xs[i + 1] - xs[i], u = (x - xs[i]) / h, u2 = u * u, u3 = u2 * u;
    return (2 * u3 - 3 * u2 + 1) * ys[i] + (u3 - 2 * u2 + u) * h * m[i] + (-2 * u3 + 3 * u2) * ys[i + 1] + (u3 - u2) * h * m[i + 1];
  };
}

// 카메라: [[진행 0~1, 보는 곳 x, y, 배율], …]을 지나는 캣멀롬 곡선. 키프레임마다 멈추지 않고 흐른다. 배율은 로그로 잇는다.
function camAt(cam, k) {
  const n = cam.length;
  if (n === 1) return cam[0].slice(1);
  let i = 0;
  while (i < n - 2 && k >= cam[i + 1][0]) i += 1;
  const q0 = cam[Math.max(0, i - 1)], q1 = cam[i], q2 = cam[i + 1], q3 = cam[Math.min(n - 1, i + 2)];
  const u = clamp((k - q1[0]) / (q2[0] - q1[0]));
  const cr = (a, b, c, e) => 0.5 * (2 * b + (c - a) * u + (2 * a - 5 * b + 4 * c - e) * u * u + (3 * b - a - 3 * c + e) * u * u * u);
  return [cr(q0[1], q1[1], q2[1], q3[1]), cr(q0[2], q1[2], q2[2], q3[2]), Math.exp(cr(Math.log(q0[3]), Math.log(q1[3]), Math.log(q2[3]), Math.log(q3[3])))];
}
// 화면 가장자리가 비지 않게 막아서 transform으로.
function camStyle([cx, cy, z], W = 1920, H = 1080) {
  const tx = clamp(W / 2 - cx * z, W - W * z, 0), ty = clamp(H / 2 - cy * z, H - H * z, 0);
  return `translate(${tx}px, ${ty}px) scale(${z})`;
}

// 글자를 하나씩 더할 때마다의 너비(말풍선이 글자를 따라 매끄럽게 늘어나게). 글꼴이 다 들어온 뒤 한 번 잰다.
function prefixWidths(el, text, caret = "") {
  el.style.width = "auto";
  const ws = [...Array(text.length + 1).keys()].map((n) => {
    el.innerHTML = text.slice(0, n) + caret;
    return el.getBoundingClientRect().width;
  });
  el.textContent = "";
  return ws;
}
