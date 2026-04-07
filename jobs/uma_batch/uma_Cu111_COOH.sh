#!/bin/bash
#SBATCH --job-name=uma_Cu111_COOH
#SBATCH --account=ssrl:isaac
#SBATCH --partition=ada
#SBATCH --gres=gpu:l40s:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:15:00
#SBATCH --qos=normal
#SBATCH --output=/sdf/home/d/dsokaras/hackathon_april2026/logs/uma_Cu111_COOH-%j.out
#SBATCH --error=/sdf/home/d/dsokaras/hackathon_april2026/logs/uma_Cu111_COOH-%j.err

source /sdf/group/ssrl/dsokaras/miniconda3/bin/activate
conda activate fairchem

cd /sdf/home/d/dsokaras/hackathon_april2026

python /sdf/home/d/dsokaras/hackathon_april2026/scripts/uma_systematic_benchmark.py --model uma-s-1p2 --surface Cu111 --adsorbate COOH --outdir /sdf/home/d/dsokaras/hackathon_april2026/results/uma_benchmark
