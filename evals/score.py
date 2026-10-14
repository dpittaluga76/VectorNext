"""Deterministic source-coverage scoring; no inference and no automatic entailment claim."""
import json
import re
import unicodedata


def normalize(text):
    return ' '.join(re.findall(r'[^\W_]+',unicodedata.normalize('NFKC',text).lower(),re.UNICODE))


def exact(a,b):
    if type(a) is not type(b): return False
    if isinstance(a,dict): return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
    if isinstance(a,list): return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    return a==b


def pointer_parts(pointer):
    return [] if not pointer else [s.replace('~1','/').replace('~0','~') for s in pointer[1:].split('/')]


def ancestor(parent,child):
    a,b=pointer_parts(parent),pointer_parts(child)
    return b[:len(a)]==a


def leaves(value,pointer):
    if isinstance(value,dict) and value:
        return [leaf for k,v in value.items() for leaf in leaves(v,pointer+'/'+k.replace('~','~0').replace('/','~1'))]
    if isinstance(value,list) and value:
        return [leaf for i,v in enumerate(value) for leaf in leaves(v,pointer+'/'+str(i))]
    return [pointer]


def resolve(value, parts):
    for part in parts: value=value[int(part)] if isinstance(value,list) else value[part]
    return value


def interval_covered(start,end,ranges):
    cursor=start
    for a,b in sorted(ranges):
        if b<=cursor: continue
        if a>cursor: return False
        cursor=max(cursor,b)
        if cursor>=end: return True
    return False


def geometry(gold,actual):
    g=gold['bbox']; a=actual['bbox']
    if gold['page']!=actual['page']: return False
    a=[a[0]-2,a[1]-2,a[2]+2,a[3]+2]
    overlap=max(0,min(a[2],g[2])-max(a[0],g[0]))*max(0,min(a[3],g[3])-max(a[1],g[1]))
    area=min((a[2]-a[0])*(a[3]-a[1]),(g[2]-g[0])*(g[3]-g[1]))
    return area>0 and overlap/area>=.8


