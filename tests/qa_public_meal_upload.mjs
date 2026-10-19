// Exercise the application's normal photo preparation on a public CC0 fixture.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
const require=createRequire(import.meta.url),{chromium}=require('../tmp/ui-tools/node_modules/playwright');
const browser=await chromium.launch({headless:true,channel:'msedge'});
try{
 const page=await browser.newPage();await page.goto('http://127.0.0.1:8798');
 const original=await readFile('tmp/public-meal-cc0.jpg');
 const result=await page.evaluate(async base64=>{
  const {prepareUpload,MAX_IMAGE_DATA_URL_LENGTH}=await import('/image-upload.js');
  const file=new File([Uint8Array.from(atob(base64),ch=>ch.charCodeAt(0))],'public-meal.jpg',{type:'image/jpeg'});
  const prepared=await prepareUpload(file,'auto');const img=new Image();img.src=prepared.data;await img.decode();
  return {...prepared,width:img.naturalWidth,height:img.naturalHeight,limit:MAX_IMAGE_DATA_URL_LENGTH};
 },original.toString('base64'));
 assert(result.data.length<=result.limit);
 const bytes=Buffer.from(result.data.split(',')[1],'base64');
 await writeFile('tmp/public-meal-upload.jpg',bytes);
 console.log(JSON.stringify({passed:true,originalBytes:original.length,uploadBytes:bytes.length,
  dataLength:result.data.length,width:result.width,height:result.height,limit:result.limit}));
}finally{await browser.close();}
