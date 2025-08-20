## Overview
This Python script generates an SBATCH file for SLURM submission of ichorCNA workflows. It parses a YAML configuration file and produces a corresponding SBATCH file.

## Prerequisites
- Python 3 with the modules: `pathlib`, `PyYAML`, `typer`, `jinja2`, `loguru`.
- [sambamba](https://github.com/biod/sambamba)
- [readCounter](https://github.com/shahcompbio/hmmcopy_utils)
- [ichorCNA](https://github.com/broadinstitute/ichorCNA)
- A SLURM scheduler.
- Sorted BAM files located in the input directory defined in the YAML configuration. You may also use symbolic links, i.e.,
  ```bash
  S="./OUT_BAM_HG19/1x";
  mkdir -p ./bam_links;
  find "$S" -maxdepth 4 -type f \( -name '*.bam' -o -name '*.bai' \) -exec ln -s -t ./bam_links {} +;
  ```

## Usage

1. **Edit Configuration:**  
   Modify `test_001.yaml` to suit your environment and parameters.

2. **Generate SBATCH Script:**  
   Generate the SBATCH script: `python ichorCNA_workflow.py test_001.yaml`

3. **Submit Job:**  
   Manually submit the generated SBATCH script: `sbatch test_001.sbatch`
