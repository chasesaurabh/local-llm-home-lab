# llama.cpp request fixture — source Chapter 25

`request.json` is the exact synthetic request used for the printed reader client replay. It assumes a separately installed CPU server and model. No installer, binary, weights, process controller or private log is included here.

Recorded identities: llama.cpp `0.8.0-dev`, build11960, commit8642541b2, release `b11960`; model `Qwen/Qwen3-0.6B-GGUF`, revision `23749fefcc72300e3a2ad315e1317431b06b590a`, file `Qwen3-0.6B-Q8_0.gguf`.

| Artifact | Recorded bytes | SHA-256 |
|---|---:|---|
| `llama-b11960-bin-win-cpu-x64.zip` | 24,407,745 | `73f962f82850d244db47eaacb9d913637027b82399124324298576d58c5f4287` |
| Ubuntu x64 runtime archive | 22,686,210 | `31cc3a6bc638ac6c48dc4b1b74888f1eaadf3d14227c1e5f67daf9a49541d97a` |
| Qwen3-0.6B Q8_0 GGUF | 639,446,688 | `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031` |

The runtime and model were independently downloaded, checksummed and executed in Windows and Ubuntu 24.04.4 under WSL2 in the original lab. That does not establish bare-metal Linux, macOS, GPU offload or a platform speed ranking. The model is a different artifact from the Ollama Q4 starter model. Upstream sources used in the retained verification: [runtime release](https://github.com/ggml-org/llama.cpp/releases/tag/b11960), [publisher model revision](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/tree/23749fefcc72300e3a2ad315e1317431b06b590a). Obtain the appropriate artifact and preserve its license separately; model weights are not part of this package.

After following the book's installation route, in the existing Windows GGUF work folder containing `runtime/` and `model.gguf`, start the owned local CPU server in its own terminal:

```powershell
.\runtime\llama-server.exe -m .\model.gguf --alias qwen3-0.6b-q8 `
    --host 127.0.0.1 --port 8116 -c 2048 -np 1 `
    -t 4 -ngl 0 --reasoning off
```

Wait for readiness, then from this companion folder in a second PowerShell terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8116/health
$Reply = Invoke-RestMethod -Uri http://127.0.0.1:8116/v1/chat/completions `
    -Method Post -ContentType 'application/json' `
    -Body ([IO.File]::ReadAllText((Join-Path $PWD 'request.json')))
$Reply.choices[0].message.content
```

Expected supported content is `lab-backups` (punctuation may vary). Stop only the server in its own terminal with Ctrl+C when finished; do not kill unrelated listeners. The reader request succeeded in both PowerShell 5.1 and 7.6.5 and native Ubuntu curl against the separately started WSL server. The broader three-question CPU packet passed only 2/3 on both systems, including an incorrect abstention. A functioning API is not a correctness guarantee. A local listener is not a complete browser-origin or shared-service security assessment. The new README/path layout itself has not been live-replayed during packaging.
