import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
const require=createRequire(import.meta.url),{chromium}=require('../tmp/ui-tools/node_modules/playwright');
const browser=await chromium.launch({headless:true,channel:'msedge'});
try{
 const page=await browser.newPage();
 const source=await readFile('image-upload.js','utf8');
 const result=await page.evaluate(async source=>{
  const moduleUrl=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));
  try{
   const {prepareUpload,MAX_IMAGE_DATA_URL_LENGTH}=await import(moduleUrl);
   const canvas=document.createElement('canvas');canvas.width=2200;canvas.height=1600;
   const context=canvas.getContext('2d'),pixels=context.createImageData(canvas.width,canvas.height);
   let seed=20260925;
   for(let i=0;i<pixels.data.length;i+=4){
    seed=(Math.imul(seed,1664525)+1013904223)>>>0;
    pixels.data[i]=seed&255;pixels.data[i+1]=(seed>>>8)&255;pixels.data[i+2]=(seed>>>16)&255;pixels.data[i+3]=255;
   }
   context.putImageData(pixels,0,0);
   const original=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.94));
   const upload=await prepareUpload(new File([original],'camera.jpg',{type:'image/jpeg'}),'auto');
   const image=new Image();image.src=upload.data;await image.decode();
   return {originalBytes:original.size,dataLength:upload.data.length,limit:MAX_IMAGE_DATA_URL_LENGTH,
           width:image.naturalWidth,height:image.naturalHeight,data:upload.data};
  }finally{URL.revokeObjectURL(moduleUrl);}
 },source);
 if(result.originalBytes<1_000_000)throw Error('Synthetic camera photo was too small to exercise compression');
 if(result.dataLength>result.limit)throw Error('Prepared photo exceeds the gateway-safe size');
 if(result.width<700||result.height<500)throw Error('Photo was shrunk too far');
 await writeFile('tmp/normalized-size-test.jpg',Buffer.from(result.data.split(',')[1],'base64'));
 console.log(JSON.stringify({passed:true,originalBytes:result.originalBytes,dataLength:result.dataLength,
                             limit:result.limit,width:result.width,height:result.height}));
}finally{await browser.close();}
