## Summary

## Checklist (backend)

- [ ] Pytest for changed routes
- [ ] `black` / `isort` / `pytest` pass locally
- [ ] Alembic revision if schema changed
- [ ] Runner/upload security considered

## Verification

```bash
black --check --diff app/
isort --profile black --check-only --diff app/
pytest -v
```
