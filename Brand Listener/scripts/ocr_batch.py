"""
Batch OCR script - processes all entries missing ocr_analysis.
Saves progress every 10 entries.
"""
import json, time, sys, os

# Ensure project root in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.searcher.ocr_agent import OCRAgent
from src.utils.config import get_ocr_agent_config

STORE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "entries_store.json")

def main():
    print("Loading entries...", flush=True)
    with open(STORE_PATH, 'r', encoding='utf-8') as f:
        entries = json.load(f)

    config = get_ocr_agent_config()
    config['ocr_max_images'] = 1
    config['ocr_timeout_seconds'] = 15  # Per-image timeout
    agent = OCRAgent(config)

    # Filter entries that need OCR
    to_process = []
    for e in entries:
        em = e.get('engagement_metrics') or {}
        if em.get('ocr_analysis'):
            continue
        urls = agent._extract_image_urls(e)
        if urls:
            to_process.append(e)

    print(f"Total entries: {len(entries)}", flush=True)
    print(f"Already have OCR: {len(entries) - len(to_process)}", flush=True)
    print(f"Need OCR: {len(to_process)}", flush=True)

    if not to_process:
        print("Nothing to process!", flush=True)
        return

    start = time.time()
    processed = 0
    brands_found = 0
    products_found = 0

    for i, entry in enumerate(to_process):
        try:
            result = agent.process_entry(entry)
            processed += 1
            if result.get('brands'):
                brands_found += 1
            if result.get('products'):
                products_found += 1

            if processed % 10 == 0:
                elapsed = time.time() - start
                rate = processed / elapsed
                remaining = (len(to_process) - processed) / rate if rate > 0 else 0
                print(f"Progress: {processed}/{len(to_process)} ({processed*100//len(to_process)}%) | brands: {brands_found}, products: {products_found} | {rate:.2f} entries/s | ETA: {remaining/60:.1f}min", flush=True)
                # Save progress
                with open(STORE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(entries, f, ensure_ascii=False, default=str)
        except Exception as e:
            print(f"Error on entry {entry.get('id', '?')}: {e}", flush=True)
            # Set empty OCR on error
            em = entry.setdefault('engagement_metrics', {})
            em['ocr_analysis'] = {
                "brands": [], "products": [], "ingredients": [],
                "raw_texts": [], "image_count": 0, "error": str(e),
            }

    # Final save
    with open(STORE_PATH, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, default=str)

    elapsed = time.time() - start
    print(f"\nDone! Processed {processed}/{len(to_process)} in {elapsed:.0f}s ({elapsed/60:.1f}min)", flush=True)
    print(f"OCR found brands in {brands_found} entries, products in {products_found} entries", flush=True)

if __name__ == "__main__":
    main()
