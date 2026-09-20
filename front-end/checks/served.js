const {JSDOM} = require('jsdom');
const fs = require('fs'), path = require('path');
const FE = '/home/dhrupatel/bnkr-openfund/front-end';
const BASE = 'http://127.0.0.1:8111/';
(async () => {
 const html = await (await fetch(BASE)).text();
 const dom = new JSDOM(html, {runScripts:'dangerously', pretendToBeVisual:true, url: BASE});
 const w = dom.window;
 w.HTMLDialogElement.prototype.showModal = function(){this.open=true};
 w.HTMLDialogElement.prototype.close = function(){this.open=false};
 const posts = [];
 setTimeout(async () => {
  w.eval(await (await fetch(BASE+'data/openfund-data.js')).text());
  w.fetch = (url, opts) => {                       /* the real server, through node */
   if (opts && opts.method === 'POST') { posts.push(url); return Promise.resolve({ok:true, json:async()=>({started:'test'})}); }
   return fetch(new URL(url, BASE).href);
  };
  w.eval(await (await fetch(BASE+'wire.js')).text());
  setTimeout(() => {
   const out = []; const ok=(n,c)=>out.push([c?'PASS':'FAIL',n]);
   const run = w.document.querySelector('[data-action="run-cycle"]');
   ok('run button enabled when served', run && run.disabled === false);
   const cap = w.document.getElementById('flow-caption');
   ok('caption names the cycle it reads', cap && cap.textContent.startsWith('Live. Reading fixtures/live/decisions'));
   run.dispatchEvent(new w.MouseEvent('click', {bubbles:true}));
   const dlg = w.document.getElementById('detail-dialog');
   ok('clicking run opens a confirmation', dlg.open === true);
   const body = w.document.getElementById('dialog-body').textContent;
   ok('confirmation states the cost', /about \$1\.20/.test(body));
   ok('confirmation states the duration', /250 seconds|four minutes/.test(body));
   ok('confirmation names the wallet', /0x93faecde/.test(body));
   ok('confirmation says nothing is submitted on chain', /stock fills are paper/.test(body));
   ok('NOTHING was spent by opening it', posts.length === 0);
   ok('data came from the server', (w.document.getElementById('main').textContent||'').includes('c55400f87d'));
   out.forEach(([r,n])=>console.log(r+'  '+n));
   console.log(out.filter(c=>c[0]==='FAIL').length+' failed of '+out.length);
   w.close(); process.exit(0);
  }, 900);
 }, 500);
})();
