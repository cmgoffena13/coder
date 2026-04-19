# Coder
```
_________            .___            
\_   ___ \  ____   __| _/___________ 
/    \  \/ /  _ \ / __ |/ __ \_  __ \
\     \___(  <_> ) /_/ \  ___/|  | \/
 \______  /\____/\____ |\___  >__|   
        \/            \/    \/     
```
![Lines of Code](https://aschey.tech/tokei/github/cmgoffena13/coder?category=code)
[![Build Status](https://github.com/cmgoffena13/coder/actions/workflows/build-release.yml/badge.svg)](https://github.com/cmgoffena13/coder/actions)

Local Coding Assistant powered by [Ollama](https://ollama.com) & [Thoughtflow](https://github.com/jrolf/thoughtflow/tree/main)

---

## Setup
- Download the latest zip in releases
  - Extract the zip
  - Add the `coder` binary in the folder to your PATH
- Have [Ollama](https://ollama.ai) installed and running
- Place a `.env` file in the config directory (Utilize `coder --info` to locate)

## .env Variables
- `CODER_OLLAMA_MODEL` (Required) Ex. `gemma4:e2b`
- `CODER_OLLAMA_HOST` (Optional) Default: `http://localhost:11434`

## Capabilities
- Search, List, & Read Files
- Write & Patch Files
- Run Shell Commands
- Maintains Memory & Context

## CLI Commands
| Flag | Description |
|------|-------------|
| `--info` | Print the CLI binary path and config directory (where `.env` lives). |
| `--version` | Print the version string. |
| `--cwd PATH` | Workspace root (Default: current directory). Must be inside a git repo for best results. |
| `--approval always` / `balanced` / `never` | Tool approval flag (Default: balanced - ask for file modifications) |
| `-v`, `--verbose` | Log tool inputs and outputs to the terminal. |
| `-l`, `--latest` | Open the most recently saved chat session instead of a new one. |

## App Commands
| Command | Description |
|---------|-------------|
| `/help` | List slash commands. |
| `/sessions` | List saved chat sessions (up to 50). |
| `/load <prefix>` | Resume a session whose name starts with `prefix`. |
| `/delete <name>` | Delete a saved session (exact stem match). |
| `/system` | Print the full system prompt. |
| `/refresh` | Re-index the whole workspace (full parse refresh). |
| `/reset` | Delete all saved sessions and all parse indexes, then start a new session. |
| `/exit` | Quit. |

## Disclaimer
> This project includes code from [Mini-Coding-Agent](https://github.com/rasbt/mini-coding-agent) licensed under Apache 2.0.  
> This project includes code from [CodeDrift](https://github.com/darshil3011/codedrift) licensed under MIT
