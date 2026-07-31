#!/usr/bin/env python3
import collections,hashlib,json,os,shutil,subprocess,time
FIX='/srv/cloudif/test-fixtures/node24-http'; OUT='/srv/cloudif/artifacts/node24-http-fixture'; STATE='/var/lib/cloudif/node24-pipeline/result.json'
BUILDER='node@sha256:a0b9bf06e4e6193cf7a0f58816cc935ff8c2a908f81e6f1a95432d679c54fbfd'
RUNTIME='gcr.io/distroless/nodejs24-debian13@sha256:af85d11ce7ef10172855a6e3649e3e8125b1b9e3ca41849ec2918036f05cb212'
SYFT=os.environ['SYFT_IMAGE'];TRIVY=os.environ['TRIVY_IMAGE'];CACHE='/srv/cloudif/scanners/trivy-cache'
def run(cmd,timeout=900):subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=timeout)
def sha(p):return hashlib.sha256(open(p,'rb').read()).hexdigest()
def main():
 t=int(time.time());ctx=OUT+'/pipeline-context';shutil.rmtree(ctx,ignore_errors=True);os.makedirs(ctx,exist_ok=True)
 for n in ('package.json','package-lock.json','server.js','server.test.js'):shutil.copy2(FIX+'/'+n,ctx+'/'+n)
 dockerfile=f'''FROM {BUILDER} AS test\nWORKDIR /app\nCOPY package.json package-lock.json ./\nRUN npm ci --ignore-scripts --no-audit --no-fund --offline\nCOPY server.js server.test.js ./\nRUN npm test\nFROM {RUNTIME}\nWORKDIR /app\nCOPY --from=test --chown=65532:65532 /app/package.json /app/package-lock.json /app/server.js ./\nENV PORT=8080 NODE_ENV=production\nEXPOSE 8080\nCMD ["server.js"]\n'''
 open(ctx+'/Dockerfile','w').write(dockerfile);tag='cloudif-node/node24-http-fixture:homologation-'+str(t)
 run(['docker','build','--pull=false','--network=none','-t',tag,ctx]);iid=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip()
 name='cloudif-node24-homologation';subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 run(['docker','run','-d','--name',name,'--network','none','--read-only','--user','65532:65532','--tmpfs','/tmp:rw,noexec,nosuid,size=16m,mode=1777','--memory','256m','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',tag],120);time.sleep(3)
 running=subprocess.check_output(['docker','inspect','-f','{{.State.Running}}',name],text=True).strip()=='true';assert running
 user=subprocess.check_output(['docker','inspect','-f','{{.Config.User}}',name],text=True).strip();caps=json.loads(subprocess.check_output(['docker','inspect','-f','{{json .HostConfig.CapDrop}}',name],text=True));ports=json.loads(subprocess.check_output(['docker','inspect','-f','{{json .HostConfig.PortBindings}}',name],text=True));subprocess.run(['docker','rm','-f',name],check=True,stdout=subprocess.DEVNULL)
 os.makedirs(OUT,exist_ok=True);sb=OUT+'/pipeline-sbom.cdx.json';sc=OUT+'/pipeline-trivy.json'
 run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=256m,mode=1777','--tmpfs','/.cache:rw,noexec,nosuid,size=64m,mode=1777','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','768m','--pids-limit','256','-e','SYFT_CHECK_FOR_APP_UPDATE=false','-v','/var/run/docker.sock:/var/run/docker.sock:ro','-v',OUT+':/out',SYFT,tag,'-o','cyclonedx-json=/out/pipeline-sbom.cdx.json'])
 run(['docker','run','--rm','--network','none','--tmpfs','/tmp:rw,noexec,nosuid,size=256m,mode=1777','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1g','--pids-limit','256','-v','/var/run/docker.sock:/var/run/docker.sock:ro','-v',CACHE+':/root/.cache/trivy','-v',OUT+':/out',TRIVY,'image','--skip-db-update','--format','json','--output','/out/pipeline-trivy.json',tag])
 bom=json.load(open(sb));scan=json.load(open(sc));counts=collections.Counter()
 for r in scan.get('Results') or []:
  for v in r.get('Vulnerabilities') or []:counts[(v.get('Severity') or 'UNKNOWN').upper()]+=1
 blocked=counts['HIGH']+counts['CRITICAL']>0
 result={'ok':not blocked,'status':'ready' if not blocked else 'blocked','node_version':'24','builder_image':BUILDER,'runtime_image':RUNTIME,'artifact_image_id':iid,'artifact_tag':tag,'lockfile_sha256':sha(FIX+'/package-lock.json'),'sbom_format':bom.get('bomFormat'),'sbom_spec_version':bom.get('specVersion'),'sbom_components':len(bom.get('components') or []),'sbom_sha256':sha(sb),'scanner_counts':dict(counts),'scanner_blocked':blocked,'scanner_sha256':sha(sc),'runtime_proof':{'user':user,'read_only':True,'cap_drop':caps,'published_ports':[] if ports in (None,{}) else ports,'listen_port':8080},'build_network':'none','production_effects_enabled':False,'updated_at':t,'secrets_exposed':False}
 assert not blocked and user in ('65532','65532:65532') and caps==['ALL'] and ports in (None,{})
 tmp=STATE+'.tmp';open(tmp,'w').write(json.dumps(result,separators=(',',':'))+'\n');os.replace(tmp,STATE);print(json.dumps(result))
if __name__=='__main__':main()
