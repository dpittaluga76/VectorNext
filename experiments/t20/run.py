"""T20 fixed protocol. Explicit commands create new artifacts; tests never regenerate them."""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import random
import struct
import time
from urllib.parse import urlsplit

import numpy as np
import psycopg

SIZES = (400, 1600)
FILTERS = ('all', 'scope5', 'attribute1', 'empty')
CONFIGS = ('vectornext', 'pg_exact', 'pg_hnsw40', 'pg_hnsw200')
DIM = 384
CHUNKS = 32
TOLERANCE = 1e-5
SOURCES = ('examples/vector_bench.rs', 'experiments/t20/run.py', 'experiments/t20/test_benchmark.py',
           'docs/t20-protocol.md', 'docs/t20-protocol-amendment-01.md', 'compose.benchmark.yaml', 'docker/benchmark.Dockerfile',
           'docker/benchmark-runner.Dockerfile', 'Cargo.toml', 'Cargo.lock')

def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def key(index, count):
    return f'd{index//CHUNKS:05}/c{index%CHUNKS:02}' if index < count*CHUNKS else f'z-sentinel/c{index%CHUNKS:02}'

def row_index(identifier, count):
    document, chunk = identifier.split('/')
    return (count if document == 'z-sentinel' else int(document[1:]))*CHUNKS + int(chunk[1:])

def eligible(index, scope, count):
    document = index//CHUNKS
    if scope == 'all': return True
    if scope == 'scope5': return document < count//20
    if scope == 'attribute1': return document < count and document % 100 == 0
    if scope == 'empty': return False
    raise ValueError('unknown filter')

def reference(vectors, query, scope, count):
    indices = np.array([i for i in range(len(vectors)) if eligible(i, scope, count)], dtype=np.int64)
    if not len(indices): return {'hits': [], 'boundary': [], 'required': [], 'eligible': 0}
    rows = vectors[indices].astype(np.float64)
    q = np.asarray(query, dtype=np.float64)
    scores = rows @ q / (np.linalg.norm(rows, axis=1)*np.linalg.norm(q))
    order = np.lexsort((indices, -scores))
    top = order[:10]
    boundary = scores[top[-1]] - TOLERANCE
    return {'hits': [{'id': key(int(indices[i]), count), 'score': float(scores[i])} for i in top],
            'boundary': [key(int(indices[i]), count) for i in np.flatnonzero(scores >= boundary)],
            'required': [key(int(indices[i]), count) for i in np.flatnonzero(scores > scores[top[-1]] + TOLERANCE)], 'eligible': len(indices)}

def score(hits, expected, query, vectors, scope, count, error=None):
    wanted = {h['id'] for h in expected['hits']}
    returned = [h['id'] for h in hits]
    valid = error is None and len(returned) == len(set(returned))
    numeric_ok = True
    q = np.asarray(query, dtype=np.float64)
    for hit in hits:
        try:
            i = row_index(hit['id'], count)
            if i < 0 or i >= len(vectors) or key(i, count) != hit['id'] or not eligible(i, scope, count):
                valid = False
                continue
            row = vectors[i].astype(np.float64)
            cosine = float(row @ q / (np.linalg.norm(row)*np.linalg.norm(q)))
            numeric_ok &= np.isfinite(hit['score']) and abs(cosine-hit['score']) <= TOLERANCE
        except (ValueError, IndexError, KeyError): valid = False
    strict_recall = len(wanted.intersection(returned))/len(wanted) if wanted else None
    ordered = all(a['score']+TOLERANCE >= b['score'] for a,b in zip(hits,hits[1:]))
    correct = valid and numeric_ok and ordered and len(returned) == len(wanted) and set(returned).issubset(expected['boundary']) and set(expected['required']).issubset(returned)
    return {'recall10': 0.0 if error and wanted else strict_recall, 'correct': bool(correct),
            'valid_ids': bool(valid), 'valid_scores': bool(numeric_ok), 'valid_order': bool(ordered), 'returned': len(returned)}

def update_digest(digest, doc):
    for i, (text, vector) in enumerate(zip(doc['texts'], doc['vectors'])):
        digest.update(f"{doc['id']}/c{i:02}\n{text}\n".encode())
        digest.update(struct.pack('<i', doc['bucket']))
        digest.update(np.asarray(vector, dtype='<f4').tobytes())

