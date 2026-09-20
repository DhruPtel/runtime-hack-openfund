const {JSDOM} = require('jsdom');
const fs = require('fs'), path = require('path');
const FE = '/home/dhrupatel/bnkr-openfund/front-end';
const dom = new JSDOM(fs.readFileSync(path.join(FE, 'Openfund.html'), 'utf8'),
  {runScripts: 'dangerously', pretendToBeVisual: true, url: 'file://' + FE + '/Openfund.html'});
const w = dom.window;
w.HTMLDialogElement.prototype.showModal = function(){this.open=true};
w.HTMLDialogElement.prototype.close = function(){this.open=false};
setTimeout(() => {
  /* exactly what the two script tags do, in order */
  w.eval(fs.readFileSync(path.join(FE, 'data/openfund-data.js'), 'utf8'));
  w.fetch = () => Promise.reject(new Error('file:// cannot fetch'));   /* no server */
  w.eval(fs.readFileSync(path.join(FE, 'wire.js'), 'utf8'));
  setTimeout(() => {
    const main = () => (w.document.getElementById('main').textContent||'').replace(/\s+/g,' ');
    const go = id => { w.location.hash='#'+id; w.dispatchEvent(new w.Event('hashchange')); return main(); };
    const out = []; const ok=(n,c)=>out.push([c?'PASS':'FAIL',n]);
    ok('export reached the page', !!w.OPENFUND_EXPORT);
    ok('data applied with no server', go('overview').includes('c55400f87d'));
    const run = w.document.querySelector('[data-action="run-cycle"]');
    ok('run button disabled', !!run && run.disabled === true);
    const cap = w.document.getElementById('flow-caption');
    ok('reason shown on the page', !!cap && /filesystem|backend/.test(cap.textContent));
    ok('footer label honest', (w.document.querySelector('[data-action="demo-info"]')||{}).textContent === 'About this data');
    ok('chain renders four swaps', go('chain').includes('Confirmed swaps4'));
    ok('both NAVs, never summed', go('books').includes('$200.03') && main().includes('$1.29'));
    out.forEach(([r,n])=>console.log(r+'  '+n));
    console.log(out.filter(c=>c[0]==='FAIL').length+' failed of '+out.length);
    console.log('caption: ' + (cap ? cap.textContent.slice(0,150) : '(none)'));
    w.close(); process.exit(0);
  }, 600);
}, 600);
