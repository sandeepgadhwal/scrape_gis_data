# rajasthan citizen udh

## URL
https://rajdharaa.rajasthan.gov.in/citizenudh

## Prerequisite
Install uv using this [link](https://docs.astral.sh/uv/getting-started/installation/).

## Dependencies
This project keeps both `pyproject.toml` and `requirements.txt`:

- `pyproject.toml` is the source of package metadata and project dependencies for `uv`.
- `requirements.txt` is for pip-style installs and uses a relative editable path.

Install from `requirements.txt` with:
```bash
pip install -r requirements.txt
```

## Scrape data
Scrape data using this command
```bash
uv run main.py
```