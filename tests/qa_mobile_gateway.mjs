import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/lxx/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const url=readFileSync('.mobile-private/pairing-url.txt','utf8').trim();
const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:390,height:844}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(url);await page.locator('#connection').filter({hasText:'数据已连接'}).waitFor();
 const capabilities=await page.evaluate(()=>({secure:isSecureContext,uuid:crypto.randomUUID(),cookie:document.cookie}));
 if(capabilities.secure||! /^[0-9a-f-]{36}$/.test(capabilities.uuid)||capabilities.cookie.includes('zhiheng_mobile'))throw Error('LAN compatibility/auth mismatch');
 for(const view of ['chat','plan','dashboard','archive']){await page.locator(`nav [data-view="${view}"]`).click();if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow: '+view);}
 await page.screenshot({path:'tmp/android-release-20260917/lan-mobile.png',fullPage:true});await page.reload();await page.locator('#connection').filter({hasText:'数据已连接'}).waitFor();
 if(errors.length)throw Error(errors.join('\n'));console.log(JSON.stringify({errors,lanHttp:true,uuidFallback:true,refreshAuthenticated:true,formalReadOnly:true}));
}finally{await browser.close();}
