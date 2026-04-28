#!/usr/bin/env node
/**
 * Copy font files từ <repo>/fonts/ → <remotion>/public/fonts/
 * Gọi từ thư mục remotion của job (cwd mặc định), hoặc: node sync-fonts.mjs /path/to/remotion
 */
import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.join(__dirname, "..");
const FONTS_SRC = path.join(REPO_ROOT, "fonts");
const EXT = /\.(ttf|otf|woff2)$/i;

const remotionDir = path.resolve(process.argv[2] || process.cwd());
const fontsDest = path.join(remotionDir, "public", "fonts");

function main() {
  if (!fs.existsSync(FONTS_SRC)) {
    console.warn(`[sync-fonts] Không có thư mục nguồn: ${FONTS_SRC}`);
    fs.mkdirSync(fontsDest, {recursive: true});
    return;
  }

  fs.mkdirSync(fontsDest, {recursive: true});
  const names = fs.readdirSync(FONTS_SRC);
  let n = 0;
  for (const name of names) {
    if (!EXT.test(name)) continue;
    const from = path.join(FONTS_SRC, name);
    if (!fs.statSync(from).isFile()) continue;
    fs.copyFileSync(from, path.join(fontsDest, name));
    n++;
  }
  if (n > 0) {
    console.log(`[sync-fonts] Đã copy ${n} file → ${fontsDest}`);
  } else {
    console.warn(
      `[sync-fonts] Không có .ttf/.otf/.woff2 trong ${FONTS_SRC} — bỏ qua.`,
    );
  }
}

main();
