import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
const require=createRequire(import.meta.url),{chromium}=require('../tmp/ui-tools/node_modules/playwright');
const phase=process.argv[2]||'before';
const browser=await chromium.launch({headless:true,channel:'msedge'});
const page=await browser.newPage({viewport:{width:390,height:844}}),rows=[],errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:8798');await page.getByText('数据已连接',{exact:true}).waitFor();
 await page.locator('#new-chat').click();
 const draft='我已经写了一半：晚上下班很饿，不能吃花生。';
 await page.locator('#message').fill(draft);
 await page.locator('[data-starter]').first().click();
 rows.push({case:'starter_preserves_typed_draft',passed:(await page.locator('#message').inputValue())===draft});
 await page.locator('#message').fill(draft);
 const chooser=page.waitForEvent('filechooser');await page.locator('[data-start-report]').click();await chooser;
 rows.push({case:'report_entry_preserves_typed_draft',passed:(await page.locator('#message').inputValue())===draft});
 await page.locator('#message').fill(draft);
 await page.locator('#open-history').click();await page.locator('#history-search').fill('搜索测试');
 await page.keyboard.press('Escape');
 rows.push({case:'history_escape_preserves_draft',passed:(await page.locator('#message').inputValue())===draft});
 for(const width of [320,390,1280]){
  await page.setViewportSize({width,height:720});await page.waitForTimeout(100);
  rows.push({case:`no_overflow_${width}`,passed:await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)});
 }
 rows.push({case:'no_javascript_errors',passed:errors.length===0,errors});
 await writeFile(`tmp/agent-draft-ui-${phase}.json`,JSON.stringify(rows,null,2));
 console.log(JSON.stringify(rows));
 if(phase==='after')assert(rows.every(r=>r.passed));
}finally{await browser.close();}
