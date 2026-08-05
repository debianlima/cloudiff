#!/usr/bin/env python3
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DB = '/var/lib/cloudif/portal/cloudif-portal.db'


def envfile(path):
    data = {}
    p = Path(path)
    if p.exists():
        for line in p.read_text(errors='ignore').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                data[key.strip()] = value.strip().strip('"\'')
    return data


def request(url, method='GET', payload=None, headers=None, timeout=420):
    request_headers = {'Accept': 'application/json'}
    request_headers.update(headers or {})
    body = None
    if payload is not None:
        body = json.dumps(payload).encode()
        request_headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw or b'{}')
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            data = json.loads(raw or b'{}')
        except Exception:
            data = {'raw': raw.decode(errors='ignore')[:1000]}
        return exc.code, data


def public_number(slug):
    con = sqlite3.connect(DB)
    row = con.execute(
        'select public_number from project_public_ids where project_slug=?',
        (slug,),
    ).fetchone()
    con.close()
    if not row:
        raise RuntimeError('public_number_missing')
    return int(row[0])


def project_access(slug):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    project = con.execute('select * from projects where slug=?', (slug,)).fetchone()
    if not project:
        con.close()
        raise RuntimeError('project_missing')
    owner = str(project['owner'] or project['created_by'] or '') if 'created_by' in project.keys() else str(project['owner'] or '')
    acl = [
        {'type': str(row['subject_type']), 'subject': str(row['subject'])}
        for row in con.execute(
            'select subject_type,subject from project_acl where slug=? order by id',
            (slug,),
        )
    ]
    con.close()
    return {'owner': owner.strip().lower(), 'acl': acl}


