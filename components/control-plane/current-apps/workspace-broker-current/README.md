# Workspace Broker Current

Componentes implantados no plano de controle e no host de hospedagem.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/control-plane/current-apps/workspace-broker-current`

Componentes implantados no plano de controle e no host de hospedagem.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-workspace-broker.py`](cloudif-workspace-broker.py) | `.py` | Implementa `docker`, `base_container_args`, `probe`, `fetch_archive`, `safe_extract`, `detect_technologies` e outros componentes. |
| [`cloudif_change_set.py`](cloudif_change_set.py) | `.py` | Implementa `ChangeSetError`, `sha256`, `canonical`, `change_set_digest`, `normalize_path`, `decode_content` e outros componentes. |
| [`cloudif_multitech_detector.py`](cloudif_multitech_detector.py) | `.py` | Implementa `path_allowed`, `safe_json_file`, `safe_yaml_file`, `service_name`, `node_version`, `node_component` e outros componentes. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
