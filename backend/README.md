# Backend Layout

This directory contains the main backend entry and configuration:

- `backend/api.py`: main FastAPI app implementation.
- `backend/config.py`: backend configuration and env parsing.

Compatibility shims are kept at project root:

- `api.py` -> imports `backend.api`
- `config.py` -> imports `backend.config`

So existing commands still work:

```bash
python api.py
bash scripts/start_web.sh
```

