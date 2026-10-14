"""Structure-preserving offline PDF conversion. No access to database storage."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import tempfile

from processor.assets import ROOT, profile, verify

SETTINGS = json.loads((ROOT / 'settings.json').read_text())


def box(value, height):
    """Docling bounding/rotated boxes to top-left PDF points."""
    if hasattr(value, 'to_bounding_box'):
        value = value.to_bounding_box()
    value = value.to_top_left_origin(height)
    return [float(value.l), float(value.t), float(value.r), float(value.b)]


def overlap(a, b):
    area = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    return area / max(0.000001, min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1])))


def normalized(text):
    return ' '.join(text.split()).casefold()


def warning(code, page, message, bbox=None):
    return dict(code=code, page=page, message=message, bbox=bbox)


def preflight(path):
    from pypdf import PdfReader
    if not 0 < path.stat().st_size <= SETTINGS['max_bytes']:
        raise ValueError('PDF must contain 1..16 MiB of bytes')
    reader = PdfReader(path)
    if reader.is_encrypted:
        raise ValueError('Encrypted PDFs are unsupported')
    if not 0 < len(reader.pages) <= SETTINGS['max_pages']:
        raise ValueError('PDF exceeds page limit')
    sizes = []
    for page in reader.pages:
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        unit = float(page.get('/UserUnit', 1))
        if not all(math.isfinite(n) and 0 < n <= SETTINGS['max_page_points'] for n in (w*unit, h*unit)):
            raise ValueError('PDF exceeds page dimension limit')
        sizes.append((w, h))
    return sizes


def converter(models):
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractCliOcrOptions, OcrMode
    from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
    options = PdfPipelineOptions(
        artifacts_path=Path(models), generate_parsed_pages=True,
        accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=SETTINGS['threads']),
        ocr_options=TesseractCliOcrOptions(lang=SETTINGS['ocr_languages'],
            mode=OcrMode(SETTINGS['ocr_mode']), scale=SETTINGS['ocr_scale']),
        document_timeout=SETTINGS['timeout_seconds']-20,
        ocr_batch_size=1, layout_batch_size=1, table_batch_size=1, queue_max_size=4,
        enable_remote_services=False, allow_external_plugins=False,
        do_picture_classification=False, do_picture_description=False, do_chart_extraction=False)
    options.layout_options.model_spec.revision = SETTINGS['layout_revision']
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})


def adapt(result, source_sha256, expected_pages):
    from docling_core.types.doc import ContentLayer
    document = result.document
    warnings, pages, cells = [], [], {}
    for page in result.pages:
        number = page.page_no
        if page.size is None:
            warnings.append(warning('missing_page_geometry', None, f'No geometry for page {number}'))
            continue
        width, height = float(page.size.width), float(page.size.height)
        raw = page.parsed_page.textline_cells if page.parsed_page else []
        local = [dict(text=c.text, bbox=box(c.rect, height), ocr=c.from_ocr,
                      confidence=float(c.confidence)) for c in raw if c.text.strip()]
        cells[number] = local
        ocr = [c['confidence'] for c in local if c['ocr']]
        pages.append(dict(page=number, width=width, height=height,
                          native_cells=sum(not c['ocr'] for c in local), ocr_cells=len(ocr),
                          ocr_mean_confidence=sum(ocr)/len(ocr) if ocr else None))
        if not local:
            warnings.append(warning('empty_page', number, 'No readable text was extracted'))
        for c in local:
            if c['ocr'] and c['confidence'] < SETTINGS['low_ocr_confidence']:
                warnings.append(warning('low_ocr_confidence', number, c['text'], c['bbox']))
    sizes = {p['page']: p for p in pages}
    if len(pages) != expected_pages:
        warnings.append(warning('missing_pages', None, 'Not every source page was converted'))
    if result.status.value != 'success':
        warnings.append(warning('conversion_partial', None, str(result.status.value)))
    for error in result.errors:
        warnings.append(warning('conversion_error', None, str(error)))

    def region(page, bbox, start, end):
        matching = [c for c in cells.get(page, []) if overlap(c['bbox'], bbox) > 0.5]
        ocr = [c['confidence'] for c in matching if c['ocr']]
        if not matching:
            warnings.append(warning('unmatched_source', page, 'No native/OCR cells match extracted text', bbox))
        return dict(bytes=dict(start=start, end=end), page=page, bbox=bbox,
                    extraction='Ocr' if ocr or not matching else 'Native',
                    confidence=min(ocr) if ocr else None)

    def provenance(item, text):
        spans = []
        for p in item.prov:
            if p.page_no not in sizes:
                warnings.append(warning('missing_source_page', None, f'Item references missing page {p.page_no}'))
                continue
            start, end = p.charspan
            if len(item.prov) == 1:
                start, end = 0, len(text)
            if not 0 <= start < end <= len(text):
                warnings.append(warning('invalid_charspan', p.page_no, 'Item has no usable source text span'))
                continue
            spans.append(region(p.page_no, box(p.bbox, sizes[p.page_no]['height']),
                                len(text[:start].encode()), len(text[:end].encode())))
        return spans

    ordered = [item for item, _ in document.iterate_items(included_content_layers=set(ContentLayer))]
    items, table_reports = [], []
    section, heading, heading_sources = None, '', []
    top_seen = {}
    for item in ordered:
        label = str(item.label.value)
        if label == 'picture':
            for p in item.prov:
                if p.page_no in sizes:
                    warnings.append(warning('uninterpreted_picture', p.page_no,
                        'Picture/diagram semantics are not extracted', box(p.bbox, sizes[p.page_no]['height'])))
            continue
        text = getattr(item, 'text', '')
        if label == 'table':
            if len(item.prov) != 1 or item.prov[0].page_no not in sizes:
                warnings.append(warning('multipage_table', None, 'Cannot assign table cell boxes to pages safely'))
                continue
            page = item.prov[0].page_no
            height = sizes[page]['height']
            table_box = box(item.prov[0].bbox, height)
            data = item.data
            header_cells = [c for c in data.table_cells if c.column_header]
            headers = ' | '.join(c.text for c in header_cells)
            header_sources = [region(page, box(c.bbox, height) if c.bbox else table_box, 0, max(1, len(headers.encode()))) for c in header_cells]
            related = [ref.resolve(document) for ref in [*item.captions, *item.footnotes, *item.references]]
            context = '\n'.join(t for t in [heading, *(getattr(r, 'text', '') for r in related), headers] if t)
            support = heading_sources + [s for r in related for s in provenance(r, getattr(r, 'text', ''))] + header_sources
            rows = []
            for row in range(data.num_rows):
                selected = [c for c in data.table_cells if c.start_row_offset_idx <= row < c.end_row_offset_idx]
                selected.sort(key=lambda c: c.start_col_offset_idx)
                rowtext = ' | '.join(c.text for c in selected)
                if not rowtext.strip():
                    continue
                sources, offset = [], 0
                for c in selected:
                    end = offset + len(c.text.encode())
                    if end > offset:
                        sources.append(region(page, box(c.bbox, height) if c.bbox else table_box, offset, end))
                    offset = end + 3
                rows.append(dict(id=f'{item.self_ref}/row/{row}', kind='Table', role='table_row',
                    parent=item.self_ref, text=rowtext, sources=sources, context=context,
                    context_sources=support, section=section,
                    table=dict(id=item.self_ref, row=row, cells=[c.model_dump(mode='json') for c in selected]),
                    indexed=not all(c.column_header for c in selected)))
            text = '\n'.join(r['text'] for r in rows)
            if not text or not rows:
                warnings.append(warning('empty_table', page, 'Table has no extracted cells', table_box))
                continue
            items.append(dict(id=item.self_ref, kind='Table', role='table_container', parent=None,
                text=text, sources=[region(page, table_box, 0, len(text.encode()))],
                context=heading, context_sources=heading_sources, section=section, table=None, indexed=False))
            items.extend(rows)
            table_reports.append(dict(id=item.self_ref, page=page, num_rows=data.num_rows, num_cols=data.num_cols,
                captions=[r.cref for r in item.captions], footnotes=[r.cref for r in item.footnotes]))
            continue
        if not text.strip():
            continue
        sources = provenance(item, text)
        if not sources:
            continue
        furniture = label in ('page_header', 'page_footer') or item.content_layer == ContentLayer.FURNITURE
        # Repeated top-margin titles/subtitles must not reset a continued section.
        first = sources[0]
        if first['bbox'][1] < sizes[first['page']]['height'] * 0.15:
            key = re.sub(r'\s*[-–—]?\s*continued\s*$', '', normalized(text))
            if key in top_seen and top_seen[key] < first['page']:
                furniture = True
            top_seen.setdefault(key, first['page'])
        kind = 'Heading' if label in ('section_header', 'title') else 'List' if label == 'list_item' else 'Paragraph'
        candidate = dict(id=item.self_ref, kind=kind, role='furniture' if furniture else 'body', parent=None,
            text=text, sources=sources, context='' if kind == 'Heading' else heading,
            context_sources=[] if kind == 'Heading' else heading_sources, section=section,
            table=None, indexed=not furniture)
        # Deduplicate only matching text at overlapping source locations, preferring native.
        duplicate = next((old for old in items if normalized(old['text']) == normalized(text)
            and old['sources'][0]['page'] == first['page'] and overlap(old['sources'][0]['bbox'], first['bbox']) > 0.8), None)
        if duplicate:
            if first['extraction'] == 'Native' and duplicate['sources'][0]['extraction'] == 'Ocr':
                duplicate['sources'] = sources
            continue
        items.append(candidate)
        if kind == 'Heading' and not furniture:
            section, heading, heading_sources = item.self_ref, text, sources

    # Report text cells left out by the layout/assembly pipeline, even on SUCCESS.
    for page, local in cells.items():
        covered = [s['bbox'] for i in items for s in i['sources'] if s['page'] == page]
        for cell in local:
            if not any(overlap(cell['bbox'], b) > 0.5 for b in covered):
                warnings.append(warning('unmapped_text', page, cell['text'], cell['bbox']))
    if len(items) > SETTINGS['max_items']:
        raise ValueError('PDF exceeds extracted item limit')
    if not any(i['indexed'] for i in items):
        raise ValueError('PDF has no indexable evidence')
    return dict(schema=SETTINGS['schema'], source_sha256=source_sha256, profile_sha256=profile(),
                status='partial' if warnings else 'complete', pages=pages, items=items,
                warnings=warnings, tables=table_reports)


def extract(path, models, engine=None):
    path = Path(path)
    expected_pages = len(preflight(path))
    verify(models)
    result = (engine or converter(models)).convert(path, raises_on_error=False,
        max_num_pages=SETTINGS['max_pages'], max_file_size=SETTINGS['max_bytes'])
    artifact = adapt(result, hashlib.sha256(path.read_bytes()).hexdigest(), expected_pages)
    if len(json.dumps(artifact).encode()) > SETTINGS['max_output_bytes']:
        raise ValueError('PDF output exceeds 16 MiB limit')
    return artifact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--models', type=Path, default=Path('/models'))
    args = parser.parse_args()
    # A failed OCR subprocess/model cannot leave a CLI conversion running forever.
    # Raising into Docling is insufficient because it can swallow exceptions.
    signal.signal(signal.SIGALRM, lambda *_: os._exit(124))
    signal.alarm(SETTINGS['timeout_seconds'])
    artifact = extract(args.source, args.models)
    encoded = json.dumps(artifact, ensure_ascii=False, indent=2).encode()
    if len(encoded) > SETTINGS['max_output_bytes']:
        raise ValueError('Serialized PDF output exceeds 16 MiB limit')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=args.output.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(encoded)
    temporary.replace(args.output)
    print(json.dumps(dict(status=artifact['status'], pages=len(artifact['pages']),
        items=len(artifact['items']), warnings=len(artifact['warnings']), profile=artifact['profile_sha256'])))


if __name__ == '__main__':
    main()
