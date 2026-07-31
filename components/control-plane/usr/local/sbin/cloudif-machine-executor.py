#!/usr/bin/env python3
import json,sys
# MVP: executor deliberadamente bloqueado. Nenhuma ação privilegiada é aceita.
print(json.dumps({'ok':False,'error':'executor_actions_disabled','message':'Executor instalado em modo bloqueado até confirmação de política e RBAC.'},ensure_ascii=False))
raise SystemExit(77)
