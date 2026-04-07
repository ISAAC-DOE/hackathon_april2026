#!/bin/bash
#SBATCH --job-name=uma_bench
#SBATCH --account=ssrl:isaac
#SBATCH --partition=ada
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=results/uma_benchmark/ada_%x_%j.out
#SBATCH --error=results/uma_benchmark/ada_%x_%j.err

# Args: --model MODEL --surface SURFACE --adsorbate ADS
source /sdf/group/ssrl/dsokaras/miniconda3/bin/activate
conda activate fairchem

cd /sdf/home/d/dsokaras/hackathon_april2026
mkdir -p results/uma_benchmark

python scripts/uma_systematic_benchmark.py "$@"
