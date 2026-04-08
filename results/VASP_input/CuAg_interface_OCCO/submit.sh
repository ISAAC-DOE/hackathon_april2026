#!/bin/bash
#SBATCH -A mxxxx
#SBATCH -q regular
#SBATCH -J CuAg_interface_OCCO
#SBATCH -t 8:00:00
#SBATCH -N 2
#SBATCH -C cpu
#SBATCH --mail-type=ALL
#SBATCH --mail-user=user@example.com

module load vasp/6.4.3-cpu

export OMP_NUM_THREADS=2
export OMP_PLACES=threads
export OMP_PROC_BIND=spread

srun -n 128 -c 4 --cpu-bind=cores vasp_std
