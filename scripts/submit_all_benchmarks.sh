#!/bin/bash
# Submit systematic UMA benchmark across ada (L40S) and ampere (A100)
# 7 surfaces x 8 adsorbates x 1 model = 56 jobs per partition = 112 total
# Each job takes ~30-60s compute, request 10min wall time for safety

SCRIPT_DIR="/sdf/home/d/dsokaras/hackathon_april2026/scripts"
RESULTS_DIR="/sdf/home/d/dsokaras/hackathon_april2026/results/uma_benchmark"
JOB_DIR="/sdf/home/d/dsokaras/hackathon_april2026/jobs/benchmark"
LOG_DIR="/sdf/home/d/dsokaras/hackathon_april2026/logs/benchmark"

mkdir -p "$RESULTS_DIR" "$JOB_DIR" "$LOG_DIR"

SURFACES=("Cu111" "Cu100" "Cu211" "Au111" "Ag111" "Cu3Au111" "Cu3Ag111")
ADSORBATES=("CO" "H" "OH" "CHO" "COH" "OCCO" "COOH" "CO2")
MODEL="uma-s-1p2"

# Counter for alternating between partitions
count=0
ada_count=0
ampere_count=0

for surface in "${SURFACES[@]}"; do
    for adsorbate in "${ADSORBATES[@]}"; do
        # Alternate between ada and ampere
        if (( count % 2 == 0 )); then
            PARTITION="ada"
            ACCOUNT="ssrl:isaac"
            QOS="normal"
            GPU_TYPE="l40s"
            ((ada_count++))
        else
            PARTITION="ampere"
            ACCOUNT="lcls:default"
            QOS="preemptable"
            GPU_TYPE="a100"
            ((ampere_count++))
        fi

        JOBNAME="uma_${surface}_${adsorbate}_${GPU_TYPE}"
        JOBSCRIPT="${JOB_DIR}/${JOBNAME}.sh"

        cat > "$JOBSCRIPT" << SLURM_EOF
#!/bin/bash
#SBATCH --job-name=${JOBNAME}
#SBATCH --account=${ACCOUNT}
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:15:00
#SBATCH --output=${LOG_DIR}/${JOBNAME}-%j.out
#SBATCH --error=${LOG_DIR}/${JOBNAME}-%j.err

source /sdf/group/ssrl/dsokaras/miniconda3/bin/activate
conda activate fairchem

cd /sdf/home/d/dsokaras/hackathon_april2026

python scripts/uma_systematic_benchmark.py \\
    --model ${MODEL} \\
    --surface ${surface} \\
    --adsorbate ${adsorbate} \\
    --outdir ${RESULTS_DIR}
SLURM_EOF

        chmod +x "$JOBSCRIPT"
        JOB_ID=$(sbatch "$JOBSCRIPT" 2>&1)
        echo "${JOBNAME}: ${JOB_ID} (${PARTITION}/${GPU_TYPE})"

        ((count++))
    done
done

echo ""
echo "=== Submission complete ==="
echo "Total jobs: ${count}"
echo "  ada (L40S):     ${ada_count}"
echo "  ampere (A100):  ${ampere_count}"
echo "Results dir: ${RESULTS_DIR}"
echo "Logs dir:    ${LOG_DIR}"
echo ""
echo "Monitor with: squeue -u \$USER | grep uma_"
echo "Check results: ls ${RESULTS_DIR}/*.json | wc -l"
