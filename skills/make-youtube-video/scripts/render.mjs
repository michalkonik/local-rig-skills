// Render the frames listed in a plan file (written by video.py) with headless Chrome.
//   node render.mjs PLAN.json
// plan: {width, height, short, brand, vars, scenes:[...], items:[{s, beat, opts, out}]}
import { chromium } from "playwright-core";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const plan = JSON.parse(readFileSync(process.argv[2], "utf8"));
const here = path.dirname(fileURLToPath(import.meta.url));
const exe = ["/usr/bin/google-chrome", "/usr/bin/chromium"].find(existsSync);
const browser = await chromium.launch({ executablePath: exe, args: ["--force-color-profile=srgb", "--hide-scrollbars"] });
const page = await browser.newPage({ viewport: { width: plan.width, height: plan.height }, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(path.join(here, plan.page || "stage.html")).href);
const t0 = Date.now();
let n = 0;
for (const it of plan.items) {
  if (existsSync(it.out) && !plan.force) { n++; continue; }
  const sc = plan.scenes[it.s];
  const opts = { ...it.opts, short: plan.short, brand: plan.brand, vars: plan.vars };
  if (opts.bg) opts.bgUrl = pathToFileURL(path.resolve(plan.dir, opts.bg)).href;
  if (sc.type === "image" && sc.src) opts.imgUrl = pathToFileURL(path.resolve(plan.dir, sc.src)).href;
  await page.evaluate(([sc, b, o]) => window.show(sc, b, o), [sc, it.beat, opts]);
  if (sc.type === "image" || opts.bg) await page.waitForTimeout(300);
  if (sc.type === "image") await page.waitForFunction(() => { const i = document.querySelector("img"); return !i || i.complete; });
  await page.screenshot({ path: it.out, type: "png" });
  n++;
}
await browser.close();
console.log(`rendered ${n} frames in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
