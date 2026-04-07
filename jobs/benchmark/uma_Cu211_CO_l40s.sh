#!/bin/bash
#SBATCH --job-name=uma_Cu211_CO_l40s
#SBATCH --account=ssrl:isaac
#SBATCH --partition=ada
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:15:00
#SBATCH --output=/sdf/home/d/dsokaras/hackathon_april2026/logs/benchmark/uma_Cu211_CO_l40s-%j.out
#SBATCH --error=/sdf/home/d/dsokaras/hackathon_april2026/logs/benchmark/uma_Cu211_CO_l40s-%j.err

source /sdf/group/ssrl/dsokaras/miniconda3/bin/activate
conda activate fairchem

cd /sdf/home/d/dsokaras/hackathon_april2026

python scripts/uma_systematic_benchmark.py \
    --model uma-s-1p2 \
    --surface Cu211 \
    --adsorbate CO \
    --outdir /sdf/home/d/dsokaras/hackathon_april2026/results/uma_benchmark
