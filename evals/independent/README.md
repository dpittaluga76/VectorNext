# T11: independent public-source comparison

A frozen comparison of **two versus five primary passages** on real NASA and USGS documents. It uses the existing local pipeline, structural context, MiniLM embedding/reranking and Gemma 4 26B A4B QAT. The experimental variable is `primary_limit`; candidates stay at 30 and reranking at 20.

The corpus is independent of T01's synthetic soccer data. Codex authored the questions and inspected the sources before inference. This is **not an independently administered benchmark**, and public facts may have appeared in model training. Original source support is scored separately from answer values.

Completed result: five passages scored **16/28**, two **15/28**, identically in both cache passes. Two reduced median latency by 46–50% but lost required answers, so five remain the default. Only 18/20 documents were admitted; six PDF questions remain in every denominator. Read the [full report](../../docs/reports/t11-independent.md), [machine-readable results](../../docs/reports/t11-independent.json) and [separate source review](../../docs/reports/t11-source-review.json).

## Dataset

| Source | Documents | Preparation |
| --- | ---: | --- |
| NASA mission pages | 16 TXT | Article text in source order; headings/table separators inserted, whitespace normalized; navigation/scripts/forms removed and images omitted, captions retained |
| NASA/JPL fact sheets | 2 PDF, 4 pages | Original downloaded bytes; all four pages visually inspected before annotation |
| USGS earthquake API | 2 JSON | Original GeoJSON responses, one event each; ingest records at `/features` |

There are **28 questions**, **47 gold evidence references**, and 23 supported, two ambiguous and three insufficient-evidence outcomes. Four questions require three or four different mission documents. Other cases exercise PDF columns and cross-page facts, similar mission names, units, conversation history, raw nulls, numeric types and missing values. TXT sizes range from about 1.7 to 55 KB; this is not a 400-document capacity benchmark.

- [`dataset.json`](dataset.json): labels, source locations, expected typed fields and alternative support sets.
- [`requests.json`](requests.json): only public questions, field schemas, history and presentation templates. This is the runner's sole source of model requests.
- [`sources.json`](sources.json): publisher, exact URL, acquisition time, file size, hashes and transformation for every document.
- [`freeze.json`](freeze.json): hashes of sources, labels, public requests, protocol and relevant execution/model code, taken before inference.
- [Protocol](../../docs/t11-protocol.md): fixed experiment order, denominators and conservative decision criteria.

### Reading the source correctly

The Perseverance sheet dates from December 2020; its landing date was a **plan at publication**. Questions explicitly preserve that context. The USGS `tsunami: 0` case asks for the raw stored flag; it does not claim the historical earthquake had no tsunami. A null station distance cannot become a numeric zero.

The captured Voyager 1 page contains both two and four operating-instrument counts in different passages. The frozen conflict case expects clarification rather than an unqualified count. That is an explicitly chosen task interpretation, not a claim that the spacecraft simultaneously had both counts. A newer dated passage could support a different interpretation of “currently”; any adjudication is reported separately without rewriting the gold result.

The JSON coordinate order follows the [USGS GeoJSON format](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php): longitude, latitude, depth. Source snapshots preserve the API's actual stored types; a numeric `29` and a numeric `22.9` are not silently converted to strings.

## Reproduce

Run from the repository root. Keep the frozen files unchanged. Validation is offline and never downloads or regenerates sources:

For the historical T11 execution, use commit `aed598c336477b184a25c86e17cf63136ff88fdd` in a separate checkout. T12 adds reporting to `deployment/client.py`, which is one of the frozen execution files. The original freeze correctly rejects that later implementation; do not regenerate it to run a different version under the old comparison name. The source snapshots, labels, requests and scorer are unchanged.

```sh
docker compose build evals
docker compose run --rm -v "${PWD}:/workspace:ro" evals python -m unittest evals.independent.test_protocol -v
docker compose run --rm -v "${PWD}:/workspace:ro" evals python -m evals.independent.freeze
```

The comparison uses the T11 API image and unchanged T10 CPU/generator images. A [pre-query amendment](../../docs/t11-protocol-amendment-01.md) records the UTF-8 ingestion defect found on the first attempt and its regression-tested repair. On a new machine, build those tags from this source tree (the report records the original image IDs). Follow the [root quickstart](../../README.md#quickstart) to acquire local model weights first:

```sh
docker compose -f compose.app.yaml -f compose.independent.yaml -p vectornext-t11 build vectornext processor llm
python -m evals.independent.run --run my-independent-repeat
python -m evals.independent.summarize data/t11/my-independent-repeat --write
docker compose -f compose.app.yaml -f compose.independent.yaml -p vectornext-t11 stop
```

The runner is a host orchestration script using Python's standard library and the Docker CLI; application parsing, storage and inference all run in Docker. Use a fresh alphanumeric run name. It uses port **8091**, project **`vectornext-t11`**, a new database directory under that project's data volume and fresh cache paths. It refuses to overwrite captures or ingest into a populated database. It never deletes volumes or stops other projects.

It ingests once and runs **five/cold → two/cold → two/warm → five/warm**, recreating CPU/API processes between blocks. Cold means an empty variant processing cache with model weights loaded; warm means the same variant's persisted cache is reused. OS caches and other host activity are uncontrolled. Generation answers are not cached. Warm is not a second independent set of questions.

Raw requests' responses, HTTP failures, metrics, samples, job outcomes and document snapshots are retained under ignored `data/t11/<run>/`. Missing documents and failed requests remain in the planned denominator. The old six T01 holdout questions are never sent to a model. The runner verifies frozen input hashes and unchanged runtime image IDs/corpus between blocks.

`acquire.py --download` and `build_dataset.py --author` are preparation history, not refresh or test commands. They refuse to overwrite a completed source manifest/freeze. Source changes require a separately versioned future dataset; do not tune this comparison's labels after observing results.

## Source attribution and reuse

NASA and NASA/JPL-Caltech supplied the mission articles and fact sheets. USGS supplied the earthquake records. Each item links to its original publisher in [`sources.json`](sources.json). The PDFs retain their original embedded credits, illustrations and marks. HTML-to-text snapshots retain textual credit lines but omit images. Raw HTML download hashes are recorded; the original HTML download cache is local and not bundled. The included TXT/PDF/JSON bytes are sufficient to reproduce ingestion and scoring without downloading changing pages.

These source materials are **not relicensed as AGPL repository code**. Consult [NASA's media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/) and [USGS copyright and credit information](https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits). NASA identifies exceptions for third-party material and restrictions on agency identifiers; preserve individual credits and check them before reusing illustrations separately. Inclusion here is for attributed technical evaluation and does not imply NASA, JPL-Caltech or USGS endorsement.

[`voyager1.txt`](fixtures/voyager1.txt) is also the README demonstration source. Its public [request file](../../tests/fixtures/answers/voyager.json) asks for launch and Jupiter/Saturn flyby years; gold labels and source locations are never included in that request.
