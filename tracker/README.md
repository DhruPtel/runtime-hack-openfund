# `tracker/` — what was built, and what went wrong

Two files. One is the build log; the other is the more useful one.

| File | What it holds |
|---|---|
| `LOGS.md` | every unit as it was built, with the commits, the figures it produced, and a state-at-close note written for whoever picks this up next |
| `LESSONS.md` | what was believed, what turned out to be true, and what changed because of it |

## Why a record of failure is part of the product

This fund's claim is not "it works". It is **"you can check"**. A repository that only
records successes gives a reader no way to judge whether the successes were examined at
all.

So `LESSONS.md` holds the things that went wrong, in the same detail as the things that
went right:

- three components once counted cash three different ways, and the sweep that found it;
- a replay that silently read today's config instead of the config the record was
  decided under — which would have made every "byte-identical" claim meaningless;
- a risk brief that told the agent an overall veto kills every order without saying when
  one was warranted, so it vetoed two whole plans over a single flagged mark;
- an unauthenticated local endpoint that spent $1.33 on a request nobody meant to send;
- two bugs that only appeared when a real transaction did not settle on the first read.

Each entry says what was believed, what the evidence showed, and what changed. Several
were found by deliberately breaking a rule in a scratch copy to confirm a test would
catch it — and twice, the test did not, which is recorded too.

`LOGS.md` ends with a **state at close** note: what runs, what each command needs, what
is owed, and where the numbers came from. It is written to be read cold.
