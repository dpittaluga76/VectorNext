"""Offline acceptance checks against synthetic source PDFs, never answer labels."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import resource
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from processor import pdf
from processor.assets import verify, profile


class ExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = Path(os.environ.get('PDF_MODELS', '/models'))
        verify(cls.models)
        cls.artifacts = {}
        cls.seconds = {}
        engine = pdf.converter(cls.models)
        sources = [Path('evals/fixtures/equipment_guide.pdf'), Path('evals/fixtures/scanned_note.pdf'),
                   *sorted(Path('processor/fixtures').glob('*.pdf'))]
        for source in sources:
            start = time.monotonic()
            cls.artifacts[source.stem] = pdf.extract(source, cls.models, engine)
            cls.seconds[source.stem] = round(time.monotonic()-start, 3)
        # Opt-in capture for Rust's offline adapter tests/report, not regeneration of gold.
        if output := os.environ.get('PDF_CAPTURE'):
            root = Path(output)
            root.mkdir(parents=True, exist_ok=True)
            for name, artifact in cls.artifacts.items():
                (root / (name+'.json')).write_text(json.dumps(artifact, indent=2, ensure_ascii=False)+'\n')
            (root / 'timings.json').write_text(json.dumps(cls.seconds, indent=2)+'\n')
            (root / 'resources.json').write_text(json.dumps(dict(
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                profile=profile(), cpus=2, memory_limit_gib=4), indent=2)+'\n')

    def test_native_structure_order_and_cross_page_section(self):
        a = self.artifacts['equipment_guide']
        self.assertEqual(a['status'], 'complete', a['warnings'])
        items = [i for i in a['items'] if i['indexed']]
        start = next(i for i in items if i['text'].startswith('When the Harbor'))
        end = next(i for i in items if i['text'].startswith('wait 8 minutes'))
        self.assertEqual(items.index(end), items.index(start)+1)
        self.assertEqual(start['section'], end['section'])
        self.assertEqual([s['page'] for s in start['sources']+end['sources']], [1,2])
        self.assertAlmostEqual(start['sources'][0]['bbox'][1], 696.102, places=2)
        self.assertTrue(all(s['extraction'] == 'Native' for i in items for s in i['sources']))
        self.assertTrue(any(i['role']=='furniture' and 'continued' in i['text'] for i in a['items']))

    def test_table_values_headers_units_and_cell_coordinates(self):
        a = self.artifacts['equipment_guide']
        row = next(i for i in a['items'] if i['text']=='H2 | 12 | 20')
        self.assertIn('Flow (L/min)', row['context'])
        self.assertIn('Water (C)', row['context'])
        self.assertIn('20 C', row['context'])
        self.assertEqual(row['table']['row'], 2)
        self.assertEqual([c['text'] for c in row['table']['cells']], ['H2','12','20'])
        self.assertAlmostEqual(row['sources'][1]['bbox'][0], 202.0)
        self.assertAlmostEqual(row['sources'][1]['bbox'][1], 275.102)
        self.assertTrue(row['context_sources'])

    def test_scanned_numbers_and_provenance(self):
        a = self.artifacts['scanned_note']
        self.assertEqual(a['status'], 'complete', a['warnings'])
        j2 = next(i for i in a['items'] if 'Connector J2' in i['text'])
        self.assertIn('6 N m', j2['text'])
        self.assertTrue(all(s['extraction']=='Ocr' and s['confidence']>=0.6 for s in j2['sources']))
        self.assertEqual(a['pages'][0]['native_cells'], 0)
        self.assertAlmostEqual(j2['sources'][0]['bbox'][1], 190, delta=3)

    def test_native_and_ocr_in_one_page(self):
        a = self.artifacts['mixed_regions']
        self.assertEqual(a['status'], 'complete', a['warnings'])
        v8 = next(i for i in a['items'] if 'valve V8' in i['text'])
        v9 = next(i for i in a['items'] if 'valve V9' in i['text'])
        self.assertIn('31 kPa', v9['text'])
        self.assertEqual(v8['sources'][0]['extraction'], 'Native')
        self.assertEqual(v9['sources'][0]['extraction'], 'Ocr')
        self.assertEqual(v9['sources'][0]['page'], v8['sources'][0]['page'])

    def test_searchable_scan_has_no_ocr_duplicate(self):
        a = self.artifacts['mixed_overlay']
        self.assertEqual(a['status'], 'complete', a['warnings'])
        matches = [i for i in a['items'] if 'valve V5' in i['text'] and i['indexed']]
        self.assertEqual(len(matches), 1)
        # Docling omits this invisible text layer and obtains the line by OCR.
        # Preserve the actual extraction method; do not claim native provenance.
        self.assertEqual(matches[0]['sources'][0]['extraction'], 'Ocr')

    def test_graphics_are_reported_as_partial(self):
        a = self.artifacts['uninterpreted_graphic']
        self.assertEqual(a['status'], 'partial')
        self.assertTrue(any(w['code']=='uninterpreted_picture' for w in a['warnings']))
        text = ' '.join(i['text'] for i in a['items'])
        self.assertNotIn('blue', text.lower())

    def test_all_coordinates_and_byte_ranges(self):
        for artifact in self.artifacts.values():
            self.assertEqual(artifact['profile_sha256'], profile())
            sizes = {p['page']:p for p in artifact['pages']}
            for item in artifact['items']:
                for source in item['sources']:
                    p=sizes[source['page']]
                    x0,y0,x1,y1=source['bbox']
                    self.assertTrue(0 <= x0 < x1 <= p['width'])
                    self.assertTrue(0 <= y0 < y1 <= p['height'])
                    start,end=source['bytes'].values()
                    self.assertTrue(0 <= start < end <= len(item['text'].encode()))
                    item['text'].encode()[start:end].decode()

    def test_missing_models_and_bad_input_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'Missing or changed model'):
                verify(directory)
            path=Path(directory)/'empty.pdf'
            path.write_bytes(b'')
            with self.assertRaisesRegex(ValueError, '1..16 MiB'):
                pdf.preflight(path)


class DiagnosticTests(unittest.TestCase):
    def result(self, confidence=0.99):
        from docling_core.types.doc import BoundingBox, CoordOrigin, ContentLayer
        bbox=BoundingBox(l=20,t=20,r=200,b=40,coord_origin=CoordOrigin.TOPLEFT)
        cell=NS(text='Parsed evidence',rect=bbox,from_ocr=True,confidence=confidence)
        item=NS(label=NS(value='text'),text=cell.text,self_ref='#/texts/0',content_layer=ContentLayer.BODY,
                prov=[NS(page_no=1,bbox=bbox,charspan=(0,len(cell.text)))])
        document=Mock()
        document.iterate_items.return_value=[(item,0)]
        return NS(document=document,errors=[],status=NS(value='success'),
            pages=[NS(page_no=1,size=NS(width=612,height=792),parsed_page=NS(textline_cells=[cell]))])

    def test_low_confidence_is_partial_even_when_converter_says_success(self):
        a=pdf.adapt(self.result(0.2),'0'*64,1)
        self.assertEqual(a['status'],'partial')
        self.assertEqual(a['warnings'][0]['code'],'low_ocr_confidence')
        self.assertEqual(a['items'][0]['sources'][0]['confidence'],0.2)

    def test_missing_page_is_partial_even_when_converter_says_success(self):
        a=pdf.adapt(self.result(),'0'*64,2)
        self.assertEqual(a['status'],'partial')
        self.assertTrue(any(w['code']=='missing_pages' for w in a['warnings']))

    def test_unmapped_native_text_is_reported(self):
        result=self.result()
        from docling_core.types.doc import BoundingBox, CoordOrigin
        result.pages[0].parsed_page.textline_cells.append(NS(text='Lost digits 007',from_ocr=False,confidence=1,
            rect=BoundingBox(l=20,t=120,r=200,b=140,coord_origin=CoordOrigin.TOPLEFT)))
        a=pdf.adapt(result,'0'*64,1)
        self.assertEqual(a['status'],'partial')
        self.assertTrue(any(w['code']=='unmapped_text' and w['message']=='Lost digits 007' for w in a['warnings']))

    def test_page_limit_prevents_conversion(self):
        with patch('pypdf.PdfReader',return_value=NS(is_encrypted=False,pages=[None]*33)):
            with self.assertRaisesRegex(ValueError,'page limit'):
                pdf.preflight(Path('evals/fixtures/equipment_guide.pdf'))

    def test_large_page_prevents_conversion(self):
        page=Mock();page.mediabox.width=10000;page.mediabox.height=792;page.get.return_value=1
        with patch('pypdf.PdfReader',return_value=NS(is_encrypted=False,pages=[page])):
            with self.assertRaisesRegex(ValueError,'dimension limit'):
                pdf.preflight(Path('evals/fixtures/equipment_guide.pdf'))


if __name__ == '__main__':
    unittest.main()