def seed_db(tenant):
    import subprocess
    name = f'cloudif_{tenant}-db-1'
    sql = '''CREATE TABLE IF NOT EXISTS public.cloudif_tutorial_steps (
      id integer PRIMARY KEY,title text NOT NULL,completed boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now());
      ALTER TABLE public.cloudif_tutorial_steps ENABLE ROW LEVEL SECURITY;
      DROP POLICY IF EXISTS cloudif_tutorial_read ON public.cloudif_tutorial_steps;
      CREATE POLICY cloudif_tutorial_read ON public.cloudif_tutorial_steps FOR SELECT TO anon, authenticated USING (true);
      GRANT USAGE ON SCHEMA public TO anon, authenticated;
      GRANT SELECT ON public.cloudif_tutorial_steps TO anon, authenticated;
      INSERT INTO public.cloudif_tutorial_steps(id,title,completed) VALUES
      (1,'Entrar no Portal CloudIF',true),(2,'Editar um arquivo no Forgejo',false),
      (3,'Acompanhar o deploy no Komodo',false),(4,'Consultar o banco no Supabase',false),
      (5,'Entender os webhooks',false)
      ON CONFLICT(id) DO UPDATE SET title=excluded.title;
      NOTIFY pgrst, 'reload schema';'''
    proc = subprocess.run(
        ['docker', 'exec', '-i', name, 'psql', '-U', 'postgres', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1'],
        input=sql,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    if proc.returncode:
        raise RuntimeError('seed_db_failed:' + proc.stderr[-300:])


def wait_public(url, timeout=600):
    deadline = time.monotonic() + timeout
    last = 'unknown'
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'CloudIFF-Initial-Publication/2.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    return
                last = str(response.status)
        except urllib.error.HTTPError as exc:
            last = str(exc.code)
            if exc.code not in (404, 425, 429, 500, 502, 503, 504):
                raise RuntimeError('public_health_status_' + last)
        except Exception as exc:
            last = type(exc).__name__
        time.sleep(5)
    raise RuntimeError('public_health_timeout_' + last)


def update_db(slug, tenant, owner, number, deployment, publisher, promotion):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    commit = str(deployment.get('commit') or '')
    detail = json.dumps({
        'komodo': deployment,
        'npm': publisher,
        'promotion': promotion,
        'runtime_contract': 'managed-root-v1',
        'infrastructure_in_git': False,
    }, ensure_ascii=False)
    con.execute('update project_publications set is_active=0 where project_slug=?', (slug,))
    con.execute('''
      insert into project_publications(
        project_slug,public_number,deploy_number,version,commit_sha,stable_hostname,
        version_hostname,status,is_active,created_by,created_at,published_at,message,detail_json
      ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      on conflict(project_slug,deploy_number) do update set
        commit_sha=excluded.commit_sha,status='published',is_active=1,
        published_at=excluded.published_at,message=excluded.message,detail_json=excluded.detail_json
    ''', (
        slug, number, 1, 'd1', commit,
        f'{number}.cloudiff.duckdns.org', f'{number}-d1.cloudiff.duckdns.org',
        'published', 1, owner, now, now,
        'Publicação inicial em container versionado próprio', detail,
    ))
    integration_cols = {row[1] for row in con.execute('pragma table_info(project_integrations)')}
    updates = []
    params = []
    for column, value in (
        ('status', 'ready'),
        ('message', 'Publicação d1 criada em runtime versionado sem alterar a stack-base de checkout.'),
        ('updated_at', now),
    ):
        if column in integration_cols and value:
            updates.append(column + '=?')
            params.append(value)
    if updates:
        con.execute(
            'update project_integrations set ' + ','.join(updates) + ' where project=?',
            params + [slug],
        )
    project_cols = {row[1] for row in con.execute('pragma table_info(projects)')}
    project_updates = []
    project_params = []
    for column, value in (
        ('status', 'published'),
        ('komodo_status', 'running'),
        ('updated_at', now),
    ):
        if column in project_cols:
            project_updates.append(column + '=?')
            project_params.append(value)
    if project_updates:
        con.execute(
            'update projects set ' + ','.join(project_updates) + ' where slug=?',
            project_params + [slug],
        )
    con.commit()
    con.close()


def main():
    job_path = Path(sys.argv[1])
    job = json.loads(job_path.read_text())
    slug = str(job['slug'])
    tenant = str(job.get('tenant') or '')
    owner = str((job.get('user') or {}).get('username') or '')
    kind = str(job.get('template_kind') or 'none')
    number = public_number(slug)

    komodo = envfile('/etc/cloudif/komodo-agent-client.env')
    komodo_base = (komodo.get('KOMODO_AGENT_URL') or 'http://10.62.91.2:18098').rstrip('/')
    komodo_token = komodo.get('KOMODO_AGENT_TOKEN', '')
    komodo_headers = {
        'X-CloudIF-Token': komodo_token,
        'Authorization': 'Bearer ' + komodo_token,
    }
    deploy_payload = {
        'project': slug,
        'public_number': number,
        'deploy_number': 1,
        'timeout': 600,
    }
    status, deployment = request(
        komodo_base + '/komodo/publication/deploy',
        'POST',
        deploy_payload,
        komodo_headers,
        timeout=900,
    )
    if status // 100 != 2 or not deployment.get('ok'):
        raise RuntimeError('versioned_d1_deploy_failed:' + json.dumps(deployment, ensure_ascii=False)[:900])

    publisher_cfg = envfile('/etc/cloudif/npm-publisher-client.env')
    publisher_token = publisher_cfg.get('NPM_PUBLISHER_TOKEN', '')
    status, publisher = request(
        'http://10.62.91.3/publish',
        'POST',
        {'public_number': number, 'deploy_number': 1},
        {'Host': 'cloudif-publisher.internal', 'X-CloudIF-Token': publisher_token},
        timeout=300,
    )
    if status // 100 != 2 or not publisher.get('ok'):
        raise RuntimeError('npm_publish_failed:' + json.dumps(publisher, ensure_ascii=False)[:500])

    status, promotion = request(
        komodo_base + '/komodo/publication/promote',
        'POST',
        {'project': slug, 'public_number': number, 'deploy_number': 1},
        komodo_headers,
        timeout=180,
    )
    if status // 100 != 2 or not promotion.get('ok'):
        raise RuntimeError('d1_promotion_failed:' + json.dumps(promotion, ensure_ascii=False)[:500])

    wait_public(publisher['version_url'])
    wait_public(publisher['stable_url'])
    if kind == 'onboarding' and tenant:
        seed_db(tenant)

    update_db(slug, tenant, owner, number, deployment, publisher, promotion)
    access = project_access(slug)
    _, membership = request(
        komodo_base + '/komodo/project/membership/reconcile',
        'POST',
        {'project': slug, 'access': access},
        komodo_headers,
        timeout=180,
    )
    try:
        sys.path.insert(0, '/srv/cloudif/lib')
        from cloudif_reconcile_client import enqueue
        enqueue(
            'project.membership.changed',
            actor=owner or 'project-initial-publish',
            username=owner,
            project=slug,
            tenant=tenant,
            payload={'source': 'initial_publication', 'operation': 'reconcile'},
            dedupe_seconds=0,
        )
    except Exception:
        pass

    result = {
        'ok': True,
        'project': slug,
        'template_kind': kind,
        'public_number': number,
        'deploy_number': 1,
        'container': deployment.get('container'),
        'stack_id': deployment.get('stack_id'),
        'commit': deployment.get('commit'),
        'stable_url': publisher['stable_url'],
        'version_url': publisher['version_url'],
        'membership': membership,
        'infrastructure_in_git': False,
    }
    output = Path(f'/srv/cloudif/provisioning/projects/{slug}/initial-publication.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
