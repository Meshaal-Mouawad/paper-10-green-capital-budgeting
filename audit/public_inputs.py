"""Directory-backed reader for the hash-pinned scientific release."""
import hashlib
from pathlib import Path

SCIENCE_MANIFEST_SHA256 = "c8c176e90c62d6f013a6480267474db38b906b120203f54fe9734c8aafd9acd3"

class ScientificInputs:
    def __init__(self, directory):
        self.root = Path(directory)
        manifest = self.root / "SHA256SUMS.txt"
        data = manifest.read_bytes()
        if hashlib.sha256(data).hexdigest() != SCIENCE_MANIFEST_SHA256:
            raise ValueError("Scientific baseline manifest differs from the pinned release.")
        self.files = {"SHA256SUMS.txt"}
        for line in data.decode().splitlines():
            expected, name = line.split("  ", 1)
            if hashlib.sha256((self.root / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f"Scientific baseline file mismatch: {name}")
            self.files.add(name)

    def namelist(self):
        return sorted(self.files)

    def open(self, name):
        if name not in self.files:
            raise KeyError(name)
        return (self.root / name).open("rb")

    def read(self, name):
        with self.open(name) as stream:
            return stream.read()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False
