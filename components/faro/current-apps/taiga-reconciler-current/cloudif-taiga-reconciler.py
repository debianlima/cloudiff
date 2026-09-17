#!/usr/bin/env python3
import hmac,json,os,re,subprocess,sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
HOST=os.environ.get('TAIGA_RECONCILER_HOST','10.62.91.5')
PORT=int(os.environ.get('TAIGA_RECONCILER_PORT','19010'))
TOKEN=os.environ.get('TAIGA_RECONCILER_TOKEN','')
CONTAINER=os.environ.get('TAIGA_BACK_CONTAINER','taiga-current-taiga-back-1')
SLUG=re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
DJANGO=r'''
import json,sys
from django.db import transaction
from taiga.projects.models import Project,ProjectTemplate,Membership
from taiga.users.models import User,Role
payload=json.load(sys.stdin)
slug=payload['slug']; name=payload.get('name') or slug; description=payload.get('description') or ('Projeto CloudIFF: '+slug)
members=payload.get('desired_members') or []
owner_name=(payload.get('owner') or '').strip().lower()
by_name={str(x.get('username') or '').strip().lower():x for x in members if str(x.get('username') or '').strip()}
if owner_name and owner_name not in by_name: by_name[owner_name]={'username':owner_name,'email':'','full_name':owner_name,'is_owner':True}
unresolved=[]; pending_identity=[]; created_users=[]
def user_for(spec):
    username=str(spec.get('username') or '').strip().lower(); source_email=str(spec.get('email') or '').strip().lower(); full=str(spec.get('full_name') or username).strip() or username
    if not username:return None
    email_collision=bool(source_email and User.objects.filter(email__iexact=source_email).exists())
    placeholder=(not bool(source_email)) or email_collision
    email=(username+'@pending.cloudif.invalid') if placeholder else source_email
    u=User.objects.filter(username__iexact=username).first()
    if not u:
        u=User.objects.create(username=username,email=email,full_name=full,is_active=True,verified_email=not placeholder)
        u.set_unusable_password();u.save(update_fields=['password'])
        created_users.append(username)
    else:
        changed=[]
        current_email=str(u.email or '').strip().lower()
        if source_email and source_email!=current_email and (not current_email or current_email.endswith('@pending.cloudif.invalid')):
            collision=User.objects.filter(email__iexact=source_email).exclude(pk=u.pk).exists()
            if not collision:
                u.email=source_email;changed.append('email')
                if hasattr(u,'verified_email') and not u.verified_email:
                    u.verified_email=True;changed.append('verified_email')
        if full and (not u.full_name or u.full_name==u.username) and u.full_name!=full:
            u.full_name=full;changed.append('full_name')
        if not u.is_active:
            u.is_active=True;changed.append('is_active')
        if changed:u.save(update_fields=changed)
    if str(u.email or '').strip().lower().endswith('@pending.cloudif.invalid'):
        pending_identity.append(username)
    return u
with transaction.atomic():
    resolved={}
    for username,spec in by_name.items():
        u=user_for(spec)
        if u:resolved[username]=u
    owner=resolved.get(owner_name)
    p=Project.objects.filter(slug=slug).first()
    if not p and not owner:
        print(json.dumps({'ok':True,'status':'waiting_identity','slug':slug,'project_created':False,'unresolved':sorted(set(unresolved)),'added':[],'removed':[],'kept':[],'secrets_exposed':False},separators=(',',':')));raise SystemExit()
    created=False
    if not p:
        tmpl=ProjectTemplate.objects.get(slug='scrum')
        p=Project.objects.create(name=name,slug=slug,description=description,owner=owner,creation_template=tmpl,is_private=True)
        created=True
    else:
        changed=[]
        if p.name!=name:p.name=name;changed.append('name')
        if owner and p.owner_id!=owner.id:p.owner=owner;changed.append('owner')
        if changed:p.save(update_fields=changed)
    # Managed role with full member permissions cloned from the template's first computable role.
    base=p.roles.filter(computable=True).order_by('order','id').first() or p.roles.first()
    role=p.roles.filter(slug='cloudiff-member').first()
    if not role:
        role=Role.objects.create(project=p,name='Membro CloudIFF',slug='cloudiff-member',permissions=list(base.permissions or []),order=45,computable=True)
    elif list(role.permissions or [])!=list(base.permissions or []):
        role.permissions=list(base.permissions or []);role.save(update_fields=['permissions'])
    owner_role=p.roles.filter(slug='product-owner').first() or p.roles.first()
    desired_user_ids={u.id for u in resolved.values()}
    current_by_uid={m.user_id:m for m in p.memberships.select_related('user','role').filter(user__isnull=False)}
    added=[];kept=[];removed=[]
    for username,u in resolved.items():
        target_role=owner_role if username==owner_name else role
        is_admin=(username==owner_name)
        m=current_by_uid.get(u.id)
        if not m:
            Membership.objects.create(user=u,project=p,role=target_role,is_admin=is_admin,email=u.email or None)
            added.append(username)
        else:
            changes=[]
            if m.role_id!=target_role.id:m.role=target_role;changes.append('role')
            if m.is_admin!=is_admin:m.is_admin=is_admin;changes.append('is_admin')
            if changes:m.save(update_fields=changes)
            kept.append(username)
    # CloudIFF is authoritative for project membership. Compare by immutable Taiga user_id,
    # because OIDC nickname may differ from the institutional CloudIFF username.
    for uid,m in list(current_by_uid.items()):
        if uid not in desired_user_ids:
            actual=m.user.username
            m.delete();removed.append(actual)
    status='waiting_identity' if (unresolved or pending_identity) else 'ready'
    print(json.dumps({'ok':True,'status':status,'slug':slug,'project_id':p.id,'project_created':created,'created_users':sorted(created_users),'unresolved':sorted(set(unresolved)),'pending_identity':sorted(set(pending_identity)),'added':sorted(added),'removed':sorted(removed),'kept':sorted(kept),'desired_count':len(by_name),'secrets_exposed':False},separators=(',',':')))
'''
def reconcile(payload):
    if not isinstance(payload,dict):return {'ok':False,'error':'invalid_payload'}
    slug=str(payload.get('slug') or '')
    if not SLUG.fullmatch(slug):return {'ok':False,'error':'invalid_slug'}
    members=payload.get('desired_members') or []
    if not isinstance(members,list) or len(members)>500:return {'ok':False,'error':'invalid_members'}
    safe={'slug':slug,'name':str(payload.get('name') or slug)[:200],'description':str(payload.get('description') or '')[:2000],'owner':str(payload.get('owner') or '')[:150],'desired_members':[]}
    for x in members:
        if not isinstance(x,dict):continue
        u=str(x.get('username') or '').strip().lower()
        if not re.fullmatch(r'[A-Za-z0-9_.@-]{1,150}',u):continue
        safe['desired_members'].append({'username':u,'email':str(x.get('email') or '')[:320].lower(),'full_name':str(x.get('full_name') or u)[:200],'is_owner':bool(x.get('is_owner'))})
    p=subprocess.run(['docker','exec','-i',CONTAINER,'/opt/venv/bin/python','/taiga-back/manage.py','shell','-c',DJANGO],input=json.dumps(safe),text=True,capture_output=True,timeout=120)
    if p.returncode!=0:return {'ok':False,'error':'django_reconcile_failed','error_type':'subprocess','returncode':p.returncode}
    lines=[x for x in p.stdout.splitlines() if x.strip().startswith('{')]
    if not lines:return {'ok':False,'error':'invalid_django_response'}
    try:return json.loads(lines[-1])
    except Exception:return {'ok':False,'error':'invalid_json_response'}
