#!/bin/bash
#SBATCH -J CuAg_CHO_neb
#SBATCH -q regular
#SBATCH -A mxxxx
#SBATCH -C cpu
#SBATCH -N 2
#SBATCH -t 8:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=user@example.com

module load vasp-tpc/6.4.2-cpu
export OMP_NUM_THREADS=2
export OMP_PLACES=threads
export OMP_PROC_BIND=spread

# NOTE: For NEB, adjust nodes and image-parallel launch as needed.
python run_custodian.py
