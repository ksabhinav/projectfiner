"""Render public/og-image.svg → public/og-image.png (1200×630) for OG meta."""
import os
os.environ.setdefault('DYLD_FALLBACK_LIBRARY_PATH', '/opt/homebrew/lib')
os.environ.setdefault('DYLD_LIBRARY_PATH', '/opt/homebrew/lib')
import cairosvg
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / 'public/og-image.svg'
PNG = ROOT / 'public/og-image.png'
cairosvg.svg2png(url=str(SVG), write_to=str(PNG),
                 output_width=1200, output_height=630)
print(f'  wrote {PNG.relative_to(ROOT)} ({PNG.stat().st_size//1024} KB)')
