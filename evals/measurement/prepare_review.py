"""Prepare an UNAPPROVED public-human-label review package, without inference.

No answers are printed. The sealed proposal must be transferred to an independent
custodian; local file separation is not an access-control or review attestation.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from xml.sax.saxutils import escape

HERE=Path(__file__).resolve().parent


def digest(value): return hashlib.sha256(value).hexdigest()
def key(value): return digest(('t39-v2-selection-1:'+value).encode())


def write_json(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')


def load_sources(root):
    lock=json.loads((HERE/'public-sources.json').read_text(encoding='utf-8'))
    loaded={}
    for item in lock['sources']:
        raw=(root/item['file']).read_bytes()
        if len(raw)!=item['bytes'] or digest(raw)!=item['sha256']:
            raise ValueError('source differs from pinned bytes: '+item['file'])
        if item['file'].endswith('.json'): loaded[item['file']]=json.loads(raw)
    return loaded,lock


def proposals(sources):
    rows=[]
    for article in sources['squad-dev.json']['data']:
        for n,paragraph in enumerate(article['paragraphs']):
            text=paragraph['context']
            doc='squad-'+key(article['title']+':'+str(n))[:16]
            for q in paragraph['qas']:
                answers=q['answers']
                if not q['is_impossible'] and not answers: continue
                if any(text[a['answer_start']:a['answer_start']+len(a['text'])]!=a['text'] for a in answers):
                    raise ValueError('source span mismatch')
                rows.append({'id':'squad-'+q['id'],'source':'squad','family':'squad:'+article['title'],
                    'document_id':doc,'format':'txt','structure':'prose','question':q['question'],
                    'expected':'insufficient_evidence' if q['is_impossible'] else 'supported',
                    'alternatives':list(dict.fromkeys(a['text'] for a in answers)),
                    'support':answers,'text':text,'original_id':q['id'],
                    'transformation':'Unchanged scoped source paragraph; not the entire Wikipedia article.'})
    for paper_id,paper in sources['qasper-dev.json'].items():
        paragraphs=[paper['title'],paper['abstract']]
        for section in paper['full_text']:
            if section['section_name']: paragraphs.append(section['section_name'])
            paragraphs.extend(section['paragraphs'])
        paragraphs.extend(f['caption'] for f in paper['figures_and_tables'])
        text='\n\n'.join(paragraphs)
        for q in paper['qas']:
            answers=[x['answer'] for x in q['answers']]
            negative=bool(answers) and all(a['unanswerable'] for a in answers)
            positive=bool(answers) and all(not a['unanswerable'] and len(a['extractive_spans'])==1
                and a['extractive_spans'][0] in text and a['evidence']
                and all(e in text for e in a['evidence']) for a in answers)
            if not (negative or positive): continue
            rows.append({'id':'qasper-'+q['question_id'],'source':'qasper','family':'qasper:'+paper_id,
                'document_id':'qasper-'+paper_id,'format':'txt','structure':'prose','question':q['question'],
                'expected':'insufficient_evidence' if negative else 'supported',
                'alternatives':list(dict.fromkeys(a['extractive_spans'][0] for a in answers)) if positive else [],
                'support':answers,'text':text,'original_id':q['question_id'],
                'transformation':'Complete supplied text/abstract/section names/captions in order. Images not supplied; reviewer must exclude any visual dependence.'})
    for doc in sources['tatqa-dev.json']:
        table=doc['table']['table']
        records=[{'row_index':i,'headers':table[0],'cells':row} for i,row in enumerate(table)]
        records += [{'paragraph_order':p['order'],'text':p['text']} for p in doc['paragraphs']]
        text=json.dumps({'records':records},ensure_ascii=False,indent=2)
        for q in doc['questions']:
            if q['answer_type']!='span' or q['answer_from']!='table' or q['req_comparison'] or len(q['answer'])!=1:
                continue
            matches=[{'record_index':i,'pointer':'/cells/'+str(j)} for i,row in enumerate(table)
                     for j,cell in enumerate(row) if cell==q['answer'][0]]
            if not matches: continue
            uid=doc['table']['uid']
            rows.append({'id':'tatqa-'+q['uid'],'source':'tatqa','family':'tatqa-provisional:'+uid,
                'family_requires_review':True,'document_id':'tatqa-'+uid,'format':'json','structure':'table',
                'question':q['question'],'expected':'supported','alternatives':q['answer'],
                'support':{'possible_exact_cells':matches,'scale':q['scale'],'source_question':q},
                'text':text,'original_id':q['uid'],
                'transformation':'Table rows with unchanged string cells and repeated source first-row headers; all source paragraphs retained as records. Ingest /records. Table IDs are NOT verified report-family IDs.'})
    return rows


def select(rows):
    quotas={('squad','supported'):50,('squad','insufficient_evidence'):40,
            ('qasper','supported'):20,('qasper','insufficient_evidence'):10,('tatqa','supported'):60}
    selected=[]
    per_family=Counter()
    for (source,outcome),count in quotas.items():
        eligible=sorted((r for r in rows if (r['source'],r['expected'])==(source,outcome)),key=lambda r:key(r['id']))
        chosen=[]
        for r in eligible:
            # Family caps prevent one frequently annotated source dominating.
            limit=6 if source=='squad' else 2
            if per_family[r['family']]<limit:
                chosen.append(r.copy()); per_family[r['family']]+=1
            if len(chosen)==count: break
        if len(chosen)!=count: raise ValueError(f'insufficient eligible {source}/{outcome}: {len(chosen)}/{count}')
        selected.extend(chosen)
    families=defaultdict(list)
    for r in selected: families[r['family']].append(r)
    sealed=set()
    for family in sorted(families,key=key):
        if len(sealed)>=20 and sum(len(families[f]) for f in sealed)>=60: break
        sealed.add(family)
    if len(families)-len(sealed)<20: raise ValueError('insufficient development families')
    # File-format probes use human-labelled paragraphs, not fabricated facts.
    # Never use a label or expected outcome to decide which sources become PDFs.
    pdf_docs=set()
    for r in sorted((r for r in selected if r['source']=='squad'),key=lambda r:key(r['document_id'])):
        pdf_docs.add(r['document_id'])
        if sum(x['document_id'] in pdf_docs for x in selected)>=30: break
    for r in selected:
        r['split']='sealed' if r['family'] in sealed else 'development'
        if r['document_id'] in pdf_docs:
            r['format']='pdf'
            r['transformation']+=' Controlled one-column typeset PDF, NOT the publisher layout; reviewer visual approval required.'
    return sorted(selected,key=lambda r:(r['split'],key(r['family']),key(r['id'])))


def render_pdf(path,text,font):
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    from reportlab.pdfgen.canvas import Canvas
    from pypdf import PdfReader
    pdfmetrics.registerFont(TTFont('ReviewSource',str(font)))
    style=ParagraphStyle('source',fontName='ReviewSource',fontSize=11,leading=16,spaceAfter=12)
    def canvas(*args,**kwargs):
        kwargs['invariant']=1
        return Canvas(*args,**kwargs)
    SimpleDocTemplate(str(path),pagesize=(612,792),leftMargin=54,rightMargin=54,
        topMargin=54,bottomMargin=54).build([Paragraph(escape(text),style)],canvasmaker=canvas)
    extracted=' '.join(p.extract_text() for p in PdfReader(path).pages)
    normalize=lambda s: re.sub(r'\s+',' ',s).strip()
    if normalize(extracted)!=normalize(text):
        raise ValueError('PDF text round trip differs; retain failed package for review')
    return {'renderer':'reportlab','version':reportlab.Version,'font_sha256':digest(font.read_bytes()),
            'pages':len(PdfReader(path).pages),'text_roundtrip':'passed','visual_review':'pending_independent_reviewer'}


def build(source_dir,output,font):
    sources,lock=load_sources(source_dir)
    rows=select(proposals(sources))
    output.mkdir(parents=True,exist_ok=False)
    counts={}
    for split in ('development','sealed'):
        dest=output/split; (dest/'documents').mkdir(parents=True)
        subset=[r for r in rows if r['split']==split]
        requests=[]; labels=[]; docs={}
        for row in subset:
            name=row['document_id']+'.'+row['format']
            path=dest/'documents'/name
            if name not in docs:
                render={}
                if row['format']=='pdf': render=render_pdf(path,row['text'],font)
                else: path.write_text(row['text'],encoding='utf-8',newline='\n')
                docs[name]={'path':'documents/'+name,'sha256':digest(path.read_bytes()),'bytes':path.stat().st_size,
                    'format':row['format'],'transformation':row['transformation'],'source':row['source'],
                    'family':row['family'],'rendering':render}
            requests.append({'case_id':row['id'],'family':row['family'],'split':split,
                'source':row['source'],'format':row['format'],'structure':row['structure'],
                'capability':'direct_extraction_proposal','document':name,
                'question':row['question'],'history':[],'prose':False})
            labels.append({k:v for k,v in row.items() if k not in ('text','question','transformation')}
                          | {'review_status':'pending','gold_fields':None,'approved_support':None})
        write_json(dest/'requests.json',requests)
        write_json(dest/'proposed-labels.json',labels)
        write_json(dest/'documents.json',list(docs.values()))
        write_json(dest/'review-template.json',{'approved':False,'reviewer':None,'custodian':None,
            'independent_of_implementation':False,'date':None,'package_manifest_sha256':None,
            'required_checks':['source-family mapping (especially TAT-QA reports)','exact typed alternatives and semantic field definitions',
             'negative scope','provenance/proof locations','PDF visual review','no unsupported reasoning in primary track',
             'no source family crosses splits after corrections','minimum counts/strata after exclusions'],
            'accepted_case_ids':[],'excluded':[]})
        counts[split]={'questions':len(subset),'families':len({r['family'] for r in subset}),
            'negative':sum(r['expected']!='supported' for r in subset),
            'formats':dict(Counter(r['format'] for r in subset)),'tables':sum(r['structure']=='table' for r in subset),
            'documents':len(docs),'pdf_pages':sum(d['rendering'].get('pages',0) for d in docs.values())}
    write_json(output/'source-lock.json',lock)
    (output/'protocol.md').write_bytes((HERE/'protocol.md').read_bytes())
    files={p.relative_to(output).as_posix():digest(p.read_bytes()) for p in sorted(output.rglob('*')) if p.is_file()}
    manifest={'version':1,'status':'UNAPPROVED_PROPOSAL_NOT_AN_EXECUTION_FREEZE','files':files,'counts':counts,
              'builder_sha256':digest(Path(__file__).read_bytes()),'sealed_custody':'pending_transfer',
              'limitations':['public data may be in model training','PDFs are controlled format probes',
                  'TAT-QA family IDs require report-level review','no independently authored new NASA/USGS labels',
                  'automatic proposal filters are not semantic adjudication','gold fields/support need independent approval']}
    write_json(output/'manifest.json',manifest)
    return {'manifest_sha256':digest((output/'manifest.json').read_bytes()),'status':manifest['status'],'counts':counts}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--font',type=Path,required=True,help='Unicode TrueType font; its hash is frozen in the output')
    a=p.parse_args()
    print(json.dumps(build(a.sources,a.output,a.font),indent=2))


if __name__=='__main__': main()
