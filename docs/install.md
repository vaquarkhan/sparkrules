# Installation

## From PyPI

```bash
pip install sparkrules          # core engine only
pip install sparkrules[api]     # + FastAPI server and Workbench UI
pip install sparkrules[spark]   # + PySpark cluster integration
pip install sparkrules[all]     # everything
```

## From source

```bash
git clone https://github.com/vaquarkhan/sparkrules.git
cd sparkrules
pip install -e ".[test]"
```

## Docker

```bash
docker compose up --build
# → http://127.0.0.1:8042/workbench/
```

## Requirements

- Python 3.11+
- For `sparkrules[api]`: FastAPI, uvicorn, httpx, structlog, prometheus-client
- For `sparkrules[spark]`: PySpark 3.5+ and a Java runtime

## Verify installation

```python
import sparkrules
print(sparkrules.__version__)  # 1.0.1
```
