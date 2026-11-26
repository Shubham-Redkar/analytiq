import fs from "node:fs";
import path from "node:path";

const targetDirs = ["app", "components", "context", "lib", "tests"];
const extensions = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".json", ".css"];
let hasError = false;

function scanDir(dir) {
  if (!fs.existsSync(dir)) return;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== "node_modules" && entry.name !== ".next") {
        scanDir(fullPath);
      }
    } else if (extensions.some((ext) => entry.name.endsWith(ext))) {
      checkFile(fullPath);
    }
  }
}

function checkFile(filePath) {
  const content = fs.readFileSync(filePath, "utf-8");
  const lines = content.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.includes("\r")) {
      console.error(`Formatting violation: CRLF line ending in ${filePath}:${i + 1}`);
      hasError = true;
    }
    if (/[ \t]+$/.test(line)) {
      console.error(`Formatting violation: Trailing whitespace in ${filePath}:${i + 1}`);
      hasError = true;
    }
  }
  if (content.length > 0 && !content.endsWith("\n")) {
    console.error(`Formatting violation: Missing newline at end of file in ${filePath}`);
    hasError = true;
  }
}

for (const d of targetDirs) {
  scanDir(path.join(process.cwd(), d));
}

if (hasError) {
  process.exit(1);
} else {
  console.log("All frontend files verified: clean line endings, no trailing whitespace, clean EOF.");
}