def prepare(directory):
    directory.mkdir(parents=True, exist_ok=False)
    rng = np.random.Generator(np.random.PCG64(20261015))
    centers = rng.normal(size=(128, DIM))
    def sample(n):
        values = centers[rng.integers(0, 128, size=n)] + .35*rng.normal(size=(n, DIM))
        return (values/np.linalg.norm(values, axis=1)[:, None]).astype(np.float32)
    source_root=Path('/source')
    files=sorted(set(SOURCES)|{str(p.relative_to(source_root)) for p in (source_root/'src').rglob('*') if p.is_file()})
    manifest = {'protocol': 't20-v1+recovery-amendment-01', 'sizes': list(SIZES), 'dimensions': DIM, 'queries_per_scope': 32,
                'source_hashes': {name: sha(source_root/name) for name in files}, 'corpora': {}}
    for count in SIZES:
        part = directory/str(count)
        part.mkdir()
        vectors = sample((count+1)*CHUNKS)
        queries = sample(32)
        np.save(part/'vectors.npy', vectors, allow_pickle=False)
        digest = hashlib.sha256()
        with (part/'documents.jsonl').open('x') as output:
            for document in range(count+1):
                identifier = f'd{document:05}' if document < count else 'z-sentinel'
                texts = [f'Synthetic T20 document {identifier} chunk {i}. ' + 'This invented passage records equipment inspection details for a database capacity comparison. '*6 for i in range(CHUNKS)]
                doc = {'id': identifier, 'bucket': document % 100 if document < count else -2, 'texts': texts,
                       'vectors': vectors[document*CHUNKS:(document+1)*CHUNKS].tolist()}
                if document == count:
                    before_digest = digest.hexdigest()
                    write_json(part/'sentinel.json', doc)
                else:
                    output.write(json.dumps(doc, separators=(',', ':'))+'\n')
                update_digest(digest, doc)
        requests = []
        for qid, query in enumerate(queries):
            for scope in FILTERS:
                requests.append({'id': f'{scope}-{qid:02}', 'filter': scope, 'vector': query.tolist(),
                    'expected': reference(vectors[:count*CHUNKS], query, scope, count),
                    'after_restart': reference(vectors, query, scope, count)})
        write_json(part/'queries.json', requests)
        manifest['corpora'][str(count)] = {'digest': before_digest, 'after_sentinel_digest': digest.hexdigest(),
            'files': {p.name: sha(p) for p in part.iterdir()}}
        print(f'Prepared {count} documents and independent references', flush=True)
    write_json(directory/'manifest.json', manifest)

def check_manifest(directory):
    manifest = json.loads((directory/'manifest.json').read_text())
    for name, expected in manifest['source_hashes'].items():
        if sha(Path('/source')/name) != expected: raise ValueError(f'execution source changed: {name}')
    for size, corpus in manifest['corpora'].items():
        for name, expected in corpus['files'].items():
            if sha(directory/size/name) != expected: raise ValueError(f'fixture changed: {size}/{name}')
    return manifest

class VectorNext:
    def __init__(self):
        target = urlsplit(os.environ.get('VECTORNEXT_BENCH_URL', 'http://vectornext:8080'))
        self.connection = http.client.HTTPConnection(target.hostname, target.port, timeout=180)
    def call(self, op, **kwargs):
        started = time.perf_counter()
        body = json.dumps({'op': op, **kwargs}, separators=(',', ':')).encode()
        self.connection.request('POST', '/bench', body, {'Content-Type': 'application/json'})
        response = self.connection.getresponse()
        raw = response.read()
        result = json.loads(raw)
        elapsed = (time.perf_counter()-started)*1000
        if response.status != 200: raise RuntimeError(result)
        return result, elapsed

def vector_literal(values):
    # Nine significant digits round-trip every finite float32 coordinate.
    return '['+','.join(format(float(v), '.9g') for v in values)+']'

