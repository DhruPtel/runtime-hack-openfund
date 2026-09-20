# Checks

Two scripts that render the page headlessly and assert what it shows, because
"it looks right" is not evidence. They need `jsdom`, which this repository does
not vendor:

```bash
mkdir -p /tmp/openfund-checks && cd /tmp/openfund-checks
npm init -y >/dev/null && npm install jsdom --silent
node /path/to/front-end/checks/from-the-filesystem.js
```

- **`from-the-filesystem.js`** loads `Openfund.html` over `file://`, evaluates the
  two script tags in order with `fetch` refused, and asserts that every section
  still renders from the committed export, that the run button is disabled, and
  that the reason is on the page. 7 checks.
- **`served.js`** runs against `python3 -m fund.run.serve --port 8111` and asserts
  that the button is enabled, that clicking it opens a confirmation naming the
  cost, the duration and the wallet, and that **nothing is posted** until the
  confirmation itself is clicked. 9 checks.

Both were passing when they were committed.
