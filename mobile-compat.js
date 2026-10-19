// Android System WebView on older devices may not implement Array.at yet.
if(!Array.prototype.at){Object.defineProperty(Array.prototype,'at',{value:function(index){index=Math.trunc(Number(index)||0);return this[index<0?this.length+index:index];},writable:true,configurable:true});}
// getRandomValues is available on LAN HTTP even when randomUUID is not.
if(!globalThis.crypto.randomUUID){
 globalThis.crypto.randomUUID=()=>{const b=crypto.getRandomValues(new Uint8Array(16));b[6]=(b[6]&15)|64;b[8]=(b[8]&63)|128;const h=Array.from(b,v=>v.toString(16).padStart(2,'0')).join('');return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;};
}
