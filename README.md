# CodeBook Studio

[![DOI](https://zenodo.org/badge/758504276.svg)](https://doi.org/10.5281/zenodo.19185938) [![License](https://img.shields.io/github/license/LorcanMcLaren/codebook-studio)](https://github.com/LorcanMcLaren/codebook-studio/blob/main/LICENSE)

[![CodeBook Studio demo](assets/codebook-studio-demo.gif)](https://codebook.streamlit.app/)

CodeBook Studio is a browser-based annotation app for computational social science. It lets researchers define a codebook once, annotate CSV data with human coders, adjudicate disagreements, and export the files needed for research reporting and LLM benchmarking.

Studio is the companion app to [CodeBook Lab](https://github.com/LorcanMcLaren/codebook-lab). Studio defines the task and collects human labels; Lab runs LLM annotation experiments and evaluates model outputs against those labels.

## Start Here

- Use the hosted app: [codebook.streamlit.app](https://codebook.streamlit.app/)
- Read the Studio guide: [lorcanmclaren.com/codebook-lab/studio.html](https://lorcanmclaren.com/codebook-lab/studio.html)
- Read the Lab documentation: [lorcanmclaren.com/codebook-lab/](https://lorcanmclaren.com/codebook-lab/)
- Cite the software: [CodeBook citation information](https://lorcanmclaren.com/codebook-lab/citation.html)

## What Studio Exports

CodeBook Studio works with CSV input files and supports checkbox, dropdown, Likert, textbox, and span-style annotations. It can export:

- `codebook.json` for CodeBook Lab experiments
- labelled annotation CSVs for human coders
- completed adjudication queues for unresolved coder disagreements
- Markdown and LaTeX codebook documentation

## How Studio And Lab Fit Together

1. Build the annotation task in Studio.
2. Annotate texts with human coders.
3. Export `codebook.json` and `ground-truth.csv`.
4. Run validation and LLM benchmarking in [CodeBook Lab](https://lorcanmclaren.com/codebook-lab/).

For full workflow details, use the [CodeBook Studio guide](https://lorcanmclaren.com/codebook-lab/studio.html).

## Running Locally

The hosted app is easiest for most users. Run locally when you want to modify the app or keep data on your own machine:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run text_annotation_app.py
```

## Repository Layout

- `text_annotation_app.py`: main Streamlit app
- `components/`: custom app components
- `utils/`: export, parsing, and prompt-preview helpers
- `data/` and `demo_tasks/`: sample files for trying the app locally
- `requirements.txt`: Python dependencies

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

## Citation

If you use CodeBook Studio in research, please cite the software repository. Citation metadata is available in [`CITATION.cff`](CITATION.cff) and on the [CodeBook citation page](https://lorcanmclaren.com/codebook-lab/citation.html).

McLaren, Lorcan. 2026. *CodeBook Studio* (Version v1.2.1) [Computer software]. Zenodo. <https://doi.org/10.5281/zenodo.19185938>.
