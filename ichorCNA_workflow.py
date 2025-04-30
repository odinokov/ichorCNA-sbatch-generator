#!/usr/bin/env python3
"""
Usage:
  $0 CONFIG_FILE

This script generates an SBATCH script for an ichorCNA workflow using a simple YAML configuration.

Use -h or --help for additional details.
"""

import sys
import yaml
import typer
from pathlib import Path
from jinja2 import Template
from loguru import logger

app = typer.Typer(
    help="Generate an SBATCH script for an ichorCNA workflow using a simple YAML configuration.\n\nUsage:\n  $0 CONFIG_FILE"
)

# SBATCH template with essential parameters
SBATCH_TEMPLATE = Template(
r"""#!/bin/bash
#SBATCH --job-name={{ sbatch.job_name }}
#SBATCH --partition={{ sbatch.partition }}
{% if sbatch.account %}#SBATCH --account={{ sbatch.account }}{% endif %}
#SBATCH --array=0-{{ total_files - 1 }}%{{ sbatch.max_concurrent }}
#SBATCH --time={{ sbatch.time }}
#SBATCH --nodes={{ sbatch.nodes }}
#SBATCH --ntasks-per-node={{ sbatch.ntasks_per_node }}
#SBATCH --cpus-per-task={{ sbatch.cpus_per_task }}
#SBATCH --mem={{ sbatch.mem }}
#SBATCH --output={{ sbatch.output }}
#SBATCH --error={{ sbatch.error }}
#SBATCH --mail-user={{ sbatch.mail_user }}
#SBATCH --mail-type={{ sbatch.mail_type }}

set -eo pipefail
umask 077

export SAMBAMBA_CMD="{{ workflow.sambamba }}"
export READCOUNTER_CMD="{{ workflow.readCounter }}"
export RSCRIPT_CMD="{{ workflow.Rscript }}"
export ICHOR_SCRIPT="{{ workflow.ichorCNA_script }}"
export BIN_SIZE="{{ workflow.bin_size }}"
export READCOUNTER_CHRS="{{ workflow.readcounter_chrs }}"
export READCOUNTER_QUALITY="{{ workflow.readcounter_quality }}"
export MY_IN_DIR="{{ workflow.my_in_dir }}"
export MY_OUT_DIR="{{ workflow.my_out_dir }}"
export BASE_TMP_DIR="{{ workflow.my_tmp_dir }}"
export LIST_FILE="{{ list_file }}"

export GC_FILE="{{ ichorCNA.paths.gc_file }}"
export MAP_FILE="{{ ichorCNA.paths.map_file }}"
export CENT_FILE="{{ ichorCNA.paths.cent_file }}"
export PON_FILE="{{ ichorCNA.paths.PON_file }}"
export PLOIDY="{{ ichorCNA.parameters.ploidy }}"
export NORMAL="{{ ichorCNA.parameters.normal }}"
export MAX_CN="{{ ichorCNA.parameters.maxCN }}"
export INCLUDE_HOMD="{{ 'TRUE' if ichorCNA.parameters.includeHOMD else 'FALSE' }}"
export CHRS="{{ ichorCNA.parameters.chrs }}"
export CHR_TRAIN="{{ ichorCNA.parameters.chrTrain }}"
export CHR_NORMALIZE="{{ ichorCNA.parameters.chrNormalize }}"
export ESTIMATE_NORMAL="{{ 'TRUE' if ichorCNA.parameters.estimateNormal else 'FALSE' }}"
export ESTIMATE_PLOIDY="{{ 'TRUE' if ichorCNA.parameters.estimatePloidy else 'FALSE' }}"
export ESTIMATE_SC_PREVALENCE="{{ 'TRUE' if ichorCNA.parameters.estimateScPrevalence else 'FALSE' }}"
export SC_STATES="{{ ichorCNA.parameters.scStates }}"
export TXN_E="{{ ichorCNA.parameters.txnE }}"
export TXN_STRENGTH="{{ ichorCNA.parameters.txnStrength }}"
export GENOME_STYLE="{{ ichorCNA.parameters.genomeStyle }}"
export GENOME_BUILD="{{ ichorCNA.parameters.genomeBuild }}"
export PLOT_TYPE="{{ ichorCNA.parameters.plotFileType }}"

process_sample() {
    local input_bam="$1"
    local sample_id="$2"
    local tmp_dir="$3"
    trap 'rm -rf "${tmp_dir}"' EXIT ERR

    filtered_bam="${tmp_dir}/${sample_id}.filtered.bam"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processing ${sample_id}"
    "${SAMBAMBA_CMD}" view -t "${SLURM_CPUS_PER_TASK}" -l 3 -h -f bam -F "not (duplicate or failed_quality_control)" -o "${filtered_bam}.tmp" "${input_bam}"
    mv "${filtered_bam}.tmp" "${filtered_bam}"
    "${SAMBAMBA_CMD}" index -t "${SLURM_CPUS_PER_TASK}" "${filtered_bam}"
    "${READCOUNTER_CMD}" --chromosome "${READCOUNTER_CHRS}" --window "${BIN_SIZE}" --quality "${READCOUNTER_QUALITY}" "${filtered_bam}" > "${tmp_dir}/${sample_id}.wig.tmp"
    mv "${tmp_dir}/${sample_id}.wig.tmp" "${tmp_dir}/${sample_id}.wig"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running ichorCNA for ${sample_id}"
    "${RSCRIPT_CMD}" "${ICHOR_SCRIPT}" \
        --id "${sample_id}" \
        --WIG "${tmp_dir}/${sample_id}.wig" \
        --gcWig "$GC_FILE" \
        --mapWig "$MAP_FILE" \
        --centromere "$CENT_FILE" \
        --normalPanel "$PON_FILE" \
        --includeHOMD "$INCLUDE_HOMD" \
        --chrs "$CHRS" --chrTrain "$CHR_TRAIN" \
        --chrNormalize "$CHR_NORMALIZE" \
        --estimateNormal "$ESTIMATE_NORMAL" \
        --estimatePloidy "$ESTIMATE_PLOIDY" \
        --estimateScPrevalence "$ESTIMATE_SC_PREVALENCE" \
        --scStates "$SC_STATES" \
        --txnE "$TXN_E" \
        --txnStrength "$TXN_STRENGTH" \
        --outDir "$MY_OUT_DIR/${SAMPLE_ID}" \
        --genomeBuild "$GENOME_BUILD" \
        --genomeStyle "$GENOME_STYLE" \
        --plotFileType "$PLOT_TYPE"
}

declare -a BAM_FILES
mapfile -t BAM_FILES < "{{ list_file }}"
main() {
    SAMPLE_ID=$(basename "${BAM_FILES[$SLURM_ARRAY_TASK_ID]}" .bam)
    mkdir -p "${BASE_TMP_DIR} "${MY_OUT_DIR}/${SAMPLE_ID}" || exit 1
    TMP_DIR=$(mktemp -d -p "${BASE_TMP_DIR}/${SAMPLE_ID}-${SLURM_JOB_ID}") || exit 1
    process_sample \
        "${BAM_FILES[$SLURM_ARRAY_TASK_ID]}" \
        "${SAMPLE_ID}" \
        "${TMP_DIR}"
      
    rm -rf "${TMP_DIR}"
}

main "$@"
"""
)

