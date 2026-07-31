#!/usr/bin/env python3
import importlib.util
p='/srv/cloudif/app-pointers/project-onboarding-current/cloudif-project-onboarding.py';s=importlib.util.spec_from_file_location('o',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.init();r=m.reconcile_all();print(__import__('json').dumps(r,separators=(',',':')));raise SystemExit(0 if r['ok'] else 1)
