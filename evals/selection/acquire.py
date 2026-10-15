"""Explicit NASA text acquisition. Validation/tests never call this module."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request
from evals.evidence.acquire import Node, Parser

URLS={name:f'https://science.nasa.gov/{name}/facts/' for name in
      ['mercury','earth','mars','jupiter','saturn','uranus','neptune','sun','moon']}
URLS['venus']='https://science.nasa.gov/venus/venus-facts/'
TERMS='https://www.nasa.gov/nasa-brand-center/images-and-media/'


def extract(raw):
    parser=Parser();parser.feed(raw.decode('utf-8'))
    bodies=[n for n in parser.root.walk() if 'entry-content' in n.attrs.get('class','').split()]
    assert len(bodies)==1
    body=bodies[0]
    title=next(n.text().strip() for n in body.walk() if n.tag=='h1')
    parts=[]
    def visit(node):
        if node.tag in {'figure','figcaption','script','style','iframe','nav','form','aside','button'}:return
        if any(c in node.attrs.get('class','').lower() for c in ['caption','credit','social','feedback']):return
        if node.tag in {'p','h2','h3','h4','h5','h6','li','tr'}:
            value=' | '.join(c.text().strip() for c in node.children if isinstance(c,Node) and c.tag in {'td','th'}) if node.tag=='tr' else node.text()
            value=re.sub(r'\s+',' ',value).strip()
            if value:parts.append((node.tag,value))
            return
        for child in node.children:
            if isinstance(child,Node):visit(child)
    visit(body)
    blocks=['# '+title]
    for tag,value in parts:
        if value in ['Keep Exploring','More to Explore','Learn More','Related Resources']:break
        blocks.append(('## ' if tag.startswith('h') else '- ' if tag=='li' else '')+value)
    return title,'\n\n'.join(blocks).strip()+'\n'


def main():
    out=Path('evals/selection');fixtures=out/'fixtures';fixtures.mkdir(parents=True,exist_ok=True)
    assert not any(fixtures.iterdir()),'refusing to regenerate existing fixtures'
    rawdir=Path('data/t24/source-html');rawdir.mkdir(parents=True,exist_ok=True)
    sources=[]
    for name,url in URLS.items():
        path=rawdir/f'{name}.html'
        if not path.exists():
            with urllib.request.urlopen(url,timeout=40) as response:path.write_bytes(response.read())
        raw=path.read_bytes();title,text=extract(raw);data=text.encode('utf-8')
        (fixtures/f'{name}.txt').write_bytes(data)
        sources.append({'id':name,'title':title,'url':url,'retrieved_utc':datetime.now(timezone.utc).isoformat(),
            'html_sha256':hashlib.sha256(raw).hexdigest(),'text_sha256':hashlib.sha256(data).hexdigest(),
            'text_bytes':len(data),'file':f'fixtures/{name}.txt','terms':TERMS})
        print(name,len(data),flush=True)
    with (out/'sources.json').open('x',encoding='utf-8',newline='\n') as f:
        json.dump({'extraction':'NASA article body to UTF-8 TXT; whitespace normalized, headings/lists retained; image/caption/script/navigation/form elements omitted; stop before related-resource sections; superscripts ^(...); modified 2026-10-15','sources':sources},f,ensure_ascii=False,indent=2);f.write('\n')


if __name__=='__main__':main()
