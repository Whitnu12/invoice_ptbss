// Exercise the actual template script without a live DB or login session.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const template = fs.readFileSync(path.join(__dirname, 'templates/master_po.html'), 'utf8');
assert(!template.includes('id="analyticsRows"'), 'Do not render a second unpaginated PO table');
assert.equal((template.match(/id="poRows"/g) || []).length, 1);
const script = template.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace(/\{\{\s*url_for\("([^"]+)"[^}]*\}\}/g, (_, endpoint) => '/' + endpoint + '/0')
  .replace(/\{%[^%]*%\}/g, '');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    value: id === 'pageSize' ? '5' : '', innerHTML: '', textContent: '', style: {},
    classList: {add(){}, remove(){}}, setAttribute(){},
    insertAdjacentHTML(_, value){this.innerHTML += value;},
    closest(){return {scrollIntoView(){}};},
  });
  return elements.get(id);
}
const calls = [];
let failure = null;
const context = {URLSearchParams, Intl, console: {error(){}}, setTimeout, clearTimeout,
  document: {getElementById: element, addEventListener(){}, body: {style:{}}, querySelector(){return null;}},
  window: {}, alert(message){throw Error(message);},
  async fetch(url) {
    calls.push(url);
    if (failure) return failure;
    let data;
    if (url.includes('api_detail')) data = {success:true, data:{header:{id:7,nomor_po:'PO-7'},items:[]}};
    else if (url.includes('api_analytics')) data = {success:true,summary:{jumlah_po:12,total_plafon:1200},data:[]};
    else {
      const params = new URLSearchParams(url.split('?')[1]);
      const size = Number(params.get('per_page'));
      const page = Number(params.get('page'));
      data = {success:true, data:Array.from({length:Math.min(size, 12-(page-1)*size)},(_,i)=>({id:i+1,nomor_po:'PO-'+i,status_po:'ACTIVE'})),
        pagination:{page,per_page:size,total:12,pages:Math.ceil(12/size)}};
    }
    return {ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>data};
  },
};
vm.runInNewContext(script, context);
const settle = () => new Promise(resolve => setImmediate(resolve));
(async()=>{
  await context.window.loadPO();
  assert.equal((element('poRows').innerHTML.match(/Buka detail/g)||[]).length, 5);
  assert.match(element('paginationInfo').textContent, /1–5 dari 12/);
  context.window.goToPage(2); await settle();
  assert.match(element('paginationInfo').textContent, /6–10 dari 12/);
  element('pageSize').value = '10'; context.window.changePageSize(); await settle();
  assert.match(element('paginationInfo').textContent, /1–10 dari 12/);
  assert.equal(element('kpiPlafon').textContent.includes('1.200'), true);
  await context.window.detailPO(7);
  assert.match(element('poDetail').innerHTML, /PO-7/);
  failure = {ok:false,status:500,headers:{get:()=> 'application/json'},json:async()=>({success:false,message:'Database error',error_code:'PO-DB-1267-test'})};
  await context.window.detailPO(7);
  assert.match(element('poDetail').innerHTML, /PO-DB-1267-test/);
  failure = {ok:false,status:500,headers:{get:()=> 'text/html'}};
  await context.window.detailPO(7);
  assert.match(element('poDetail').innerHTML, /HTTP 500/);
  console.log('PASS: combined list, pagination, totals, detail and JSON/HTML errors');
})().catch(error=>{console.error(error);process.exitCode=1;});