class Scorer:
    def __init__(self,dataset,documents):
        self.gold={e['id']:e for e in dataset['evidence']}
        self.expected_docs={d['id']:d for d in dataset['documents']}
        self.documents=documents
        self.chunks={}
        for doc in documents.values():
            expected=self.expected_docs[doc['document_id']]
            if doc['original']['sha256']!=expected['sha256']: raise ValueError('source hash differs')
            for chunk in doc['chunks']:
                self.chunks[(doc['document_id'],doc['revision'],chunk['id'])]=chunk

    def chunk_item(self,key):
        c=self.chunks[(key['document_id'],key['revision'],key['chunk_id'])]
        return {'key':key,'text':c['evidence'],'sources':c['sources'],'record':None}

    def source_label_item(self,key):
        """Measure the original headings/PDF labels carried into reranking, without neighbors.

        Keep raw chunk coverage separately: metadata-only table units are not raw body text.
        Generated annotations never enter this measurement.
        """
        item=self.chunk_item(key); c=self.chunks[(key['document_id'],key['revision'],key['chunk_id'])]
        attrs=c.get('attributes',{})
        if 'record' in attrs and 'Generated' not in attrs['record']['derivation']: return item
        doc=self.documents[key['document_id']]; blocks={b['id']:b for b in doc.get('blocks',[])}
        parents=set()
        for span in c.get('spans',[]):
            parent=blocks[span['block_id']].get('parent')
            while parent:
                parents.add(parent); parent=blocks[parent].get('parent')
        text=[]; sources=list(item['sources'])
        for block in doc.get('blocks',[]):
            if block['kind']=='Heading' and block['id'] in parents:
                text.append(block['text']); sources.extend(block['sources'])
        context=attrs.get('pdf_context')
        if context and 'Generated' not in context['derivation'] and isinstance(context['value'],str):
            text.extend(line for line in context['value'].splitlines() if line.strip() and line not in text)
            sources.extend(context['sources'])
        return item | {'text':'\n\n'.join(text+[item['text']]),'sources':sources}

    def parse_fidelity(self,ids):
        result={}
        for id in ids:
            gold=self.gold[id]; doc=self.documents[gold['document_id']]
            if gold['locator']['kind']=='json':
                valid=False
                for block in doc['blocks']:
                    for source in block['sources']:
                        p=source['locator'].get('Json',{}).get('pointer')
                        if p is not None and ancestor(p,gold['locator']['pointer']):
                            try:
                                value=resolve(json.loads(block['text']),pointer_parts(gold['locator']['pointer'])[len(pointer_parts(p)):])
                                valid=valid or exact(value,gold['expected'])
                            except (ValueError,KeyError,TypeError,IndexError): pass
                result[id]={'exact_typed_value':valid}
            else:
                items=[{'key':{'document_id':doc['document_id'],'revision':doc['revision']},'text':b['text'],'sources':b['sources']} for b in doc['blocks']]
                result[id]=self.coverage(items,[id])[id]
        return result

    def coverage(self,items,ids):
        out={}
        for id in ids:
            e=self.gold[id]; g=e['locator']; located=[]; texts=[]; ranges=[]; pointers=[]
            for item in items:
                key=item['key']; doc=self.documents.get(key['document_id'])
                if not doc or key['document_id']!=e['document_id'] or key['revision']!=doc['revision']: continue
                matched=False
                for source in item['sources']:
                    if source['revision']!=doc['revision']: continue
                    locator=source['locator']
                    if g['kind']=='text' and 'Text' in locator:
                        r=locator['Text']['bytes']; ranges.append((r['start'],r['end'])); matched=True
                    elif g['kind']=='json' and 'Json' in locator:
                        pointers.append(locator['Json']['pointer']); matched=True
                    elif g['kind']=='pdf' and 'Pdf' in locator and geometry(g,locator['Pdf']):
                        located.append(True); matched=True
                if matched: texts.append(item['text'])
            if g['kind']=='text': location=interval_covered(g['byte_start'],g['byte_end'],ranges)
            elif g['kind']=='json': location=all(any(ancestor(p,leaf) for p in pointers) for leaf in leaves(e['expected'],g['pointer']))
            else: location=bool(located)
            # JSON exactness is checked against immutable parsed source records separately;
            # complete parent/leaf source mappings establish retrieval location credit.
            fidelity=None if g['kind']=='json' else normalize(e['expected']) in normalize(' '.join(texts))
            out[id]={'location':location,'text_fidelity':fidelity,'covered':location and (g['kind']!='pdf' or fidelity)}
        return out

    def stage(self,items,sets):
        if not sets: return {'recall':None,'complete':None,'first_complete_rank':None,'coverage':{}}
        ids=set().union(*map(set,sets)); coverage=self.coverage(items,ids)
        covered={k for k,v in coverage.items() if v['covered']}
        first=None
        for n in range(1,len(items)+1):
            found={k for k,v in self.coverage(items[:n],ids).items() if v['covered']}
            if any(set(s)<=found for s in sets): first=n; break
        return {'recall':max(len(set(s)&covered)/len(s) for s in sets),'complete':any(set(s)<=covered for s in sets),
            'first_complete_rank':first,'coverage':coverage}

    def case(self,case,report):
        expected=case['expected']; status=expected['status']
        sets=expected.get('support_sets',[])
        if status=='ambiguous': sets=[list({e for alt in expected['alternatives'] for e in alt['support_set']})]
        retrieval=report.get('retrieval') or {}; stages={}
        for name in ['dense','keyword','fused','results']:
            stages[name]=self.stage([self.chunk_item(h['key']) for h in retrieval.get(name,[])],sets)
        stages['reranked']=self.stage([self.chunk_item(h['key']) for h in report.get('ranked',[])],sets)
        stages['reranked_top5']=self.stage([self.chunk_item(h['key']) for h in report.get('ranked',[])[:5]],sets)
        stages['reranked_top5_with_source_labels']=self.stage([self.source_label_item(h['key']) for h in report.get('ranked',[])[:5]],sets)
        evidence=report.get('evidence',[])
        stages['context']=self.stage(evidence,sets)
        answer=report['answer']; fields={k:p['value'] for k,p in answer['fields'].items()}
        gold=expected.get('fields',{})
        proofs={}
        for field,proof in answer['fields'].items():
            item=next((e for e in evidence if e['id']==proof['evidence_id']),None)
            refs=expected.get('field_sources',{}).get(field,[])
            coverage=self.coverage([item] if item else [],refs)
            proofs[field]={'gold_source_overlap':any(v['covered'] for v in coverage.values()),'coverage':coverage}
        spans=[(e['key']['document_id'],e['key']['revision'],s['block_id'],s['bytes']['start'],s['bytes']['end']) for e in evidence for s in e['spans']]
        total=sum(end-start for _,_,_,start,end in spans); unique=0
        groups={}
        for d,r,b,a,z in spans: groups.setdefault((d,r,b),[]).append((a,z))
        for pairs in groups.values():
            end=-1
            for a,z in sorted(pairs): unique+=max(0,z-max(a,end)); end=max(end,z)
        return {'expected_status':status,'actual_status':answer['status'],'status_correct':answer['status']==status,
            'field_correct':sum(k in fields and exact(v,fields[k]) for k,v in gold.items()),'field_total':len(gold),
            'all_fields_correct':exact(fields,gold),'answer_correct':answer['status']==status and exact(fields,gold),
            'extra_fields':sorted(fields.keys()-gold.keys()),'template_correct':report.get('formatted')==case.get('presentation',{}).get('expected_text') if 'presentation' in case else None,
            'stages':stages,'proofs':proofs,'prompt_tokens':report.get('prompt_tokens'),
            'evidence_chars':sum(len(e['text']) for e in evidence),'source_span_bytes':total,'repeated_source_span_bytes':total-unique,
            'factual_support':'requires source review','mechanical_validation':report['validation']}
