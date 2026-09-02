# Seed JSON para Railway

Snapshots de resultados de pruebas usados al arrancar la vitrina cuando `/app/out` está vacío.

Actualizar desde local:

```powershell
Copy-Item out\query-smoke.json,out\golden-set-eval.json,out\rag-validation.json,out\load-test-report.json,out\analysis-status.json,out\ingestion-results.json deploy\railway-seed\ -Force
```

No incluir secretos ni corpus cliente.
