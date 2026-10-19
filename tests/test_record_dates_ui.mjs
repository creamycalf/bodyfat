import assert from 'node:assert/strict';
import {recordDay,recordDateText,renderHealthPages} from '../health-pages.js';

const unknown={id:'unknown',type:'weight',value:{kg:90},date_precision:'month',date_text:'2026-09',created_at:'2026-10-17T09:00:00'};
const year={date_precision:'year',date_text:'2025',occurred_at:null,created_at:null};
assert.equal(recordDay(unknown),'');
assert.equal(recordDay(year),'');
assert.equal(recordDateText(unknown),'2026-09（具体日期待补充）');
assert.equal(recordDateText(year),'2025（具体日期待补充）');
assert.equal(recordDateText({date_precision:'unknown',created_at:null,recorded_at:'2026-10-17T09:00:00'}),'日期待补充');
assert.equal(recordDateText({observed_at:'2026-10-16T00:00:00',created_at:'2026-10-17T09:00:00'}),'2026-10-16');

const roots=new Map(['#dashboard-content','#plan-content','#archive-content'].map(key=>[key,{innerHTML:''}]));
globalThis.document={querySelector:key=>roots.get(key)};
renderHealthPages({records:[unknown],fields:{},profile:{},profile_sources:{},pending:[],plans:[],feedback:[],tasks:[]},
 {sourceHtml:()=>'',field:()=>'',recordText:r=>String(r.value.kg)});
const board=roots.get('#dashboard-content').innerHTML,archive=roots.get('#archive-content').innerHTML;
assert.match(archive,/2026-09（具体日期待补充）/);
assert.doesNotMatch(board,/class="weight-chart"|最近 1 次测量/);
assert.doesNotMatch(board+archive,/1970|NaN|undefined|null/);
console.log('record date UI: imprecise dates remain visible and stay outside measured trends');
