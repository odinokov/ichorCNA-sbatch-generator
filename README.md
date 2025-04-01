## Overview
This python script generates an SBATCH file for SLURM submission of ichorCNA workflows. It parses a YAML configuration file and produces a corresponding SBATCH file.

## Prerequisites
- Python 3 with the modules: `PyYAML`, `typer`, `jinja2`, `loguru`.
- A SLURM scheduler.
- Sorted BAM files located in the input directory defined in the YAML configuration.

## Usage

1. **Edit Configuration:**  
   Modify `test_001.yaml` to suit your environment and parameters.

2. **Generate SBATCH Script:**  
   Execute the command below to generate the SBATCH script: `python ichorCNA_workflow.py test_001.yaml`

3. **Submit Job:**  
   Manually submit the generated SBATCH script: `sbatch test_001.sbatch`
