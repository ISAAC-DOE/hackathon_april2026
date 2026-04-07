#!/bin/bash
#SBATCH --job-name=uma_Cu100_CO2_a100
#SBATCH --account=lcls:default
#SBATCH --partition=ampere
#SBATCH --qos=preemptable
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:15:00
#SBATCH --output=/sdf/home/d/dsokaras/hackathon_april2026/logs/benchmark/uma_Cu100_CO2_a100-%j.out
#SBATCH --error=/sdf/home/d/dsokaras/hackathon_april2026/logs/benchmark/uma_Cu100_CO2_a100-%j.err

source /sdf/group/ssrl/dsokaras/miniconda3/bin/activate
conda activate fairchem

cd /sdf/home/d/dsokaras/hackathon_april2026

python scripts/uma_systematic_benchmark.py \
    --model uma-s-1p2 \
    --surface Cu100 \
    --adsorbate CO2 \
    --outdir /sdf/home/d/dsokaras/hackathon_april2026/results/uma_benchmark