DJANGO_GRANT_ACCESS = r'''
import json,sys
from django.db import transaction
from taiga.projects.models import Project,Membership
from taiga.users.models import User
payload=json.load(sys.stdin)
slug=str(payload.get('slug') or '').strip().lower()
username=str(payload.get('username') or '').strip().lower()
email=str(payload.get('email') or '').strip().lower()
full_name=str(payload.get('full_name') or username).strip() or username
p=Project.objects.filter(slug=slug).first()
if not p:
    print(json.dumps({'ok':False,'error':'project_not_found','secrets_exposed':False},separators=(',',':')));raise SystemExit()
u=User.objects.filter(username__iexact=username).first()
created_user=False
identity_pending=False
if not u:
    collision=bool(email and User.objects.filter(email__iexact=email).exists())
    effective_email=email if (email and not collision) else (username+'@pending.cloudif.invalid')
    identity_pending=collision or not bool(email)
    u=User.objects.create(username=username,email=effective_email,full_name=full_name,is_active=True,verified_email=not identity_pending)
    u.set_unusable_password();u.save(update_fields=['password']);created_user=True
else:
    changed=[]
    if email and not u.email:u.email=email;changed.append('email')
    if full_name and (not u.full_name or u.full_name==u.username) and u.full_name!=full_name:u.full_name=full_name;changed.append('full_name')
    if not u.is_active:u.is_active=True;changed.append('is_active')
    if changed:u.save(update_fields=changed)
with transaction.atomic():
    role=p.roles.filter(slug='product-owner').first() or p.roles.filter(computable=True).order_by('order','id').first() or p.roles.first()
    membership=Membership.objects.filter(project=p,user=u).first()
    created_membership=False
    if not membership:
        membership=Membership.objects.create(project=p,user=u,role=role,is_admin=True,email=u.email or None)
        created_membership=True
    else:
        changes=[]
        if role and membership.role_id!=role.id:membership.role=role;changes.append('role')
        if not membership.is_admin:membership.is_admin=True;changes.append('is_admin')
        if changes:membership.save(update_fields=changes)
print(json.dumps({'ok':True,'slug':slug,'taiga_username':u.username,'created_user':created_user,'created_membership':created_membership,'is_admin':True,'identity_pending':identity_pending or str(u.email or '').lower().endswith('@pending.cloudif.invalid'),'secrets_exposed':False},separators=(',',':')))
'''