@app.command()
def generate(
    config_file: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, help="Path to YAML configuration file."
    )
):
    """
    Generate an SBATCH script for an ichorCNA workflow using a simple configuration.

    The YAML file should contain keys: 'sbatch', 'workflow', and 'ichorCNA'.
    """
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    try:
        # Load configuration as a simple dictionary
        config = yaml.safe_load(config_file.read_text())
        sbatch = config["sbatch"]
        workflow = config["workflow"]
        ichorCNA = config["ichorCNA"]
        
        # Remove trailing slash from directory paths if present
        workflow["my_in_dir"] = workflow["my_in_dir"].rstrip("/")
        workflow["my_out_dir"] = workflow["my_out_dir"].rstrip("/")
        workflow["my_tmp_dir"] = workflow["my_tmp_dir"].rstrip("/")


        # Create output directory for results
        Path(workflow["my_out_dir"]).mkdir(parents=True, exist_ok=True)
        
        # Create log folders based on YAML log paths (e.g., "./log")
        for log_path in (sbatch["output"], sbatch["error"]):
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)

        # Enumerate BAM files from my_in_dir
        bam_files = sorted(Path(workflow["my_in_dir"]).glob("*.bam"))
        if not bam_files:
            raise FileNotFoundError(f"No BAM files found in {workflow['my_in_dir']}.")
        if len(bam_files) > sbatch["max_queue"]:
            raise ValueError(f"Number of BAM files ({len(bam_files)}) exceeds max_queue of {sbatch['max_queue']}.")

        # Write BAM file list
        yaml_stem = config_file.stem
        list_file = Path(workflow["my_out_dir"]) / f"{yaml_stem}.lst"
        list_file.write_text("\n".join(str(bam) for bam in bam_files))
        logger.info(f"Wrote {len(bam_files)} entries to {list_file}.")

        rendered_script = SBATCH_TEMPLATE.render(
            sbatch=sbatch,
            workflow=workflow,
            ichorCNA=ichorCNA,
            total_files=len(bam_files),
            output_dir=workflow["my_out_dir"],
            list_file=str(list_file)
        )

        sbatch_path = config_file.with_suffix(".sbatch")
        sbatch_path.write_text(rendered_script)
        logger.success(f"Generated SBATCH script: {sbatch_path}")

    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(2)

if __name__ == "__main__":
    app()
  
