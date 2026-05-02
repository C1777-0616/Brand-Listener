import os
import hashlib

ROOT = r"D:\wmz\Brand Listener"
TARGETS = [
    "BrandCultureListeningAgent.yaml",
    "OfficialUpdatesAgent.yaml",
]

def file_hash(path, block_size=65536):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(block_size), b''):
            h.update(chunk)
    return h.hexdigest()

def find_paths(root, fname):
    res = []
    for dirpath, dirnames, filenames in os.walk(root):
        if fname in filenames:
            res.append(os.path.join(dirpath, fname))
    return res

def main():
    for fname in TARGETS:
        paths = find_paths(ROOT, fname)
        if len(paths) <= 1:
            continue
        # Choose canonical as the shortest path (most flattened)
        canonical = min(paths, key=lambda p: len(p))
        for p in paths:
            if p == canonical:
                continue
            try:
                if os.path.exists(canonical) and file_hash(p) == file_hash(canonical):
                    os.remove(p)
                    print(f"Deleted duplicate {p} (identical to canonical {canonical})")
                else:
                    print(f"Retained potential duplicate {p} (differs from canonical {canonical})")
            except Exception as e:
                print(f"Error processing {p}: {e}")

if __name__ == "__main__":
    main()
