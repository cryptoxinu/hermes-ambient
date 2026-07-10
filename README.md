# hermes-ambient

Run [Hermes](https://github.com/NousResearch/hermes) on
[Ambient](https://ambient.xyz) inference — frontier open models, direct, no proxy.

Hermes speaks the OpenAI API and discovers a custom provider's models from its
`/v1/models`, so pointing it at Ambient is one command and the model list stays
live. Your API key is referenced by env var — it never lands in the config file.

## Setup

```bash
export AMBIENT_API_KEY=<your key from app.ambient.xyz>
python3 setup.py
```

Then run `hermes`, open `/model`, and pick a model under **Ambient**. Hermes
lists every model Ambient advertises, fetched live.

`setup.py` is safe: it backs up your config, is idempotent, writes atomically,
and prints the block to paste by hand rather than risk editing a config it can't
cleanly modify. Use `python3 setup.py --print` to see the block and change nothing.

## What it adds

To `~/.hermes/config.yaml`:

```yaml
custom_providers:
  - name: Ambient
    base_url: https://api.ambient.xyz/v1
    key_env: AMBIENT_API_KEY
    model: moonshotai/kimi-k2.7-code
```

## Reliability

This is the **direct, native** path: Hermes talks straight to Ambient. Hermes has
no request middleware, so there is no in-process reliability layer here. If you
want the max-tokens floor and context-overflow handling (a reasoning model on a
tight budget can otherwise return empty), route Hermes through the local bridge
instead — see [`ambient-agents`](https://github.com/cryptoxinu/ambient-agents).

## Get an API key

Sign up at [app.ambient.xyz](https://app.ambient.xyz), create an API key, and
export it as `AMBIENT_API_KEY`.

## Development

`setup.py` is standard-library only. Its config-editing safety is covered by a
test suite (never duplicates a key, idempotent, refuses an existing block,
preserves line endings):

```bash
python3 test_setup.py
```

## License

MIT
