"""Explicit acquisition only. No downloads or regeneration during validation/inference."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parent
RAW = ROOT.parents[1] / 'data/t11/source-downloads'
MISSIONS = {
    'voyager1': 'voyager/voyager-1', 'voyager2': 'voyager/voyager-2',
    'pioneer10': 'pioneer-10', 'pioneer11': 'pioneer-11', 'galileo': 'galileo',
    'cassini': 'cassini', 'new_horizons': 'new-horizons', 'juno': 'juno',
    'messenger': 'messenger', 'dawn': 'dawn', 'kepler': 'kepler',
    'stardust': 'stardust', 'deep_impact': 'deep-impact-epoxi',
    'mars_pathfinder': 'mars-pathfinder', 'mars_odyssey': 'odyssey',
    'viking1': 'viking-1',
}
EXTRAS = {
    'apollo11_pdf': ('application/pdf','https://science.nasa.gov/wp-content/uploads/2024/01/apollo11-anniversar-litho.pdf','NASA'),
    'perseverance_pdf': ('application/pdf','https://assets.science.nasa.gov/content/dam/science/psd/mars/downloadable_items/4/4/44738_Mars2020_Fact_Sheet_REV_BI.pdf','NASA/JPL-Caltech'),
    'tohoku_json': ('application/json','https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2011-03-11&endtime=2011-03-12&minmagnitude=9&orderby=time-asc','USGS'),
    'maule_json': ('application/json','https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2010-02-27&endtime=2010-02-28&minmagnitude=8.5&orderby=time-asc','USGS'),
}


def sha(raw): return hashlib.sha256(raw).hexdigest()


class ArticleText(HTMLParser):
    """Keep article text/order and table cells; exclude scripts, media and navigation."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False; self.skip = []; self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag == 'article': self.active = True
        if not self.active: return
        if tag in ('script', 'style', 'nav', 'form', 'svg'):
            self.skip.append(tag)
        if self.skip: return
        if tag in ('h1','h2','h3','h4','h5','h6','p','li','tr','div','section'): self.parts.append('\n\n')
        if tag in ('td','th'): self.parts.append(' | ')
        if tag == 'br': self.parts.append('\n')
        if re.fullmatch('h[1-6]',tag): self.parts.append('#'*int(tag[1])+' ')
    def handle_endtag(self, tag):
        if tag == 'article': self.active = False
        if self.skip:
            if tag == self.skip[-1]: self.skip.pop()
            return
        if self.active and tag in ('h1','h2','h3','h4','h5','h6','p','li','tr','div','section'): self.parts.append('\n\n')
    def handle_data(self, data):
        if self.active and not self.skip: self.parts.append(data)
    def text(self):
        lines=[re.sub(r'\s+',' ',s).strip(' |') for s in ''.join(self.parts).splitlines()]
        output='\n'.join(lines)
        return re.sub(r'\n{3,}','\n\n',output).strip()+'\n'


def acquire_one(item):
    id, slug = item; url='https://science.nasa.gov/mission/'+slug+'/'
    raw_path=RAW/(id+'.html')
    if raw_path.exists(): raw=raw_path.read_bytes()
    else:
        raw=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'VectorNext source evaluation'}),timeout=60).read()
        raw_path.write_bytes(raw)
    parser=ArticleText();parser.feed(raw.decode('utf-8'))
    content=parser.text().encode()
    if len(content)<700: raise ValueError('article extraction too short: '+id)
    path=ROOT/'fixtures'/(id+'.txt')
    path.write_bytes(content)
    return {'id':id,'url':url,'publisher':'NASA','acquired_utc':datetime.fromtimestamp(raw_path.stat().st_mtime,timezone.utc).isoformat(),
        'path':'fixtures/'+path.name,'media_type':'text/plain','sha256':sha(content),'raw_sha256':sha(raw),
        'bytes':len(content),'transformation':'HTML article to TXT; original text order retained; headings/table separators inserted; navigation/scripts/forms removed; images omitted, captions/table text retained; whitespace normalized',
        'terms_url':'https://www.nasa.gov/nasa-brand-center/images-and-media/'}


def acquire_extra(item):
    id,(media,url,publisher)=item;suffix='.pdf' if media=='application/pdf' else '.json'
    path=ROOT/'fixtures'/(id+suffix)
    if path.exists(): raw=path.read_bytes()
    else:
        raw=urllib.request.urlopen(url,timeout=90).read();path.write_bytes(raw)
    if media=='application/json':
        obj=json.loads(raw)
        if obj.get('type')!='FeatureCollection' or len(obj['features'])!=1: raise ValueError('expected one original event: '+id)
    elif not raw.startswith(b'%PDF'): raise ValueError('not a PDF: '+id)
    return {'id':id,'url':url,'publisher':publisher,'acquired_utc':datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),
        'path':'fixtures/'+path.name,'media_type':media,'sha256':sha(raw),'raw_sha256':sha(raw),'bytes':len(raw),
        'transformation':'none; downloaded original bytes',
        'terms_url':'https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits' if publisher=='USGS' else 'https://www.nasa.gov/nasa-brand-center/images-and-media/'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--download',action='store_true',required=True);p.parse_args()
    if (ROOT/'sources.json').exists(): raise ValueError('source manifest exists; acquisition is not a refresh command')
    RAW.mkdir(parents=True,exist_ok=True);(ROOT/'fixtures').mkdir(exist_ok=True)
    with ThreadPoolExecutor(4) as pool:
        result=list(pool.map(acquire_one,MISSIONS.items()))
        result+=list(pool.map(acquire_extra,EXTRAS.items()))
    (ROOT/'sources-draft.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for r in result: print(r['id'],r['bytes'])


if __name__=='__main__': main()
