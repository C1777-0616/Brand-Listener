import os
import hashlib
import argparse

def file_hash(path, block_size=65536):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(block_size), b''):
            h.update(chunk)
    return h.hexdigest()

def files_identical(a, b):
    try:
        return file_hash(a) == file_hash(b)
    except Exception:
        return False

def main(root):
    # Support multiple canonical candidate paths due to historical nesting.
    candidates_brand = [
        os.path.normpath(os.path.join(root, 'Brand Listener/agents/searcher/BrandCultureListeningAgent.yaml')),
        os.path.normpath(os.path.join(root, 'Brand Listener/Brand Listener/agents/searcher/BrandCultureListeningAgent.yaml')),
    ]
    candidates_official = [
        os.path.normpath(os.path.join(root, 'Brand Listener/agents/searcher/OfficialUpdatesAgent.yaml')),
        os.path.normpath(os.path.join(root, 'Brand Listener/Brand Listener/agents/searcher/OfficialUpdatesAgent.yaml')),
        os.path.normpath(os.path.join(root, 'Brand Listener/Brand Listener/BrandListener/agents/searcher/OfficialUpdatesAgent.yaml'))
    ]

    canonical_brand = next((p for p in candidates_brand if os.path.exists(p)), None)
    canonical_official = next((p for p in candidates_official if os.path.exists(p)), None)

    # Walk and collect duplicates (same filename in nested paths)
    to_delete = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fname in filenames:
            if fname in ('BrandCultureListeningAgent.yaml', 'OfficialUpdatesAgent.yaml'):
                fpath = os.path.join(dirpath, fname)
                # skip canonical locations (best-effort)
                if canonical_brand and os.path.normpath(fpath) == os.path.normpath(canonical_brand):
                    continue
                if canonical_official and os.path.normpath(fpath) == os.path.normpath(canonical_official):
                    continue
                if fname == 'BrandCultureListeningAgent.yaml' and canonical_brand:
                    target = canonical_brand
                elif fname == 'OfficialUpdatesAgent.yaml' and canonical_official:
                    target = canonical_official
                else:
                    target = None
                if target and os.path.exists(target) and files_identical(fpath, target):
                    to_delete.append(fpath)
                else:
                    print(f"[WARN] Duplicate {fpath} exists but differs from canonical; left in place.")

    # Delete duplicates (only after collecting all to avoid partial states)
    for p in to_delete:
        try:
            os.remove(p)
            print("Deleted duplicate:", p)
        except Exception as e:
            print("Failed to delete", p, ":", e)

    print("Path normalization pass completed.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=os.getcwd(), help='Root path to search')
    args = parser.parse_args()
    main(args.root)
