"""Explicit public-source acquisition; never called by tests or inference."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request
from evals.independent.acquire import ArticleText

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = {
    **{name.replace('-', '_'): ('text/plain', 'https://science.nasa.gov/mission/' + name + '/')
       for name in ('mariner-4', 'mariner-6', 'mariner-9', 'mariner-10', 'near-shoemaker', 'magellan')},
    'nepal': ('application/json', 'https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2015-04-25&endtime=2015-04-26&minmagnitude=7.5&orderby=time-asc'),
    'sumatra': ('application/json', 'https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2004-12-26&endtime=2004-12-27&minmagnitude=9&orderby=time-asc'),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def acquire(item):
    name, (media, url) = item
    raw_path = ROOT / 'data/t14/source-downloads' / (name + ('.html' if media == 'text/plain' else '.json'))
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if raw_path.exists():
        raw = raw_path.read_bytes()
    else:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'VectorNext public source evaluation'}), timeout=90).read()
        raw_path.write_bytes(raw)
    if media == 'text/plain':
        parser = ArticleText(); parser.feed(raw.decode('utf-8'))
        content = parser.text().encode('utf-8')
        if len(content) < 1000:
            raise ValueError('article extraction too short: ' + name)
    else:
        content = raw
        if len(json.loads(raw)['features']) != 1:
            raise ValueError('expected one original event: ' + name)
    path = HERE / 'fixtures' / (name + ('.txt' if media == 'text/plain' else '.json'))
    path.write_bytes(content)
    return {'id': name, 'path': 'fixtures/' + path.name, 'media_type': media, 'url': url,
            'publisher': 'NASA' if media == 'text/plain' else 'USGS',
            'acquired_utc': datetime.fromtimestamp(raw_path.stat().st_mtime, timezone.utc).isoformat(),
            'sha256': sha(content), 'raw_sha256': sha(raw), 'bytes': len(content),
            'transformation': 'ArticleText v1: original article order, normalized whitespace, inserted heading/table separators' if media == 'text/plain' else 'none; original response bytes',
            'terms_url': 'https://www.nasa.gov/nasa-brand-center/images-and-media/' if media == 'text/plain' else 'https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits'}


if __name__ == '__main__':
    target = HERE / 'sources.json'
    if target.exists() or (HERE / 'data-freeze.json').exists():
        raise ValueError('source manifest exists; acquisition is not a refresh command')
    (HERE / 'fixtures').mkdir(exist_ok=True)
    with ThreadPoolExecutor(4) as pool:
        sources = list(pool.map(acquire, SOURCES.items()))
    target.write_text(json.dumps(sources, indent=2) + '\n', encoding='utf-8')
    for source in sources:
        print(source['id'], source['bytes'])
