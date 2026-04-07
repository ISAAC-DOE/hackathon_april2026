#!/bin/bash
# Submit systematic UMA benchmark across ada (L40S) and ampere (A100)
# 7 surfaces × 8 adsorbates × 1 model = 56 jobs (one per GPU)
# Split: even jobs → ada, odd jobs → ampere

SCRIPT_DIR="/sdf/home/d/dsokaras/hackathon_april2026"
BENCHMARK="${SCRIPT_DIR}/scripts/uma_systematic_benchmark.py"
RESULTS_DIR="${SCRIPT_DIR}/results/uma_benchmark"
JOBS_DIR="${SCRIPT_DIR}/jobs/uma_batch"

mkdir -p "$RESULTS_DIR" "$JOBS_DIR"

SURFACES=("Cu111" "Cu100" "Cu211" "Au111" "Ag111" "Cu3Au111" "Cu3Ag111")
ADSORBATES=("CO" "H" "OH" "CHO" "COH" "OCCO" "COOH" "CO2")
MODEL="uma-s-1p2"

count=0
ada_jobs=0
ampere_jobs=0

for surf in "${SURFACES[@]}"; do
    for ads in "${ADSORBATES[@]}"; do
        JOB_NAME="uma_${surf}_${ads}"
        JOB_SCRIPT="${JOBS_DIR}/${JOB_NAME}.sh"

        # Alternate between ada and ampere
        if (( count % 2 == 0 )); then
            PARTITION="ada"
            GPU_TYPE="gpu:l40s:1"
            ACCOUNT="ssrl:isaac"
            QOS="#SBATCH --qos=normal"
            ((ada_jobs++))
        else
            PARTITION="ampere"
            GPU_TYPE="gpu:a100:1"
            ACCOUNT="lcls:default"
            QOS="#SBATCH --qos=preemptable"
            ((ampere_jobs++))
        fi

        cat > "$JOB_SCRIPT" << JOBEOF
#!/bin/bash
#SBATCH --job-name=${JOB_NAME}
#SBATCH --account=${ACCOUNT}
#SBATCH --partition=${PARTITION}
#SBATCH --gres=${GPU_TYPE}
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:15:00
${QOS}
#SBATCH --output=${SCRIPT_DIR}/logs/uma_${surf}_${ads}-%j.out
#SBATCH --error=${SCRIPT_DIR}/logs/uma_${surf}_${ads}-%j.err

source /sdf/group/ssrl/dsokaras/miniconda3/bin/activate
conda activate fairchem

cd ${SCRIPT_DIR}

python ${BENCHMARK} --model ${MODEL} --surface ${surf} --adsorbate ${ads} --outdir ${RESULTS_DIR}
JOBEOF

        chmod +x "$JOB_SCRIPT"
        ((count++))
    done
done

echo "Generated ${count} job scripts (${ada_jobs} ada, ${ampere_jobs} ampere)"
echo "Job scripts in: ${JOBS_DIR}"
echo ""

# Now submit all jobs
echo "Submitting all jobs..."
submitted=0
for script in ${JOBS_DIR}/uma_*.sh; do
    JOB_ID=$(sbatch "$script" 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "  ${JOB_ID} — $(basename $script .sh)"
        ((submitted++))
    else
        echo "  FAILED: $(basename $script) — $JOB_ID"
    fi
done

echo ""
echo "Submitted ${submitted}/${count} jobs"
echo "Monitor: squeue -u $USER | grep uma_"
echo "Results: ${RESULTS_DIR}"
