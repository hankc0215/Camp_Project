const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const htmlPath = path.join(root, 'index_V1.html');
const html = fs.readFileSync(htmlPath, 'utf8');

const ids = Array.from(html.matchAll(/\sid="([^"]+)"/g), match => match[1]);
const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
const scripts = Array.from(html.matchAll(/<script\s+src="([^"]+)"/g), match => match[1]);
const inlineScripts = Array.from(html.matchAll(/<script(?:\s+[^>]*)?>([\s\S]*?)<\/script>/gi), match => match[1]);

console.log(`ids=${ids.length}`);
console.log(`duplicateIds=${duplicateIds.length ? duplicateIds.join(',') : 'none'}`);

for (const src of scripts) {
  if (/^https?:\/\//.test(src)) {
    console.log(`script:${src}:REMOTE`);
    continue;
  }
  const exists = fs.existsSync(path.join(root, src));
  console.log(`script:${src}:${exists ? 'OK' : 'MISSING'}`);
}

inlineScripts.forEach((code, index) => {
  try {
    new Function(code);
    console.log(`inline:${index + 1}:OK:${code.length}`);
  } catch (error) {
    console.log(`inline:${index + 1}:ERROR:${error.message}`);
    process.exitCode = 1;
  }
});
