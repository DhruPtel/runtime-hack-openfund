/* Wires the page to the fund. Written by hand; the data it reads is written by
   `python3 -m fund.run.dashboard --export`.

   Two modes, decided at load:
   - **served** (`python3 -m fund.run.serve`): the run button works and a live cycle's
     real stages drive the flow diagram;
   - **from the filesystem** (`file://`): every section still renders, from the same
     committed export, and the run button is disabled with the reason on the page.
     `fetch` cannot read a local file, which is why the export is a script assignment
     and not JSON fetched at load.

   `Openfund.setData` refuses to replace data while a cycle is running, so a live run
   animates first and repaints when it is done. That is respected, not worked around. */
(function () {
 'use strict';
 const SECTIONS = ['app', 'overview', 'swarm', 'decision', 'risk', 'books', 'record', 'chain'];
 const RUN = '[data-action="run-cycle"]';
 let served = false, polling = null, note = '';

 function apply(payload) {
  if (!payload) return;
  SECTIONS.forEach(name => {
   if (payload[name]) {
    try { window.Openfund.setData(name, payload[name]); }
    catch (e) { console.warn('openfund: could not set ' + name, e); }
   }
  });
 }

 /* The run button's state and the line under the flow, re-applied after every render:
    the page rebuilds its own chrome and would otherwise undo this. */
 let adjusting = false;
 function chrome() {
  if (adjusting) return;          /* this writes into the tree it watches */
  adjusting = true;
  try {
   const run = document.querySelector(RUN);
   if (run && !served && run.disabled !== true) run.disabled = true;
   if (run && !served && run.title !== note) run.title = note;
   const caption = document.getElementById('flow-caption');
   if (caption && note && caption.textContent !== note) caption.textContent = note;
   const footer = document.querySelector('[data-action="demo-info"]');
   if (footer && footer.textContent !== 'About this data') footer.textContent = 'About this data';
  } finally {
   /* after the observer has queued whatever this wrote, not before */
   setTimeout(() => { adjusting = false; }, 0);
  }
 }

 function watch() {
  const main = document.getElementById('main');
  if (!main) return;
  new MutationObserver(chrome).observe(main, {childList: true, subtree: true});
  chrome();
 }

 /* --- the run button ------------------------------------------------------------- */

 function confirmDialog() {
  const body = document.getElementById('dialog-body'),
        title = document.getElementById('dialog-title'),
        dialog = document.getElementById('detail-dialog');
  title.textContent = 'Run one live cycle';
  body.innerHTML =
   '<p>This spends real money and takes about four minutes.</p>' +
   '<div class="row-divider"></div>' +
   '<dl class="metadata">' +
   '<div><dt>Inference</dt><dd>about $1.20 — four analyst calls and one risk call</dd></div>' +
   '<div><dt>Duration</dt><dd>about 250 seconds, mostly the snapshot</dd></div>' +
   '<div><dt>Chain</dt><dd>nothing is submitted: stock fills are paper</dd></div>' +
   '<div><dt>Wallet</dt><dd>' + (window.OPENFUND_EXPORT?.app?.fundWallet || '—') + '</dd></div>' +
   '</dl><div class="row-divider"></div>' +
   '<div class="button-row"><button class="btn" id="of-confirm-run">Spend about $1.20 and run</button>' +
   '<button class="btn outline" data-action="close-dialog">Cancel</button></div>';
  dialog.showModal();
  document.getElementById('of-confirm-run').addEventListener('click', start, {once: true});
 }

 function unavailable() {
  const title = document.getElementById('dialog-title'),
        body = document.getElementById('dialog-body');
  title.textContent = 'No server';
  body.innerHTML = '<p>' + note + '</p><p class="small muted">Every section on this page is ' +
   'already real: it is reading the committed cycle and the four confirmed swaps.</p>';
  document.getElementById('detail-dialog').showModal();
 }

 async function start() {
  document.getElementById('detail-dialog').close();
  try {
   const reply = await fetch('api/cycle/run', {method: 'POST'});
   if (!reply.ok) throw new Error(await reply.text());
   window.Openfund.beginLiveCycle();
   poll();
  } catch (e) {
   console.error(e);
   alert('The cycle did not start: ' + e.message);
  }
 }

 let seen = 0;
 function poll() {
  clearTimeout(polling);
  polling = setTimeout(async () => {
   try {
    const state = await (await fetch('api/cycle/progress?since=' + seen)).json();
    (state.events || []).forEach(event => {
     seen = Math.max(seen, event.seq || 0);
     try { window.Openfund.applyProgressEvent(event); }
     catch (e) { console.warn('openfund: progress event refused', event, e); }
    });
    if (state.running) return poll();
    window.Openfund.cancelCycle();          /* setData is refused while running */
    apply(await (await fetch('api/data')).json());
   } catch (e) {
    console.error('openfund: lost the run', e);
    window.Openfund.cancelCycle();
   }
  }, 1200);
 }

 /* --- start -------------------------------------------------------------------- */

 document.addEventListener('click', e => {
  const el = e.target.closest('[data-action="run-cycle"]');
  if (!el) return;
  e.stopPropagation();
  e.preventDefault();
  served ? confirmDialog() : unavailable();
 }, true);

 async function boot() {
  apply(window.OPENFUND_EXPORT);
  try {
   const manifest = await fetch('api/manifest', {cache: 'no-store'});
   if (!manifest.ok) throw new Error('no manifest');
   served = true;
   const named = await manifest.json();
   note = 'Live. Reading ' + (named.decision || 'the latest cycle') +
          '. Running a cycle spends about $1.20.';
   apply(await (await fetch('api/data')).json());
  } catch (e) {
   served = false;
   note = window.location.protocol === 'file:'
    ? 'Opened from the filesystem, so no cycle can be started from here. Everything shown is ' +
      'real, read from the committed cycle and the four confirmed swaps. To run one: ' +
      'python3 -m fund.run.serve'
    : 'No backend is answering, so the run button is disabled. Everything shown is real, ' +
      'read from the committed export. To run a cycle: python3 -m fund.run.serve';
  }
  watch();
 }

 if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
 else boot();
})();