def grant_access(slug,payload):
    if not SLUG.fullmatch(slug):return {'ok':False,'error':'invalid_slug'}
    if not isinstance(payload,dict):return {'ok':False,'error':'invalid_payload'}
    username=str(payload.get('username') or '').strip().lower()
    email=str(payload.get('email') or '').strip().lower()
    full_name=str(payload.get('full_name') or username).strip()
    if not re.fullmatch(r'[A-Za-z0-9_.@-]{1,150}',username):return {'ok':False,'error':'invalid_username'}
    if email and (len(email)>320 or '@' not in email):return {'ok':False,'error':'invalid_email'}
    safe={'slug':slug,'username':username,'email':email[:320],'full_name':full_name[:200]}
    p=subprocess.run(['docker','exec','-i',CONTAINER,'/opt/venv/bin/python','/taiga-back/manage.py','shell','-c',DJANGO_GRANT_ACCESS],input=json.dumps(safe),text=True,capture_output=True,timeout=60)
    if p.returncode!=0:return {'ok':False,'error':'django_grant_failed','error_type':'subprocess','returncode':p.returncode}
    lines=[x for x in p.stdout.splitlines() if x.strip().startswith('{')]
    if not lines:return {'ok':False,'error':'invalid_django_response'}
    try:return json.loads(lines[-1])
    except Exception:return {'ok':False,'error':'invalid_json_response'}

DJANGO_DELETE = r'''
import json,sys
from django.db import transaction
from taiga.projects.models import Project
payload=json.load(sys.stdin)
slug=payload['slug']
with transaction.atomic():
    p=Project.objects.filter(slug=slug).first()
    if not p:
        print(json.dumps({'ok':True,'status':'already_absent','slug':slug,'project_deleted':False,'memberships_removed':0,'global_users_deleted':0,'secrets_exposed':False},separators=(',',':')))
        raise SystemExit()
    project_id=p.id
    memberships=p.memberships.filter(user__isnull=False).count()
    p.delete()
    print(json.dumps({'ok':True,'status':'deleted','slug':slug,'project_id':project_id,'project_deleted':True,'memberships_removed':memberships,'global_users_deleted':0,'secrets_exposed':False},separators=(',',':')))
'''

def delete_project(slug):
    if not SLUG.fullmatch(slug):
        return {'ok':False,'error':'invalid_slug'}
    p=subprocess.run(['docker','exec','-i',CONTAINER,'/opt/venv/bin/python','/taiga-back/manage.py','shell','-c',DJANGO_DELETE],input=json.dumps({'slug':slug}),text=True,capture_output=True,timeout=120)
    if p.returncode!=0:
        return {'ok':False,'error':'django_delete_failed','error_type':'subprocess','returncode':p.returncode}
    lines=[x for x in p.stdout.splitlines() if x.strip().startswith('{')]
    if not lines:
        return {'ok':False,'error':'invalid_django_response'}
    try:
        return json.loads(lines[-1])
    except Exception:
        return {'ok':False,'error':'invalid_json_response'}

