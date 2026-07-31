#!/usr/bin/env python3
import argparse, json, sys
sys.path.insert(0,"/srv/cloudif/lib")
import cloudif_release_manager as releases

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    sub.add_parser("init")
    d=sub.add_parser("dispatch"); d.add_argument("--limit",type=int,default=3)
    r=sub.add_parser("run-job"); r.add_argument("job_id",type=int)
    s=sub.add_parser("status"); s.add_argument("job_id",type=int)
    args=ap.parse_args()
    if args.cmd=="init": releases.ensure_schema(); print(json.dumps({"ok":True})); return
    if args.cmd=="dispatch": print(json.dumps(releases.dispatch_due(args.limit),ensure_ascii=False)); return
    if args.cmd=="run-job": print(json.dumps(releases.process_job(args.job_id),ensure_ascii=False)); return
    if args.cmd=="status": print(json.dumps(releases.get_job(args.job_id) or {"ok":False,"error":"not_found"},ensure_ascii=False)); return
if __name__=="__main__": main()
