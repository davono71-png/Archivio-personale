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
docker compose --profile ai up -d anythingllm
```

Interfaccia:

```text
http://localhost:3001
```

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
