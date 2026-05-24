"""Generate a full fake archive.
Run: uv run python -m tests.make_fake_site
"""
import shutil
from pathlib import Path
from tests.fake_data import generate_fake_site

output_dir = Path("output_fake").resolve()
if output_dir.exists():
    shutil.rmtree(output_dir)
output_dir.mkdir(parents=True)
generate_fake_site(output_dir, copy_css=True)
print(f"Generated: file:///{output_dir / 'index.html'}")

