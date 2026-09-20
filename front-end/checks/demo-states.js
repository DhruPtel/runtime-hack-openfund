const {JSDOM} = require('jsdom');
const fs = require('fs'), path = require('path');
const FE = '/home/dhrupatel/bnkr-openfund/front-end';
function page(query) {
  const dom = new JSDOM(fs.readFileSync(path.join(FE, 'Openfund.html'), 'utf8'),
    {runScripts:'dangerously', pretendToBeVisual:true, url: 'file://' + FE + '/Openfund.html' + query});
  const w = dom.window;
  w.HTMLDialogElement.prototype.showModal = function(){this.open=true};
  w.HTMLDialogElement.prototype.close = function(){this.open=false};
  return w;
}
const out = []; const ok=(n,c)=>out.push([c?'PASS':'FAIL',n]);
const full = page(''), empty = page('?empty');
setTimeout(() => {
  [full, empty].forEach(w => {
    w.eval(fs.readFileSync(path.join(FE, 'data/openfund-data.js'), 'utf8'));
    w.fetch = () => Promise.reject(new Error('no server'));
    w.eval(fs.readFileSync(path.join(FE, 'wire.js'), 'utf8'));
  });
  setTimeout(() => {
    const go = (w,id) => { w.location.hash='#'+id; w.dispatchEvent(new w.Event('hashchange'));
      return (w.document.getElementById('main').textContent||'').replace(/\s+/g,' '); };
    // PART ONE
    const o = go(empty,'overview');
    ok('empty: no decision loaded', o.includes('No cycle has run in this session'));
    ok('empty: NAV is a dash', /NAV—|NAV —/.test(o.replace(/\s/g,'')) || o.includes('NAV—'));
    ok('empty: seats waiting', go(empty,'swarm').includes('has not been asked yet'));
    ok('empty: flow idle', (empty.document.getElementById('cycle-status')||{}).textContent.includes('Ready to run'));
    ok('empty: risk has nothing to review', go(empty,'risk').includes('Nothing to review yet'));
    ok('empty: the four real swaps are still there', go(empty,'chain').includes('Confirmed swaps4'));
    ok('committed cycles not deleted', !!full.OPENFUND_EXPORT.overview.nav && go(full,'overview').includes('$'));
    // PART TWO
    const chain = go(full,'chain');
    const leg = full.document.querySelector('[data-action="run-liveleg"]');
    ok('a control that moves real money exists', !!leg);
    ok('it is disabled with no server', leg && leg.disabled === true);
    ok('it is labelled honestly', chain.includes('same treasurer'));
    // PART THREE
    const dec = go(full,'decision');
    full.document.querySelectorAll('[data-select-asset]')[0]?.dispatchEvent(new full.MouseEvent('click',{bubbles:true}));
    const trace = (full.document.getElementById('main').textContent||'').replace(/\s+/g,' ');
    ok('decision: contract, feed, round id', /Contract \(4663\)/.test(trace) && /Round id/.test(trace) && /Feed address/.test(trace));
    ok('decision: three sources', /Chainlink feed/.test(trace) && /GeckoTerminal/.test(trace) && /Venue quote/.test(trace));
    ok('decision: pinned block', /Pinned block/.test(trace));
    const risk = go(full,'risk');
    ok('risk: gates with measured values', /Gates that ran on this order/.test(risk));
    ok('risk: the fresh quote and its endpoint', /swap-quote/.test(risk) && /Age when judged/.test(risk));
    ok('risk: the agent model and cost', /The risk agent/.test(risk) && /Model/.test(risk));
    ok('risk: names who decided', /Decided by/.test(risk));
    out.forEach(([r,n])=>console.log(r+'  '+n));
    console.log(out.filter(c=>c[0]==='FAIL').length+' failed of '+out.length);
    process.exit(0);
  }, 900);
}, 700);
