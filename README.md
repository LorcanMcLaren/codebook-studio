# CodeBook Studio

CodeBook Studio is a codebook-driven text annotation app for computational social science. It helps researchers define annotation tasks once and then use the same codebook for human annotation, prompt preview, export, and downstream LLM experiments in [CodeBook Lab](https://github.com/LorcanMcLaren/codebook-lab).

The app is designed for researchers working on text classification and related annotation tasks with varied technical backgrounds. Instead of rebuilding annotation instructions and output formats for each study, you can create a structured codebook, apply it to CSV data, and export it in formats that support both annotation and research reporting.

## What It Does

CodeBook Studio lets you:

- create annotation tasks with a structured JSON codebook
- annotate CSV data through a browser interface
- work with binary, categorical, Likert-scale, and open-ended text responses
- add section-level instructions, tooltips, and worked examples
- preview the prompts that would be sent to an LLM
- export the codebook as JSON, Markdown, or LaTeX
- download annotated CSV files for further analysis or evaluation in CodeBook Lab

## How It Fits With CodeBook Lab

CodeBook Studio is the task-definition interface. CodeBook Lab is the experiment runner.

In practice, the workflow is:

1. Create a codebook in CodeBook Studio.
2. Use it to annotate texts or refine the task definition.
3. Export the JSON codebook.
4. Save the human-annotated CSV as `ground-truth.csv`.
5. Use that same codebook and `ground-truth.csv` in CodeBook Lab.
6. Let CodeBook Lab strip the annotation label columns automatically before sending the text to the LLM.
7. Evaluate the model outputs against the original human labels.

<table>
  <tr>
    <td align="center"><strong>CodeBook Studio</strong></td>
    <td align="center"></td>
    <td align="center"><strong>CodeBook Lab</strong></td>
  </tr>
  <tr>
    <td valign="top">
      Define the annotation task<br>
      Annotate texts with humans<br>
      Export <code>codebook.json</code><br>
      Save labeled data as <code>ground-truth.csv</code>
    </td>
    <td align="center" valign="middle">→</td>
    <td valign="top">
      Read rows from <code>ground-truth.csv</code><br>
      Strip label columns automatically<br>
      Run LLM annotation experiments<br>
      Compare models, prompts, and settings<br>
      Evaluate outputs against human labels
    </td>
  </tr>
</table>

<p><em>CodeBook Studio defines the task; CodeBook Lab runs and evaluates the experiment.</em></p>

This shared codebook structure makes it easier to compare human and model annotations against the same annotation scheme.

Useful links:

- Hosted app: [codebook.streamlit.app](https://codebook.streamlit.app/)
- CodeBook Lab repository: [github.com/LorcanMcLaren/codebook-lab](https://github.com/LorcanMcLaren/codebook-lab)

## Hosted App

For most users, the hosted app at [codebook.streamlit.app](https://codebook.streamlit.app/) is the simplest and recommended way to use CodeBook Studio.

It lets you create codebooks, annotate texts, preview prompts, and export the files needed for downstream LLM evaluation without any local setup.

If you want to run LLM annotation experiments from an exported codebook, use [CodeBook Lab](https://github.com/LorcanMcLaren/codebook-lab).

## Running Locally

Running locally is mainly useful for power users who want greater customization, or for cases where data sensitivity means you prefer to keep everything on your own machine.

### 1. Create an environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Start the app

```bash
streamlit run text_annotation_app.py
```

By default, the app will open in your browser at a local Streamlit URL.

## Core Concepts

### Codebook

The codebook is the central object in the app. It defines:

- the header column shown during annotation
- the text column to annotate
- one or more annotation sections
- the questions within each section
- the response type for each question
- instructions, tooltips, and optional examples

The app can export this structure as JSON for reuse in [CodeBook Lab](https://github.com/LorcanMcLaren/codebook-lab), and as Markdown or LaTeX for documentation and appendices.

### Annotation Types

CodeBook Studio supports:

- `checkbox` for binary labels
- `dropdown` for categorical labels
- `likert` for ordinal scales
- `textbox` for open-ended text responses

### Prompt Preview

The prompt preview page shows how each annotation question would be formatted for LLM-based annotation. This helps researchers inspect instructions, examples, and response formatting before moving to [CodeBook Lab](https://github.com/LorcanMcLaren/codebook-lab).

## Repository Layout

- `text_annotation_app.py`: main Streamlit app
- `utils/prompt_preview.py`: LLM prompt generation and preview logic
- `utils/export.py`: Markdown and LaTeX codebook export
- `utils/html_parser.py`: helper logic for parsing and formatting examples
- `requirements.txt`: Python dependencies

## Notes

- The app works with CSV input files.
- The downloaded JSON codebook may need to be saved as `codebook.json` when used inside a CodeBook Lab task folder.
- A human-annotated CSV exported from Studio can be used as `ground-truth.csv` in CodeBook Lab.
- CodeBook Lab can derive the unlabeled LLM input directly from `ground-truth.csv` by removing the annotation columns defined in the codebook.
- The sample files in `data/` are included as small example materials for testing and demonstration.

## Related Repository

- [CodeBook Lab](https://github.com/LorcanMcLaren/codebook-lab): LLM annotation pipeline for running experiments from exported codebooks

## Citation

If you use this repository in research, please cite the software repository.

The repository includes a [`CITATION.cff`](/Users/lorcanmclaren/Python/codebook-studio/CITATION.cff) file for the software citation used by GitHub's citation interface.

### Software Citation

APSR style:

McLaren, Lorcan. 2026. *CodeBook Studio* (Version 0.1.0) [Computer software]. [https://github.com/LorcanMcLaren/codebook-studio](https://github.com/LorcanMcLaren/codebook-studio).

BibTeX:

```bibtex
@software{mclaren_codebook_studio_2026,
  author = {McLaren, Lorcan},
  title = {CodeBook Studio},
  year = {2026},
  version = {0.1.0},
  url = {https://github.com/LorcanMcLaren/codebook-studio}
}
```
