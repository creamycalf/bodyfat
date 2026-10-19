import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const port = Number(process.env.PORT || 8787);
const mime = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8'};

function json(res, status, body) {
  res.writeHead(status, {'content-type': 'application/json; charset=utf-8', 'access-control-allow-origin': '*'});
  res.end(JSON.stringify(body));
}

async function body(req) {
  let data = ''; for await (const chunk of req) data += chunk;
  try { return data ? JSON.parse(data) : {}; } catch { return {}; }
}

function analyze(text = '') {
  const candidates = [];
  if (/睡|几点|熬夜|孩子/.test(text)) candidates.push({type:'sleep', value:{summary:'睡眠情况已描述'}, confidence:0.82, needs_confirmation:true});
  if (/外卖|吃|饭|热量|照片|拍/.test(text)) candidates.push({type:'meal', value:{status:'待上传或确认份量'}, confidence:0.58, needs_confirmation:true});
  if (/喘|胸闷|呼吸困难|剧烈疼痛|红肿/.test(text)) candidates.push({type:'safety', value:{escalate:true}, confidence:0.9, needs_confirmation:false});
  const reply = candidates.some(x=>x.type==='safety')
    ? '你描述了可能需要及时处理的症状。请先停止运动和减重调整；如果呼吸困难、胸痛或症状正在加重，请及时就医。'
    : candidates.some(x=>x.type==='meal')
      ? '可以发外卖照片。我会先给出热量范围，再追问米饭、油、酱汁或你实际吃了几成，不会把估算值直接写进档案。'
      : '我先把这句话作为今天的状态信息。确认后我会更新档案，并据此刷新今日看板。';
  return {reply, extracted_data:candidates, model:'mock-rule-engine', disclaimer:'原型阶段为规则模拟，不能替代医疗建议。'};
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') { res.writeHead(204, {'access-control-allow-origin':'*','access-control-allow-methods':'GET,POST,OPTIONS','access-control-allow-headers':'content-type'}); return res.end(); }
  if (req.url === '/api/health') return json(res, 200, {ok:true, service:'zhiheng-api', stage:'prototype'});
  if (req.url === '/api/chat' && req.method === 'POST') { const input = await body(req); return json(res, 200, analyze(input.text)); }
  const requested = req.url === '/' ? '/index.html' : req.url.split('?')[0];
  const safe = normalize(join(root, requested));
  if (!safe.startsWith(normalize(root))) return json(res, 403, {error:'forbidden'});
  try { const data = await readFile(safe); res.writeHead(200, {'content-type': mime[extname(safe)] || 'application/octet-stream'}); res.end(data); }
  catch { json(res, 404, {error:'not_found'}); }
});
server.listen(port, '127.0.0.1', () => console.log(`知衡原型服务已启动：http://127.0.0.1:${port}`));