DJANGO_SUMMARY = r'''
import json,sys
from django.db.models import Q
from taiga.projects.models import Project,Membership
from taiga.projects.tasks.models import Task
from taiga.projects.userstories.models import UserStory
from taiga.projects.milestones.models import Milestone
from taiga.projects.history.models import HistoryEntry
from taiga.users.models import User
payload=json.load(sys.stdin)
slug=payload['slug'];subject=str(payload.get('subject') or '').strip().lower();include_members=bool(payload.get('include_members'))
p=Project.objects.filter(slug=slug).first()
if not p:
    print(json.dumps({'ok':False,'error':'project_not_found','slug':slug,'secrets_exposed':False},separators=(',',':')));raise SystemExit()

def iso(value):
    return value.isoformat().replace('+00:00','Z') if value else None

def task_q(username):
    return Task.objects.filter(project=p).filter(Q(assigned_to__username__iexact=username)|Q(owner__username__iexact=username)).distinct()

def story_q(username):
    return UserStory.objects.filter(project=p).filter(Q(assigned_to__username__iexact=username)|Q(assigned_users__username__iexact=username)|Q(owner__username__iexact=username)).distinct()

def history_q(username=''):
    q=HistoryEntry.objects.filter(project=p,is_hidden=False)
    if username:
        u=User.objects.filter(username__iexact=username).first()
        if not u:return q.none()
        q=q.filter(user__pk=u.pk)
    return q

def metrics(username):
    tq=task_q(username);sq=story_q(username);hq=history_q(username)
    membership=Membership.objects.filter(project=p,user__username__iexact=username).select_related('user').first()
    u=membership.user if membership else None
    return {'username':username,'last_login':iso(getattr(u,'last_login',None)),'tasks_assigned':tq.count(),'tasks_closed':tq.filter(status__is_closed=True).count(),'stories_assigned':sq.count(),'stories_closed':sq.filter(is_closed=True).count(),'history_events':hq.count(),'last_activity':iso(hq.order_by('-created_at').values_list('created_at',flat=True).first())}
counts={'tasks':Task.objects.filter(project=p).count(),'tasks_closed':Task.objects.filter(project=p,status__is_closed=True).count(),'userstories':UserStory.objects.filter(project=p).count(),'userstories_closed':UserStory.objects.filter(project=p,is_closed=True).count(),'milestones':Milestone.objects.filter(project=p).count(),'milestones_closed':Milestone.objects.filter(project=p,closed=True).count(),'members':Membership.objects.filter(project=p,user__isnull=False).count()}
members=[]
if include_members:
    for m in Membership.objects.filter(project=p,user__isnull=False).select_related('user','role').order_by('user__username'):
        item=metrics(m.user.username.lower());item.update({'full_name':str(m.user.full_name or m.user.username)[:200],'role':str(getattr(m.role,'name','') or '')[:120],'is_admin':bool(m.is_admin)});members.append(item)
subject_metrics=metrics(subject) if subject else None
history=list(history_q(subject).order_by('-created_at')[:100])
user_ids=sorted({int((x.user or {}).get('pk')) for x in history if isinstance(x.user,dict) and str((x.user or {}).get('pk') or '').isdigit()})
usernames=dict(User.objects.filter(pk__in=user_ids).values_list('pk','username')) if user_ids else {}
timeline=[]
for x in history:
    raw=x.user if isinstance(x.user,dict) else {}
    try:uid=int(raw.get('pk'))
    except Exception:uid=0
    timeline.append({'ts':iso(x.created_at),'actor':str(usernames.get(uid) or '')[:150].lower(),'type':str(x.type or '')[:80],'key':str(x.key or '')[:180]})
print(json.dumps({'ok':True,'project':{'id':p.id,'slug':p.slug,'name':str(p.name)[:200]},'counts':counts,'subject':subject_metrics,'members':members,'timeline':timeline,'secrets_exposed':False},separators=(',',':')))
'''


