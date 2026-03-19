# CodeBook Studio

CodeBook Studio is a codebook-driven text annotation app for computational social science. It helps researchers define annotation tasks once and then use the same codebook for human annotation, prompt preview, export, and downstream LLM experiments in [CodeBook Lab](https://github.com/LorcanMcLaren/codebook-lab).

The app is designed for researchers working on text classification and related annotation tasks with varied technical backgrounds. Instead of rebuilding annotation instructions and output formats for each project, you can create a structured codebook, apply it to CSV data, and export it in formats that are useful both for annotation workflows and for research reporting.

## What It Does

CodeBook Studio lets you:

- create annotation tasks with a structured JSON codebook
- annotate CSV data through a browser interface
- work with binary, categorical, Likert-scale, and open-ended text responses
- add section-level instructions, tooltips, and worked examples
- preview the prompts that would be sent to an LLM
- export the codebook as JSON, Markdown, or LaTeX
- download annotated CSV files for further analysis

## How It Fits With CodeBook Lab

CodeBook Studio is the task-definition interface. CodeBook Lab is the experiment runner.

In practice, the workflow is:

1. Create a codebook in CodeBook Studio.
2. Use it for human annotation or codebook design.
3. Export the JSON codebook.
4. Use that same codebook in CodeBook Lab to run and evaluate LLM annotation experiments.

This shared codebook structure makes it easier to compare human and model annotations against the same task definition.

Useful links:

- Hosted app: [codebook.streamlit.app](https://codebook.streamlit.app/)
- CodeBook Lab repository: [github.com/LorcanMcLaren/codebook-lab](https://github.com/LorcanMcLaren/codebook-lab)

## Running Locally

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

## Hosted App

The hosted version is available at [codebook.streamlit.app](https://codebook.streamlit.app/).

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
- The sample files in `data/` are for development and testing.

## Related Repository

- [CodeBook Lab](https://github.com/LorcanMcLaren/codebook-lab): LLM annotation pipeline for running experiments from exported codebooks
