# PALS reference data

These files are versioned application inputs. They populate species and passive search, breeding rules, and base work suitability before any user save is uploaded. Generated ownership, inventory, plans, and decoded-save files remain under the ignored PALS runtime data directory.

- `pals.json` is a normalized snapshot of the MIT-licensed [helios57/palworld](https://github.com/helios57/palworld) Palworld 1.0 data at commit `4120331a454842e8f91b8d83cc7b21e64b4a7ade`. Display names are mapped to internal asset IDs from the pinned parser source; work labels are normalized to PALS keys. See `LICENSE.helios57-palworld`.
- `skill.json` is copied from the Apache-2.0-licensed [zaigie/palworld-server-tool](https://github.com/zaigie/palworld-server-tool) at commit `3b0e1e96a7500846e3a6fbac66f1c248b4c286e7`. See its license and notice files.

To test an updated snapshot without replacing the bundled defaults, set `PALWORLD_BREEDING_DATA` or `PALWORLD_SKILL_METADATA` to an alternate file. Validate counts, unique keys, combination references, known breeding facts, and the PALS test suite before committing a refresh.