def project_summary(slug,subject='',include_members=False):
    if not SLUG.fullmatch(slug):return {'ok':False,'error':'invalid_slug'}
    subject=str(subject or '').strip().lower()
    if subject and not re.fullmatch(r'[A-Za-z0-9_.@-]{1,150}',subject):return {'ok':False,'error':'invalid_subject'}
    payload={'slug':slug,'subject':subject,'include_members':bool(include_members)}
    p=subprocess.run(['docker','exec','-i',CONTAINER,'/opt/venv/bin/python','/taiga-back/manage.py','shell','-c',DJANGO_SUMMARY],input=json.dumps(payload),text=True,capture_output=True,timeout=120)
    if p.returncode!=0:return {'ok':False,'error':'django_summary_failed','error_type':'subprocess','returncode':p.returncode}
    lines=[x for x in p.stdout.splitlines() if x.strip().startswith('{')]
    if not lines:return {'ok':False,'error':'invalid_django_response'}
    try:return json.loads(lines[-1])
    except Exception:return {'ok':False,'error':'invalid_json_response'}


class H(BaseHTTPRequestHandler):
    server_version='cloudif-taiga-reconciler/0.4.1'
    def log_message(self,fmt,*args):pass
    def out(self,code,obj):
        b=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def auth(self):
        got=self.headers.get('Authorization','');exp='Bearer '+TOKEN
        return bool(TOKEN) and hmac.compare_digest(got,exp)
    def do_GET(self):
        parsed=urlparse(self.path);path=parsed.path
        if path=='/health':return self.out(200,{'ok':True,'service':'cloudif-taiga-reconciler','version':'0.4.1'})
        if not self.auth():return self.out(401,{'ok':False,'error':'unauthorized'})
        sm=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/summary',path)
        if sm:
            from urllib.parse import parse_qs
            q=parse_qs(parsed.query);subject=str((q.get('subject') or [''])[0]);include=str((q.get('include_members') or ['0'])[0]).lower() in {'1','true','yes'}
            result=project_summary(sm.group(1),subject,include)
            return self.out(200 if result.get('ok') else (404 if result.get('error')=='project_not_found' else 502),result)
        return self.out(404,{'ok':False,'error':'not_found'})
    def do_POST(self):
        path=urlparse(self.path).path
        if not self.auth():return self.out(401,{'ok':False,'error':'unauthorized'})
        gm=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/access/grant',path)
        if gm:
            n=int(self.headers.get('Content-Length','0') or 0)
            if n<1 or n>8192:return self.out(413,{'ok':False,'error':'invalid_size'})
            try:payload=json.loads(self.rfile.read(n))
            except Exception:return self.out(400,{'ok':False,'error':'invalid_json'})
            result=grant_access(gm.group(1),payload)
            status=200 if result.get('ok') else (404 if result.get('error')=='project_not_found' else 400 if result.get('error') in {'invalid_slug','invalid_payload','invalid_username','invalid_email','email_required'} else 502)
            return self.out(status,result)
        dm=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/delete',path)
        if dm:
            n=int(self.headers.get('Content-Length','0') or 0)
            if n<1 or n>4096:return self.out(413,{'ok':False,'error':'invalid_size'})
            try:payload=json.loads(self.rfile.read(n))
            except Exception:return self.out(400,{'ok':False,'error':'invalid_json'})
            if str(payload.get('confirm_slug') or '')!=dm.group(1):return self.out(400,{'ok':False,'error':'invalid_confirmation'})
            result=delete_project(dm.group(1))
            return self.out(200 if result.get('ok') else 502,result)
        m=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/reconcile',path)
        if not m:return self.out(404,{'ok':False,'error':'not_found'})
        n=int(self.headers.get('Content-Length','0') or 0)
        if n<1 or n>200000:return self.out(413,{'ok':False,'error':'invalid_size'})
        try:payload=json.loads(self.rfile.read(n))
        except Exception:return self.out(400,{'ok':False,'error':'invalid_json'})
        payload['slug']=m.group(1);result=reconcile(payload)
        return self.out(200 if result.get('ok') else 502,result)
if __name__=='__main__':
    if not TOKEN:raise SystemExit('TAIGA_RECONCILER_TOKEN missing')
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()
