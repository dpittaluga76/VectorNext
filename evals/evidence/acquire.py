"""Explicit NIST text snapshot acquisition, never called by validation or tests."""
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.request

URLS = {name: 'https://www.nist.gov/pml/owm/'+path for name,path in [
    ('length','si-units-length'),('time','si-units-time'),('mass','si-units-mass'),
    ('current','si-units-electric-current'),('temperature','si-units-temperature'),
    ('amount','si-units-amount-substance'),('light','si-units-luminous-intensity'),
    ('prefixes','metric-si-prefixes'),('writing','writing-si-metric-system-units'),
    ('conversion','metric-si/unit-conversion'),('overview','metric-si/si-units')]}
URLS['style']='https://www.nist.gov/pml/special-publication-330/sp-330-section-5'
TERMS='https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications'


class Node:
    def __init__(self,tag='',attrs=()):self.tag=tag;self.attrs=dict(attrs);self.children=[]
    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child,Node):yield from child.walk()
    def text(self):
        if self.tag in {'script','style','figure','img','iframe','nav'}:return ''
        value=''.join(c.text() if isinstance(c,Node) else c for c in self.children)
        if self.tag=='sup':return '^('+value+')'
        if self.tag=='sub':return '_('+value+')'
        if self.tag=='br':return '\n'
        return value


class Parser(HTMLParser):
    def __init__(self):super().__init__();self.root=Node();self.stack=[self.root]
    def handle_starttag(self,tag,attrs):
        node=Node(tag,attrs);self.stack[-1].children.append(node)
        if tag not in {'img','br','hr','input','meta','link','source','area','base','embed','param','wbr','col'}:self.stack.append(node)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:self.stack=self.stack[:i];return
    def handle_data(self,data):self.stack[-1].children.append(data)


def extract(raw):
    parser=Parser();parser.feed(raw.decode('utf-8'))
    nodes=list(parser.root.walk())
    title=next(n.text().strip() for n in nodes if n.tag=='h1')
    bodies=[n for n in nodes if 'text-with-summary' in n.attrs.get('class','').split()]
    assert len(bodies)==1, ('body count',len(bodies))
    blocks=[]
    def visit(node):
        if node.tag in {'figure','script','style','iframe','nav'}:return
        if node.tag in {'p','h2','h3','h4','h5','h6','li','tr'}:
            if node.tag=='tr':
                text=' | '.join(c.text().strip() for c in node.children if isinstance(c,Node) and c.tag in {'td','th'})
            else:text=node.text()
            text=re.sub(r'\s+',' ',text).strip()
            if text and not text.startswith(('Credit:','Return to Top','Resources for Students and Teachers |')):
                blocks.append((node.tag,text))
            return
        for child in node.children:
            if isinstance(child,Node):visit(child)
    visit(bodies[0])
    text='# '+title+'\n\n'
    for tag,value in blocks:
        if tag.startswith('h') and value.lower().startswith('resources for students'):break
        if ' | ' in value and ('League of SI' in value or 'Return to Top' in value):continue
        text+=('## ' if tag.startswith('h') else '- ' if tag=='li' else '')+value+'\n\n'
    return title,text


def main():
    fixtures=Path('evals/evidence/fixtures');fixtures.mkdir(parents=True,exist_ok=True)
    assert not any(fixtures.iterdir()), 'refusing to regenerate source fixtures'
    raw_dir=Path('data/t23/source-html');raw_dir.mkdir(parents=True,exist_ok=True)
    sources=[]
    for name,url in URLS.items():
        raw_path=raw_dir/f'{name}.html'
        if raw_path.exists():raw=raw_path.read_bytes();resolved=url
        else:
            request=urllib.request.Request(url,headers={'User-Agent':'VectorNext public-source evaluation snapshot'})
            with urllib.request.urlopen(request,timeout=40) as response:raw=response.read();resolved=response.url
            with raw_path.open('xb') as stream:stream.write(raw)
        title,text=extract(raw)
        (fixtures/f'{name}.txt').write_text(text,encoding='utf-8',newline='\n')
        sources.append({'id':name,'title':title,'url':url,'resolved_url':resolved,'retrieved_utc':datetime.now(timezone.utc).isoformat(),'html_sha256':hashlib.sha256(raw).hexdigest(),'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'text_bytes':len(text.encode()),'file':f'fixtures/{name}.txt','terms':TERMS})
        print(name,len(text.encode()))
    with Path('evals/evidence/sources.json').open('x',encoding='utf-8') as stream:json.dump({'extraction':'NIST HTML body to UTF-8 text; heading/paragraph/list/table boundaries; superscripts ^(...), subscripts _(...); omit figures/navigation and trailing student resources; whitespace normalized; modified 2026-10-15','sources':sources},stream,ensure_ascii=False,indent=2)


if __name__=='__main__':main()
