#!/bin/bash
#SBATCH --job-name=test_eads
#SBATCH --account=ssrl:isaac
#SBATCH --partition=ada
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:10:00
#SBATCH --output=logs/test_eads-%j.out
#SBATCH --error=logs/test_eads-%j.err

source /sdf/group/ssrl/dsokaras/miniconda3/bin/activate
conda activate fairchem
cd /sdf/home/d/dsokaras/hackathon_april2026
mkdir -p logs
python scripts/test_eads_approach.py
