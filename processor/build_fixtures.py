"""Explicit fixture authoring only; never called by tests or validation."""
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

ROOT = Path(__file__).parent / 'fixtures'


def raster(lines):
    image = Image.new('RGB', (1400, 280), 'white')
    draw = ImageDraw.Draw(image)
    # The Docker fixture-authoring environment supplies this fixed font.
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 36)
    for i, line in enumerate(lines):
        draw.text((30, 25 + 65*i), line, font=font, fill='black')
    return image


def build():
    ROOT.mkdir(exist_ok=True)
    mixed = canvas.Canvas(str(ROOT / 'mixed_regions.pdf'), pagesize=(612, 792), invariant=1)
    mixed.setFont('Helvetica-Bold', 18)
    mixed.drawString(48, 735, 'Synthetic mixed inspection')
    mixed.setFont('Helvetica', 12)
    mixed.drawString(48, 690, 'Native record: valve V8 opens at 24 kPa.')
    mixed.drawImage(ImageReader(raster(['Scanned record: valve V9 opens at 31 kPa.', 'Inspection batch: MIX-007.'])), 48, 360, width=516, height=103.2)
    mixed.drawString(48, 300, 'Native closing note: inspect again in 14 days.')
    mixed.save()

    overlay = canvas.Canvas(str(ROOT / 'mixed_overlay.pdf'), pagesize=(612, 792), invariant=1)
    overlay.setFont('Helvetica-Bold', 18)
    overlay.drawString(48, 735, 'Synthetic searchable scan')
    overlay.drawImage(ImageReader(raster(['Overlay record: valve V5 opens at 19 kPa.'])), 48, 480, width=516, height=103.2)
    # Simulate a scan with an already supplied invisible text layer.
    text = overlay.beginText(59, 560)
    text.setFont('Helvetica', 13.27)
    text.setTextRenderMode(3)
    text.textLine('Overlay record: valve V5 opens at 19 kPa.')
    overlay.drawText(text)
    overlay.save()

    graphic = canvas.Canvas(str(ROOT / 'uninterpreted_graphic.pdf'), pagesize=(612, 792), invariant=1)
    graphic.setFont('Helvetica-Bold', 18)
    graphic.drawString(48, 735, 'Synthetic diagram record')
    graphic.setFont('Helvetica', 12)
    graphic.drawString(48, 690, 'The diagram below has no machine-readable explanation.')
    picture = Image.new('RGB', (1000, 600), 'white')
    draw = ImageDraw.Draw(picture)
    draw.rectangle((80, 100, 350, 400), fill='#367bbd')
    draw.ellipse((620, 100, 920, 400), fill='#df8c37')
    draw.line((350, 250, 620, 250), fill='black', width=9)
    graphic.drawImage(ImageReader(picture), 48, 250, width=516, height=309.6)
    graphic.save()


if __name__ == '__main__':
    build()
