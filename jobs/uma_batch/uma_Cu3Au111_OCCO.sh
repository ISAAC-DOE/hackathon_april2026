#!/bin/bash
#SBATCH --job-name=uma_Cu3Au111_OCCO
#SBATCH --account=lcls:default
#SBATCH --partition=ampere
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:15:00
#SBATCH --qos=preemptable
#SBATCH --output=/sdf/home/d/dsokaras/hackathon_april2026/logs/uma_Cu3Au111_OCCO-%j.out
#SBATCH --error=/sdf/home/d/dsokaras/hackathon_april2026/logs/uma_Cu3Au111_OCCO-%j.err

source /sdf/group/ssrl/dsokaras/miniconda3/bin/activate
conda activate fairchem

cd /sdf/home/d/dsokaras/hackathon_april2026

python /sdf/home/d/dsokaras/hackathon_april2026/scripts/uma_systematic_benchmark.py --model uma-s-1p2 --surface Cu3Au111 --adsorbate OCCO --outdir /sdf/home/d/dsokaras/hackathon_april2026/results/uma_benchmark
