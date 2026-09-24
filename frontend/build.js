// Vercel 빌드 단계
// 1) 환경 변수 API_BASE_URL 로 public/config.js 를 생성한다.
//    (바닐라 JS 는 브라우저에서 process.env 를 읽을 수 없으므로 빌드 때 값을 파일에 써 넣는다)
// 2) HTML 의 CSS·JS 주소와 JS 모듈 import 경로에 배포 버전(?v=커밋)을 붙인다.
//    옛 HTML 과 새 JS 가 캐시에서 섞여 없는 요소를 건드리는 오류를 막기 위함이다.
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

const pub = path.join(__dirname, "public");
const version = (process.env.VERCEL_GIT_COMMIT_SHA || Date.now().toString(36)).slice(0, 8);

fs.writeFileSync(path.join(pub, "config.js"),
  `// 빌드 시 자동 생성됨 (build.js)\nwindow.APP_CONFIG = { API_BASE_URL: ${JSON.stringify(url)}, VERSION: ${JSON.stringify(version)} };\n`);

const indexPath = path.join(pub, "index.html");
const html = fs.readFileSync(indexPath, "utf8")
  .replace(/(href|src)="((?:styles\.css|config\.js|js\/[\w-]+\.js))"/g, `$1="$2?v=${version}"`);
fs.writeFileSync(indexPath, html);

const jsDir = path.join(pub, "js");
for (const file of fs.readdirSync(jsDir).filter((f) => f.endsWith(".js"))) {
  const p = path.join(jsDir, file);
  const code = fs.readFileSync(p, "utf8").replace(/from "(\.\/[\w-]+\.js)"/g, `from "$1?v=${version}"`);
  fs.writeFileSync(p, code);
}

console.log(`config.js 생성 완료 → API_BASE_URL=${url}, 자산 버전 v=${version}`);
