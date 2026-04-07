"""
Collect and summarize all UMA benchmark results into a single table.
Usage: python scripts/collect_benchmark_results.py
"""
import json
import os
import glob

RESULTS_DIR = "results/uma_benchmark"

def main():
    files = sorted(glob.glob(f"{RESULTS_DIR}/uma-s-1p2_*.json"))
    if not files:
        print(f"No results found in {RESULTS_DIR}/")
        return

    results = []
    for f in files:
        with open(f) as fh:
            r = json.load(fh)
            results.append(r)

    # Print table
    print(f"\n{'='*100}")
    print(f"  UMA-s-1p2 Systematic Benchmark: CO2RR Adsorption Energies")
    print(f"{'='*100}")
    print(f"{'Surface':<12} {'Adsorbate':<8} {'E_ads(eV)':>10} {'E_slab+ads':>12} {'E_slab':>12} {'Steps':>6} {'Time(s)':>8} {'fmax':>8} {'Status':<10}")
    print(f"{'-'*100}")

    for r in sorted(results, key=lambda x: (x.get('surface',''), x.get('adsorbate',''))):
        if r.get('status') == 'completed':
            print(f"{r['surface']:<12} {r['adsorbate']:<8} {r['E_ads_eV']:>10.4f} "
                  f"{r['E_slab_ads_eV']:>12.4f} {r['E_slab_eV']:>12.4f} "
                  f"{r.get('n_steps_ads','?'):>6} {r.get('total_time_s','?'):>8.1f} "
                  f"{r.get('final_fmax_ads',0):>8.4f} {r['status']:<10}")
        else:
            print(f"{r.get('surface','?'):<12} {r.get('adsorbate','?'):<8} {'ERROR':>10} "
                  f"{'':>12} {'':>12} {'':>6} {'':>8} {'':>8} {r.get('error','unknown')[:30]}")

    # Summary by surface
    completed = [r for r in results if r.get('status') == 'completed']
    print(f"\n{'='*60}")
    print(f"  Completed: {len(completed)}/{len(results)}")
    print(f"{'='*60}")

    # Pivot table: surfaces as rows, adsorbates as columns
    surfaces = sorted(set(r['surface'] for r in completed))
    adsorbates = sorted(set(r['adsorbate'] for r in completed))

    print(f"\n  E_ads (eV) pivot table:")
    header = f"{'Surface':<12}" + "".join(f"{a:>10}" for a in adsorbates)
    print(f"  {header}")
    print(f"  {'-'*len(header)}")

    for s in surfaces:
        row = f"  {s:<12}"
        for a in adsorbates:
            match = [r for r in completed if r['surface'] == s and r['adsorbate'] == a]
            if match:
                row += f"{match[0]['E_ads_eV']:>10.3f}"
            else:
                row += f"{'---':>10}"
        print(row)

    # Save combined
    combined_file = f"{RESULTS_DIR}/all_results_combined.json"
    with open(combined_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nCombined results saved to {combined_file}")


if __name__ == "__main__":
    main()
