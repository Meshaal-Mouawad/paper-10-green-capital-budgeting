"""Optional pixel/byte replay for the original Matplotlib 3.10.8 figures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import matplotlib
from PIL import Image
from public_inputs import ScientificInputs


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("--output", type=Path, default=Path("historical_figure_replay"))
    args = parser.parse_args()
    if matplotlib.__version__ != "3.10.8":
        parser.error("Use Matplotlib 3.10.8 to compare the original figure renderer.")
    ScientificInputs(args.baseline)
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root/"results").mkdir()
        (root/"study").mkdir()
        shutil.copyfile(args.baseline/"results/mode_summary.csv", root/"results/mode_summary.csv")
        shutil.copyfile(args.baseline/"study/create_figures.py", root/"study/create_figures.py")
        env = dict(os.environ, SOURCE_DATE_EPOCH="1795374420", PYTHONDONTWRITEBYTECODE="1")
        subprocess.run([sys.executable, str(root/"study/create_figures.py")], check=True, env=env)
        status = {}
        for expected in sorted((args.baseline/"figures").iterdir()):
            generated = root/"figures"/expected.name
            if expected.suffix == ".pdf":
                left, right = digest(expected.read_bytes()), digest(generated.read_bytes())
                method = "PDF file SHA-256 with original creation time"
            else:
                with Image.open(expected) as a, Image.open(generated) as b:
                    assert a.size == b.size, expected.name
                    left, right = digest(a.convert("RGBA").tobytes()), digest(b.convert("RGBA").tobytes())
                method = "SHA-256 of uncompressed RGBA pixels after checking image dimensions"
            if left != right:
                raise ValueError(f"Historical figure differs: {expected.name}")
            status[expected.name] = dict(method=method, original_sha256=left, replay_sha256=right, matched=True)
        report = dict(matplotlib=matplotlib.__version__, original_pdf_timestamp_utc="2026-11-22T19:07:00Z",
                      figures=status)
        (args.output/"historical_figure_confirmation.json").write_text(json.dumps(report,indent=2)+"\n")
        print("Both original PDFs and both original PNG pixel arrays match.")


if __name__ == "__main__":
    main()
