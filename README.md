# misgrounded

Checks that each fact in a legal brief is actually in the exhibit it cites.

A fact can be true and still cite the wrong exhibit. Faithfulness-style checks miss this, because they verify a claim against all sources at once. This project runs the same LLM judge twice: once with the whole case file (A), once with the cited exhibit only (B). A claim that passes A and fails B is **misgrounded**.

The write-up, with results: **[hajar6883.github.io/work/releases/misgrounded](https://hajar6883.github.io/work/releases/misgrounded/)**

The case file is fictional and written in French, in the style of a French commercial dispute. Code identifiers are in English; comments and data are in French.

## Replay everything, no API key

Every model answer is cached in `cache/`, so the whole pipeline replays offline.

```bash
python -m venv .venv && source .venv/bin/activate
pip install pytest
python -m pytest                                  # 152 tests
CONTROLE_PIECES_OFFLINE=1 PYTHONPATH=src python -m controle_pieces run
```

`run` prints every table and writes `results/resultats.json`.

## Re-run with the model

```bash
pip install -e ".[dev]"
cp .env.example .env                              # then set GEMINI_API_KEY
```

| Command | What it does | Calls the model |
|---|---|---|
| `python -m controle_pieces run` | full pipeline + report | no |
| `python -m controle_pieces rapport [--json]` | print the metrics | no |
| `python -m controle_pieces piege` | rebuild the brief with planted errors | no |
| `python -m controle_pieces cotes` | rebuild the brief with true facts under wrong exhibits | no |
| `python -m controle_pieces renumerotation` | renumbering drift: naive vs stable IDs | no |
| `python -m controle_pieces juge [--acte piege\|genere\|cotes]` | A/B double pass | yes |
| `python -m controle_pieces acte` | draft the brief from the case file | yes |
| `python -m controle_pieces resumes` | generate and check exhibit-list summaries | yes |

New answers are added to `cache/`; a cached answer is never requested twice.

## Layout

```
dossier/
  pieces/               10 fictional exhibits (contract, invoices, emails, ...)
  bordereau.json        exhibit list: number -> stable ID -> file -> title -> summary
  verite_terrain.json   55 ground-truth facts, each tied to one exhibit
projets/
  conclusions_llm.md        brief drafted by the LLM (false-alert measurement)
  conclusions_piegees.md    same brief with 12 planted errors (recall measurement)
  erreurs_plantees.json     the planted errors, with expected outcome
  conclusions_mauvaises_cotes.md   same brief, 14 true facts moved under a wrong exhibit
  cotes_deplacees.json      the moved citations
src/controle_pieces/
  extract.py    split the brief into claims, one per cited value
  checks.py     normalise amounts, dates, percentages; compare
  locate.py     find where a value really lives in the case file
  judge.py      the A/B double pass
  renumber.py   renumbering drift and the stable-ID fix
  report.py     metrics; rules first, judge on what they leave open
  llm.py        Gemini client, disk cache, retry on 429/503
cache/          every model call: prompt + answer
results/        output of the runs quoted in the write-up
```

## Limits

One fictional case, one model family, three briefs, 98 claims. Planted errors aren't the errors an LLM makes on its own, so recall (planted brief) and false alerts (clean brief) are measured separately and never averaged.
