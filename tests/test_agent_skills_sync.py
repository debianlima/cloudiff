#!/usr/bin/env python3
from pathlib import Path
import hashlib,io,os,subprocess,tarfile,tempfile
root=Path(__file__).resolve().parents[1]
script=root/'deploy/sync_agent_skills.sh'
s=script.read_text()
for needle in ('CLOUDIFF_AGENT_SKILLS_ALLOWED_HOSTS','CLOUDIFF_AGENT_SKILLS_ROOT','DRY_RUN_PASS','baseline_diverged','new_manifest_mismatch','current.new','mv -Tf','ROLLBACK_PASS','NOOP','unsupported archive member','current_not_symlink'):
    assert needle in s,needle
for banned in ('apt install','apt-get install','docker run','opencode','open-code','systemctl enable','npm install','pip install'):
    assert banned.lower() not in s.lower(),banned

def manifest(tree:Path,out:Path):
    rows=[]
    for p in sorted(x for x in tree.rglob('*') if x.is_file()):
        rel='./'+p.relative_to(tree).as_posix();mode=oct(p.stat().st_mode & 0o777)[2:]
        rows.append(f"{mode} {hashlib.sha256(p.read_bytes()).hexdigest()} {rel}\n")
    out.write_text(''.join(rows))

def make_release(tree:Path,version:str,body:str):
    d=tree/'cloudiff';d.mkdir(parents=True)
    p=d/'SKILL.md';p.write_text(f"---\nname: cloudiff\nversao: {version}\n---\n{body}\n");p.chmod(0o644)

def archive(tree:Path,out:Path):
    with tarfile.open(out,'w:gz') as t:
        for p in sorted(tree.rglob('*')):t.add(p,arcname=p.relative_to(tree).as_posix(),recursive=False)

def run(args,env,ok=True):
    def restrictive_umask(): os.umask(0o077)
    r=subprocess.run([str(script),*args],text=True,capture_output=True,env=env,preexec_fn=restrictive_umask)
    if ok: assert r.returncode==0,(r.returncode,r.stdout,r.stderr)
    else: assert r.returncode!=0,(r.stdout,r.stderr)
    return r

with tempfile.TemporaryDirectory() as td:
    t=Path(td);skills=t/'skills';rels=skills/'releases';rels.mkdir(parents=True)
    base=rels/'base';newsrc=t/'newsrc';make_release(base,'1','base');make_release(newsrc,'2','new')
    os.symlink(base,skills/'current')
    bm=t/'baseline.txt';nm=t/'new.txt';manifest(base,bm);manifest(newsrc,nm)
    arc=t/'new.tar.gz';archive(newsrc,arc)
    env=os.environ.copy();env.update(CLOUDIFF_AGENT_SKILLS_ROOT=str(skills),CLOUDIFF_AGENT_SKILLS_ALLOWED_HOSTS=os.uname().nodename.split('.')[0],CLOUDIFF_AGENT_SKILLS_OWNER=f'{os.getuid()}:{os.getgid()}')
    cur0=os.path.realpath(skills/'current')
    r=run(['dry-run',str(arc),'release-2',str(bm),str(nm)],env);assert 'DRY_RUN_PASS' in r.stdout;assert os.path.realpath(skills/'current')==cur0;assert not (rels/'release-2').exists()
    r=run(['install',str(arc),'release-2',str(bm),str(nm)],env);assert 'SYNC=PASS' in r.stdout;assert os.path.realpath(skills/'current')==str(rels/'release-2');assert os.path.realpath(skills/'previous')==str(base)
    # Second install must validate target then no-op; baseline for current is now the new manifest.
    r=run(['install',str(arc),'release-2',str(nm),str(nm)],env);assert 'SYNC=NOOP' in r.stdout
    r=run(['rollback'],env);assert 'ROLLBACK_PASS' in r.stdout;assert os.path.realpath(skills/'current')==str(base);assert os.path.realpath(skills/'previous')==str(rels/'release-2')
    # Existing immutable target never makes a mismatched archive acceptable.
    corrupt=t/'corrupt.tar.gz'
    with tarfile.open(corrupt,'w:gz') as tf:
        data=b'---\nname: cloudiff\nversao: CORRUPT\n---\n';ti=tarfile.TarInfo('cloudiff/SKILL.md');ti.size=len(data);tf.addfile(ti,io.BytesIO(data))
    r=run(['dry-run',str(corrupt),'release-2',str(bm),str(nm)],env,ok=False);assert r.returncode==29 and 'new_manifest_mismatch' in r.stderr
    # FIFO, symlink and hardlink are undeclared filesystem objects and are rejected.
    for kind in ('fifo','symlink','hardlink'):
        special=t/f'{kind}.tar.gz'
        with tarfile.open(special,'w:gz') as tf:
            data=(newsrc/'cloudiff'/'SKILL.md').read_bytes();ti=tarfile.TarInfo('cloudiff/SKILL.md');ti.size=len(data);tf.addfile(ti,io.BytesIO(data))
            x=tarfile.TarInfo('cloudiff/extra')
            if kind=='fifo': x.type=tarfile.FIFOTYPE
            elif kind=='symlink': x.type=tarfile.SYMTYPE;x.linkname='SKILL.md'
            else: x.type=tarfile.LNKTYPE;x.linkname='cloudiff/SKILL.md'
            tf.addfile(x)
        r=run(['dry-run',str(special),'release-special',str(bm),str(nm)],env,ok=False);assert 'unsupported archive member' in r.stderr,(kind,r.returncode,r.stderr)
    # Atomic promotion refuses a non-symlink current before creating release/pointer artifacts.
    root2=t/'root2';cur2=root2/'current';make_release(cur2,'1','base');bm2=t/'baseline2.txt';manifest(cur2,bm2)
    env2=env.copy();env2['CLOUDIFF_AGENT_SKILLS_ROOT']=str(root2)
    r=run(['install',str(arc),'release-x',str(bm2),str(nm)],env2,ok=False);assert r.returncode==33 and 'current_not_symlink' in r.stderr
    assert not (root2/'previous').exists() and not (root2/'current.new').exists() and not (root2/'releases'/'release-x').exists()
    # Baseline divergence is rejected before any promotion.
    (base/'drift.txt').write_text('drift')
    r=run(['dry-run',str(arc),'release-3',str(bm),str(nm)],env,ok=False);assert 'baseline_diverged' in r.stderr
    # Host allowlist failure is explicit.
    env_bad=env.copy();env_bad['CLOUDIFF_AGENT_SKILLS_ALLOWED_HOSTS']='definitely-not-this-host'
    r=run(['dry-run',str(arc),'release-3',str(bm),str(nm)],env_bad,ok=False);assert 'host_not_allowed' in r.stderr
    # Unsafe archive path is rejected.
    bad=t/'bad.tar.gz'
    with tarfile.open(bad,'w:gz') as tf:
        ti=tarfile.TarInfo('../SKILL.md');data=b'x';ti.size=len(data);tf.addfile(ti,io.BytesIO(data))
    r=run(['dry-run',str(bad),'bad-release',str(bm),str(nm)],env,ok=False);assert r.returncode!=0
print('AGENT_SKILLS_SYNC_OFFLINE=PASS dry_run=true atomic=true noop=true rollback=true divergence_reject=true allowlist=true no_agent_install=true')
