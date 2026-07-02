# GitHub Cleanup Checklist

Before merging Release Candidate v1.0, the following temporary and benchmarking files must be deleted from the repository. **Do not commit these files to the production branch.**

## Benchmarking & Diagnostics
- [ ] `benchmark.py` - Obsolete PyTorch vs ONNX timing script.
- [ ] `compare_engines.py` - Embedding engine comparison script.
- [ ] `investigate_memory.py` - Memory leak root-cause script.
- [ ] `stress_test.py` - 100-request parallel load tester.
- [ ] `test_load.py` - Initial basic load script.

## Server Logs
- [ ] `server_logs.txt` - Output of `psutil` profiling.
- [ ] `server_logs_2.txt` - Output of `psutil` profiling.

## Debug Data
- [ ] `actual_ui_parse.json` - Temporary parse data dump.
- [ ] `scratch/` directory - Temporary scratchpad outputs.

## Database (Ensure ignored by `.gitignore`)
- [ ] `resumeai.db-shm`
- [ ] `resumeai.db-wal`

## Commands to Run
```bash
git rm benchmark.py compare_engines.py investigate_memory.py stress_test.py test_load.py actual_ui_parse.json server_logs.txt server_logs_2.txt
git commit -m "chore: remove temporary benchmarking and debug scripts for v1.0"
```
