#!/usr/bin/env python3
from pathlib import Path
s=(Path(__file__).resolve().parents[1]/'deploy/sync_agent_skills.sh').read_text()
for needle in ('/srv/cloudif/agent-skills','releases','current.new','mv -Tf','SKILL.md','previous'):
 assert needle in s,needle
for banned in ('apt install','apt-get install','docker run','opencode','open-code','systemctl enable','npm install','pip install'):
 assert banned.lower() not in s.lower(),banned
assert "grep -Eq '(^/|(^|/)\\.\\.(/|$))'" in s
print('AGENT_SKILLS_SYNC_OFFLINE=PASS')
