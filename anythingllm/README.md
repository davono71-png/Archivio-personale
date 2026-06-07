# AnythingLLM

Questa cartella contiene la configurazione locale per AnythingLLM.

Lo storage persistente viene montato in:

```text
anythingllm/storage/
```

La cartella e ignorata da Git perche contiene database, indici e dati locali.

## Avvio

AnythingLLM e nel profilo Docker `ai`, quindi non parte con il solo `docker compose up -d`.

Avvio:

```bash
docker compose --profile ai up -d ollama anythingllm
```

Interfaccia:

```text
http://localhost:3001
```

## Modello locale con Ollama

Ollama e incluso nello stesso profilo Docker `ai`.

Scarica un modello leggero:

```bash
docker compose --profile ai exec ollama ollama pull llama3.2:3b
```

Modelli alternativi:

```bash
docker compose --profile ai exec ollama ollama pull qwen2.5:7b
docker compose --profile ai exec ollama ollama pull llama3.1:8b
```

In AnythingLLM configura:

```text
LLM Provider: Ollama
Base URL: http://ollama:11434
Model: llama3.2:3b
```

`llama3.2:3b` e indicato per test rapidi su laptop. Per qualita migliore prova
`qwen2.5:7b` o `llama3.1:8b`, tenendo conto che usano piu RAM/CPU.

## Import documenti

Prima crea il pacchetto:

```bash
gmail-drive-archiver prepare-anythingllm \
  --inventory database/inventory-da-classificare.csv \
  --text-dir database/extracted-text \
  --categories config/categories.yml \
  --output-dir database/anythingllm-import
```

Nel container la cartella e montata in sola lettura qui:

```text
/workspace/anythingllm-import
```

Importa i file `.txt` in un workspace AnythingLLM. Il file `manifest.jsonl` contiene metadati
utili per collegare risposta AI, ID Drive e categoria provvisoria.
