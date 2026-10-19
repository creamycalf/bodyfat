// Keep the whole JSON request below the vision gateway's upload limit. The
// base64 data URL is roughly one third larger than the JPEG it contains.
export const MAX_IMAGE_DATA_URL_LENGTH=700*1024;

// Normalize camera output before sending: some cameras return an empty MIME,
// huge JPEGs, or JPEGs with motion-photo trailers which the server rejects.
export async function prepareUpload(file,category='food'){
 if(!file.size)throw Error('照片文件为空，请重新拍照，或从相册选择照片。');
 if(file.size>40*1024*1024)throw Error('照片超过40 MB，请使用普通拍照模式或从相册选择较小照片。');
 const url=URL.createObjectURL(file),img=new Image();
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('读取照片超时，请从相册重新选择。')),20000);img.onload=()=>{clearTimeout(timer);resolve();};img.onerror=()=>{clearTimeout(timer);reject(Error('无法解码照片，请用 JPG/PNG 拍照或从相册选择。'));};img.src=url;});
  const max=['report','auto'].includes(category)?3000:2048;
  let scale=Math.min(1,max/Math.max(img.naturalWidth,img.naturalHeight)),quality=.84;
  const canvas=document.createElement('canvas');
  for(let attempt=0;attempt<12;attempt++){
   canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));
   const context=canvas.getContext('2d');if(!context)throw Error('手机未能处理照片，请从相册重试。');
   context.fillStyle='#fff';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(img,0,0,canvas.width,canvas.height);
   const data=canvas.toDataURL('image/jpeg',quality);
   if(!data.startsWith('data:image/jpeg;base64,'))throw Error('照片转换失败，请重新选择。');
   if(data.length<=MAX_IMAGE_DATA_URL_LENGTH){canvas.width=canvas.height=1;return {data,mime:'image/jpeg'};}
   if(quality>.65)quality=Math.max(.64,quality-.1);
   else{scale*=Math.max(.55,Math.min(.82,Math.sqrt(MAX_IMAGE_DATA_URL_LENGTH/data.length)*.95));quality=.8;}
  }
  canvas.width=canvas.height=1;
  throw Error('照片压缩后仍超过图片模型的上传上限，请使用普通拍照模式或选择较小照片。');
 }finally{URL.revokeObjectURL(url);}
}

export function imageError(error){
 const code=typeof error==='string'?error:error?.message||'未知错误';
 const messages={unsupported_image_type:'不支持这张照片的格式',invalid_image_content:'照片内容无法识别',image_type_mismatch:'照片实际格式与文件类型不一致',invalid_image_dimensions:'照片尺寸无法读取或过大',image_too_large:'照片文件过大',AI_HTTP_413:'照片超过图片模型服务的上传上限。请用新版重新选择原图上传；重试这个旧任务不会缩小照片',AI_IMAGE_TOO_LARGE:'照片超过图片模型服务的上传上限。请重新选择原图上传',AI_TIMEOUT:'模型分析超时，照片已保留，可以重试',AI_INVALID_RESPONSE:'模型未返回有效的图片分析结果',AI_AUTH_FAILED:'图片模型的凭据不可用，请检查AI设置',AI_CONNECTION_FAILED:'图片模型连接失败，可以稍后重试',AI_UPSTREAM_UNAVAILABLE:'图片模型服务暂时不可用'};
 return messages[code]?`${messages[code]}（${code}）`:code;
}
