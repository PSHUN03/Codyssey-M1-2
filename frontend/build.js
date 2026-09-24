// Vercel 빌드 단계: 환경 변수 API_BASE_URL 로 public/config.js 를 생성한다.
// (바닐라 JS 는 브라우저에서 process.env 를 읽을 수 없으므로 빌드 때 값을 파일에 써 넣는다)
const fs = require("fs");
const path = require("path");

const url = (process.env.API_BASE_URL || "").trim().replace(/\/+$/, "");
if (!url) {
  console.error("환경 변수 API_BASE_URL 이 없습니다. Vercel 프로젝트 설정 > Environment Variables 에 추가하세요.");
  process.exit(1);
}
if (!/^https?:\/\//.test(url)) {
  console.error(`API_BASE_URL 은 http(s):// 로 시작해야 합니다: ${url}`);
  process.exit(1);
}

const out = path.join(__dirname, "public", "config.js");
fs.writeFileSync(out, `// 빌드 시 자동 생성됨 (build.js)\nwindow.APP_CONFIG = { API_BASE_URL: ${JSON.stringify(url)} };\n`);
console.log(`config.js 생성 완료 → API_BASE_URL=${url}`);