class Postgres:
    def __init__(self, count):
        self.connection = psycopg.connect(autocommit=True, prepare_threshold=None)
        self.schema = f't20_{count}'
        self.count = count
    def setup(self):
        c = self.connection
        c.execute('CREATE EXTENSION IF NOT EXISTS vector')
        if c.execute('SELECT 1 FROM pg_namespace WHERE nspname=%s', (self.schema,)).fetchone():
            raise ValueError('schema already exists: use a new isolated project/volumes')
        c.execute(f'CREATE SCHEMA {self.schema}')
        c.execute(f'SET search_path TO {self.schema}, public')
        c.execute('CREATE TABLE documents (id text PRIMARY KEY, revision text NOT NULL, source text NOT NULL)')
        c.execute('CREATE TABLE chunks (id text PRIMARY KEY, document_id text NOT NULL REFERENCES documents(id), text text NOT NULL, bucket integer NOT NULL, embedding vector(384) NOT NULL)')
    def select(self): self.connection.execute(f'SET search_path TO {self.schema}, public')
    def insert(self, doc):
        started = time.perf_counter()
        with self.connection.transaction():
            self.connection.execute('INSERT INTO documents VALUES (%s,%s,%s)', (doc['id'], 'r1', '\n'.join(doc['texts'])))
            with self.connection.cursor().copy('COPY chunks (id,document_id,text,bucket,embedding) FROM STDIN') as copy:
                for i,(text,vector) in enumerate(zip(doc['texts'],doc['vectors'])):
                    copy.write_row((f"{doc['id']}/c{i:02}",doc['id'],text,doc['bucket'],vector_literal(vector)))
        return (time.perf_counter()-started)*1000
    def indexes(self, hnsw=False):
        started = time.perf_counter()
        if hnsw:
            self.connection.execute('CREATE INDEX chunks_hnsw ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)')
        else:
            self.connection.execute('CREATE INDEX chunks_document ON chunks(document_id)')
            self.connection.execute('CREATE INDEX chunks_bucket ON chunks(bucket)')
        self.connection.execute('ANALYZE chunks')
        return (time.perf_counter()-started)*1000
    def configure(self, config):
        ef = 200 if config == 'pg_hnsw200' else 40
        self.connection.execute(f'SET hnsw.ef_search={ef}')
        self.connection.execute("SET hnsw.iterative_scan='strict_order'")
        self.connection.execute('SET hnsw.max_scan_tuples=20000')
    def query(self, request, config, explain=False):
        started = time.perf_counter()
        v = vector_literal(request['vector'])
        condition, args = {'all': ('TRUE', []), 'scope5': ('document_id = ANY(%s)', [[f'd{i:05}' for i in range(self.count//20)]]),
                           'attribute1': ('bucket = %s', [0]), 'empty': ('bucket = %s', [-1])}[request['filter']]
        order = '(embedding <=> %s::vector) + 0, id' if config == 'pg_exact' else 'embedding <=> %s::vector'
        sql = f'SELECT id, 1 - (embedding <=> %s::vector) AS score FROM chunks WHERE {condition} ORDER BY {order} LIMIT 10'
        if explain: sql = 'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+sql
        rows = self.connection.execute(sql, [v, *args, v]).fetchall()
        elapsed = (time.perf_counter()-started)*1000
        if explain: return rows[0][0], elapsed
        return [{'id': identifier, 'score': score} for identifier,score in rows], elapsed
    def stats(self):
        c=self.connection
        def file(name): return c.execute('SELECT pg_read_file(%s,0,4096)',(f'/sys/fs/cgroup/{name}',)).fetchone()[0]
        return {'documents': c.execute('SELECT count(*) FROM documents').fetchone()[0],
                'chunks': c.execute('SELECT count(*) FROM chunks').fetchone()[0],
                'relation_bytes': c.execute("SELECT pg_total_relation_size('documents')+pg_total_relation_size('chunks')").fetchone()[0],
                'cluster_wal_bytes': int(c.execute('SELECT sum(size) FROM pg_ls_waldir()').fetchone()[0]),
                'memory': {'cgroup_current':file('memory.current'),'cgroup_peak':file('memory.peak'),'cpu_stat':file('cpu.stat')}}
    def digest(self):
        digest = hashlib.sha256()
        with self.connection.transaction(), self.connection.cursor(name='digest_rows') as cursor:
            cursor.execute('SELECT id,text,bucket,embedding::real[] FROM chunks ORDER BY id')
            for identifier,text,bucket,vector in cursor:
                digest.update(f'{identifier}\n{text}\n'.encode())
                digest.update(struct.pack('<i',bucket))
                digest.update(np.asarray(vector,dtype='<f4').tobytes())
        return digest.hexdigest()

def capture_query(vnx, pg, request, config, count, vectors, expected_name='expected'):
    started=time.perf_counter()
    try:
        if config == 'vectornext':
            result,elapsed=vnx.call('search',vector=request['vector'],filter=request['filter'],documents=count)
            hits=result['hits']; engine=result['engine_ms']
        else:
            hits,elapsed=pg.query(request,config); engine=None
        error=None
    except Exception as exception:
        hits=[]; elapsed=(time.perf_counter()-started)*1000; engine=None; error=repr(exception)
    return {'query':request['id'],'filter':request['filter'],'config':config,'client_ms':elapsed,'engine_ms':engine,
            'hits':hits,'error':error,**score(hits,request[expected_name],request['vector'],vectors,request['filter'],count,error)}

def run(directory, count):
    manifest=check_manifest(directory)
    part=directory/str(count)
    output=part/'run'
    output.mkdir(exist_ok=False)
    vnx=VectorNext(); pg=Postgres(count)
    opened,_=vnx.call('open',documents=count)
    stats,_=vnx.call('stats')
    if stats['documents']: raise ValueError('VectorNext corpus already populated')
    pg.setup()
    with (output/'ingestion.jsonl').open('x') as stream, (part/'documents.jsonl').open() as source:
        for n,line in enumerate(source):
            doc=json.loads(line)
            # Rotate insertion order; record each acknowledged per-document cost.
            timings={}
            for engine in (('vectornext','postgres') if n%2==0 else ('postgres','vectornext')):
                if engine=='vectornext': result,timings[engine]=vnx.call('insert',document=doc); timings['vnx_engine']=result['engine_ms']
                else: timings[engine]=pg.insert(doc)
            stream.write(json.dumps({'document':doc['id'],**timings})+'\n'); stream.flush()
            if n%100==0: print(f'{count}: loaded {n+1}',flush=True)
    indexes={'vectornext':vnx.call('index')[0], 'postgres_filter_ms':pg.indexes()}
    verified,_=vnx.call('verify')
    expected=manifest['corpora'][str(count)]['digest']
    pg_digest=pg.digest()
    if verified['digest']!=expected or pg_digest!=expected: raise ValueError('stored vectors/text/attributes differ')
    before_ann={'vectornext':vnx.call('stats')[0],'postgres':pg.stats()}
    indexes['postgres_hnsw_ms']=pg.indexes(hnsw=True)
    write_json(output/'preparation.json',{'open':opened,'indexes':indexes,'before_ann':before_ann,'verified_digest':expected})
    requests=json.loads((part/'queries.json').read_text())
    vectors=np.load(part/'vectors.npy',mmap_mode='r')[:count*CHUNKS]
    plans={}
    for config in CONFIGS[1:]:
        pg.configure(config)
        plans[config]={}
        for scope in FILTERS:
            request=next(q for q in requests if q['filter']==scope)
            plan,_=pg.query(request,config,explain=True)
            if config=='pg_exact' and 'chunks_hnsw' in json.dumps(plan): raise ValueError('exact query used ANN index')
            plans[config][scope]=plan
    write_json(output/'plans.json',plans)
    with (output/'queries.jsonl').open('x') as stream:
        for block in range(4):
            order=list(CONFIGS[block:]+CONFIGS[:block])
            if block%2: order.reverse()
            query_order=list(requests); random.Random(20261015+block).shuffle(query_order)
            for config in order:
                if config!='vectornext': pg.configure(config)
                for request in query_order:
                    record=capture_query(vnx,pg,request,config,count,vectors)
                    record.update(block=block,phase='first' if block==0 else 'warm')
                    stream.write(json.dumps(record,allow_nan=False)+'\n'); stream.flush()
                print(f'{count}: block {block} {config}',flush=True)
    settings={name:pg.connection.execute(f'SHOW {name}').fetchone()[0] for name in ('server_version','shared_buffers','work_mem','maintenance_work_mem','fsync','synchronous_commit','full_page_writes','max_parallel_workers_per_gather')}
    settings['pgvector']=pg.connection.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
    write_json(output/'final.json',{'vectornext':vnx.call('stats')[0],'postgres':pg.stats(),'settings':settings})
    checkpoint={}
    try:
        checkpoint['vectornext']={'ok':True,**vnx.call('checkpoint')[0]}
    except Exception as exception:
        checkpoint['vectornext']={'ok':False,'error':repr(exception),'recovery_path':'journal replay after rejected checkpoint'}
        checkpoint['reopen_after_rejection']=vnx.call('open',documents=count)[0]
        assert vnx.call('verify')[0]['digest']==expected,'checkpoint rejection changed acknowledged data'
    started=time.perf_counter(); pg.connection.execute('CHECKPOINT')
    checkpoint['postgres']={'ok':True,'client_ms':(time.perf_counter()-started)*1000}
    write_json(output/'checkpoint.json',checkpoint)
    sentinel=json.loads((part/'sentinel.json').read_text())
    vnx.call('insert',document=sentinel); pg.insert(sentinel)
    after=manifest['corpora'][str(count)]['after_sentinel_digest']
    if vnx.call('verify')[0]['digest']!=after or pg.digest()!=after: raise ValueError('sentinel not durable/identical')
    write_json(output/'recovery-pending.json',{'acknowledged_documents':count+1,'digest':after,'checkpoint':checkpoint})

def recover(directory,count):
    manifest=check_manifest(directory); part=directory/str(count)
    vnx=VectorNext(); pg=Postgres(count); pg.select()
    started=time.perf_counter(); opened,_=vnx.call('open',documents=count); index,_=vnx.call('index')
    reopen_ms=(time.perf_counter()-started)*1000
    expected=manifest['corpora'][str(count)]['after_sentinel_digest']
    vstats=vnx.call('verify')[0]; pstats=pg.stats()
    assert vstats['digest']==pg.digest()==expected,'recovered data differs'
    assert vstats['documents']==pstats['documents']==count+1
    vectors=np.load(part/'vectors.npy',mmap_mode='r'); records=[]
    pg.configure('pg_exact')
    for request in json.loads((part/'queries.json').read_text()):
        for config in ('vectornext','pg_exact'):
            records.append(capture_query(vnx,pg,request,config,count,vectors,'after_restart'))
    write_json(part/'run'/'recovery.json',{'open':opened,'index':index,'vnx_open_index_client_ms':reopen_ms,'digest':expected,
        'vectornext':vstats,'postgres':pstats,'queries':records,'all_exact_correct':all(r['correct'] for r in records)})
    if not all(r['correct'] for r in records): raise ValueError('recovery exact-query failures; inspect retained report')

def distributions(values):
    return {name:float(np.percentile(values,p)) for name,p in [('p50',50),('p95',95),('p99',99)]} if values else None

def summarize(directory):
    results={}
    for count in SIZES:
        output=directory/str(count)/'run'
        records=[json.loads(line) for line in (output/'queries.jsonl').read_text().splitlines()]
        identities={(r['block'],r['config'],r['query']) for r in records}
        if len(records)!=2048 or len(identities)!=2048:
            raise ValueError('incomplete or duplicate capture; preserve attempt without reporting reduced denominators')
        groups=[]
        for phase in ('first','warm'):
            for config in CONFIGS:
                for scope in FILTERS:
                    rows=[r for r in records if (r['phase'],r['config'],r['filter'])==(phase,config,scope)]
                    recall=[r['recall10'] for r in rows if r['recall10'] is not None]
                    groups.append({'phase':phase,'config':config,'filter':scope,'planned':len(rows),
                        'errors':sum(r['error'] is not None for r in rows),'correct':sum(r['correct'] for r in rows),
                        'mean_recall10':sum(recall)/len(recall) if recall else None,
                        'client_ms':distributions([r['client_ms'] for r in rows]),
                        'successful_client_ms':distributions([r['client_ms'] for r in rows if r['error'] is None])})
        ingestion=[json.loads(line) for line in (output/'ingestion.jsonl').read_text().splitlines()]
        results[str(count)]={'groups':groups,'ingestion':{e:{'total_ms':sum(r[e] for r in ingestion),'per_document_ms':distributions([r[e] for r in ingestion])} for e in ('vectornext','postgres')},
            'preparation':json.loads((output/'preparation.json').read_text()),'final':json.loads((output/'final.json').read_text()),'checkpoint':json.loads((output/'checkpoint.json').read_text()),
            'recovery':{k:v for k,v in json.loads((output/'recovery.json').read_text()).items() if k!='queries'}}
    write_json(directory/'summary.json',results)
    print(json.dumps({size:[g for g in r['groups'] if g['phase']=='warm' and g['filter']=='all'] for size,r in results.items()},indent=2))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['prepare','run','recover','summarize'])
    parser.add_argument('--run',required=True)
    parser.add_argument('--size',type=int,choices=SIZES)
    args=parser.parse_args()
    if not args.run.replace('-','').replace('_','').isalnum(): parser.error('simple new run name required')
    directory=Path('/results')/args.run
    if args.command=='prepare': prepare(directory)
    elif args.command=='summarize': summarize(directory)
    else:
        if args.size is None: parser.error('--size required')
        (run if args.command=='run' else recover)(directory,args.size)

if __name__=='__main__': main()
