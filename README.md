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
- `CODER_LOG_LEVEL` (Optional) Default: `ERROR`
- `CODER_OLLAMA_HOST` (Optional) Default: `http://localhost:11434`


> This project includes code from [Mini-Coding-Agent](https://github.com/rasbt/mini-coding-agent) licensed under Apache 2.0.
