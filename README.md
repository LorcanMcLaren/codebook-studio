# CodeBook Studio

CodeBook Studio is a codebook-driven text annotation app for computational social science. Define an annotation task once — with sections, instructions, tooltips, and worked examples — then annotate in the browser and export everything you need for research reporting and LLM benchmarking in [CodeBook Lab](https://github.com/LorcanMcLaren/codebook-lab).

The app supports the annotation types researchers most commonly need: binary labels (checkbox), categorical labels (dropdown), ordinal scales (Likert), and open-ended text responses (textbox). It works with any CSV data and does not require fixed column names.

## How It Fits With CodeBook Lab

CodeBook Studio defines the task. [CodeBook Lab](https://github.com/LorcanMcLaren/codebook-lab) runs and evaluates the experiment.

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
      Strip label columns automatically<br>
      Run LLM annotation experiments<br>
      Sweep over models, prompts, and hyperparameters<br>
      Evaluate outputs against human labels
    </td>
  </tr>
</table>

The shared codebook structure means the same annotation scheme drives both human annotation and LLM prompting, so model outputs can be compared directly against the human labels.

For a step-by-step walkthrough covering both tools, see the [CodeBook Studio & Lab Tutorial](https://lorcanmclaren.com/codebook-tutorial.html).

## Hosted App

For most users, the hosted app at [codebook.streamlit.app](https://codebook.streamlit.app/) is the simplest way to use CodeBook Studio. No local setup is required.

## Running Locally

Running locally is useful for greater customization or when data sensitivity means you prefer to keep everything on your own machine.

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

## Repository Layout

- `text_annotation_app.py`: main Streamlit app
- `utils/prompt_preview.py`: LLM prompt generation and preview logic
- `utils/export.py`: Markdown and LaTeX codebook export
- `utils/html_parser.py`: helper logic for parsing and formatting examples
- `requirements.txt`: Python dependencies

## Notes

- The app works with CSV input files.
- The sample files in `data/` can be used to try out the app before loading your own data.

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

## Citation

If you use this repository in research, please cite the software repository.

The repository includes a [`CITATION.cff`](CITATION.cff) file for the software citation used by GitHub's citation interface.

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
