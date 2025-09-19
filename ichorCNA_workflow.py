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

# SBATCH template with hardcoded (inlined) config â€” no export statements
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

process_sample() {
    local input_bam="$1"
    local sample_id="$2"
    local tmp_dir="$3"

    filtered_bam="${tmp_dir}/${sample_id}.filtered.bam"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processing ${sample_id}"

    "{{ workflow.sambamba }}" view \
        -t "${SLURM_CPUS_PER_TASK}" -l 3 -h -f bam \
        -F "not (duplicate or failed_quality_control) and proper_pair" \
        -o "${filtered_bam}.tmp" \
        "${input_bam}"
    mv "${filtered_bam}.tmp" "${filtered_bam}"

    "{{ workflow.sambamba }}" index -t "${SLURM_CPUS_PER_TASK}" "${filtered_bam}"

    "{{ workflow.readCounter }}" \
        --chromosome "{{ workflow.readcounter_chrs }}" \
        --window "{{ workflow.bin_size }}" \
        --quality "{{ workflow.readcounter_quality }}" \
        "${filtered_bam}" > "${tmp_dir}/${sample_id}.wig.tmp"
    mv "${tmp_dir}/${sample_id}.wig.tmp" "${tmp_dir}/${sample_id}.wig"

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running ichorCNA for ${sample_id}"
    "{{ workflow.Rscript }}" "{{ workflow.ichorCNA_script }}" \
        --id "${sample_id}" \
        --WIG "${tmp_dir}/${sample_id}.wig" \
        --gcWig "{{ ichorCNA.paths.gc_file }}" \
        --mapWig "{{ ichorCNA.paths.map_file }}" \
        --centromere "{{ ichorCNA.paths.cent_file }}" \
        --normalPanel "{{ ichorCNA.paths.PON_file }}" \
        --maxCN "{{ ichorCNA.parameters.maxCN }}" \
        --includeHOMD "{{ 'TRUE' if ichorCNA.parameters.includeHOMD else 'FALSE' }}" \
        --chrs "{{ ichorCNA.parameters.chrs }}" \
        --chrTrain "{{ ichorCNA.parameters.chrTrain }}" \
        --chrNormalize "{{ ichorCNA.parameters.chrNormalize }}" \
        --estimateNormal "{{ 'TRUE' if ichorCNA.parameters.estimateNormal else 'FALSE' }}" \
        --estimatePloidy "{{ 'TRUE' if ichorCNA.parameters.estimatePloidy else 'FALSE' }}" \
        --ploidy "{{ ichorCNA.parameters.ploidy }}" \
        --normal "{{ ichorCNA.parameters.normal }}" \
        --estimateScPrevalence "{{ 'TRUE' if ichorCNA.parameters.estimateScPrevalence else 'FALSE' }}" \
        --scStates "{{ ichorCNA.parameters.scStates }}" \
        --txnE "{{ ichorCNA.parameters.txnE }}" \
        --txnStrength "{{ ichorCNA.parameters.txnStrength }}" \
        --outDir "{{ workflow.my_out_dir }}/${sample_id}" \
        --genomeBuild "{{ ichorCNA.parameters.genomeBuild }}" \
        --genomeStyle "{{ ichorCNA.parameters.genomeStyle }}" \
        --plotFileType "{{ ichorCNA.parameters.plotFileType }}" \
        --plotYLim "{{ ichorCNA.parameters.plotYLim }}" \
        --minMapScore "{{ ichorCNA.parameters.minMapScore }}" \
        --rmCentromereFlankLength "{{ ichorCNA.parameters.rmCentromereFlankLength }}" \
        --maxFracCNASubclone "{{ ichorCNA.parameters.maxFracCNASubclone }}" \
        --maxFracGenomeSubclone "{{ ichorCNA.parameters.maxFracGenomeSubclone }}" \
        --minSegmentBins "{{ ichorCNA.parameters.minSegmentBins }}" \
        --altFracThreshold "{{ ichorCNA.parameters.altFracThreshold }}" \
        --normalizeMaleX "{{ 'TRUE' if ichorCNA.parameters.normalizeMaleX else 'FALSE' }}" \
        --minTumFracToCorrect "{{ ichorCNA.parameters.minTumFracToCorrect }}" \
        --fracReadsInChrYForMale "{{ ichorCNA.parameters.fracReadsInChrYForMale }}" \
        --lambdaScaleHyperParam "{{ ichorCNA.parameters.lambdaScaleHyperParam }}"
}

declare -a BAM_FILES
mapfile -t BAM_FILES < <(grep -v '^#' "{{ list_file }}")

main() {
    SAMPLE_ID=$(basename "${BAM_FILES[$SLURM_ARRAY_TASK_ID]}" .bam)
    SAMPLE_ID="${SAMPLE_ID%%.*}"
    SAMPLE_TMP_BASE="{{ workflow.my_tmp_dir }}/${SAMPLE_ID}-${SLURM_JOB_ID}"
    mkdir -p "${SAMPLE_TMP_BASE}" "{{ workflow.my_out_dir }}/${SAMPLE_ID}" || exit 1
    TMP_DIR=$(mktemp -d -p "${SAMPLE_TMP_BASE}") || exit 1

    trap 'rm -rf "${TMP_DIR}" "${SAMPLE_TMP_BASE}"' EXIT ERR

    process_sample \
        "${BAM_FILES[$SLURM_ARRAY_TASK_ID]}" \
        "${SAMPLE_ID}" \
        "${TMP_DIR}"
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

        # Normalize directory paths
        workflow["my_in_dir"] = workflow["my_in_dir"].rstrip("/")
        workflow["my_out_dir"] = workflow["my_out_dir"].rstrip("/")
        workflow["my_tmp_dir"] = workflow["my_tmp_dir"].rstrip("/")

        # Create output directory for results
        Path(workflow["my_out_dir"]).mkdir(parents=True, exist_ok=True)

        # Ensure log folders exist
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

        # Render script with all values hardcoded inline
        rendered_script = SBATCH_TEMPLATE.render(
            sbatch=sbatch,
            workflow=workflow,
            ichorCNA=ichorCNA,
            total_files=len(bam_files),
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


