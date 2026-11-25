#!/usr/bin/env python3
"""Запускает проверки в терминале и сохраняет фактический вывод."""
import json
from pathlib import Path
import shlex
import subprocess
import sys

base=Path(__file__).resolve().parent
prev=base.parent/'12-kubernetes-03-run-applications'
k=[str(prev/'bin/kubectl'),'--kubeconfig',str(prev/'.kubeconfig')]
ns=k+['-n','homework-23']
stage=sys.argv[1]
if stage=='01-conflict':
    commands=[ns+['get','pods','-l','app=web'],ns+['logs','deployment/web','-c','multitool','--tail=10']]
elif stage=='02-configmap':
    commands=[ns+['get','configmaps'],ns+['get','pods','-l','app=web'],
              ns+['exec','deployment/web','-c','multitool','--','printenv','HTTP_PORT','HTTPS_PORT'],
              ns+['get','service','web'],
              ns+['exec','deployment/web','-c','multitool','--','curl','-fsS','http://web:80'],
              ns+['exec','deployment/web','-c','nginx','--','wget','-qO-','http://web:8080']]
elif stage=='03-ingress':
    commands=[ns+['get','deployments'],ns+['get','pods'],ns+['get','services'],
              ns+['get','secret','web-tls'],ns+['get','ingress','secure-web'],
              ns+['get','ingress','secure-web','-o','jsonpath={.spec.tls}']]
elif stage=='04-https':
    node=json.loads(subprocess.check_output(k+['get','nodes','-o','json'],text=True))['items'][0]
    ip=next(a['address'] for a in node['status']['addresses'] if a['type']=='InternalIP')
    commands=[['openssl','x509','-in','certs/tls.crt','-noout','-subject','-issuer','-ext','subjectAltName'],
              ['openssl','s_client','-connect',ip+':30443','-servername','homework23.test','-CAfile','certs/tls.crt','-verify_hostname','homework23.test','-verify_return_error','-brief'],
              ['curl','--noproxy','*','--cacert','certs/tls.crt','--resolve','homework23.test:30443:'+ip,'-fsSi','https://homework23.test:30443/']]
elif stage=='05-curl-k':
    node=json.loads(subprocess.check_output(k+['get','nodes','-o','json'],text=True))['items'][0]
    ip=next(a['address'] for a in node['status']['addresses'] if a['type']=='InternalIP')
    commands=[['curl','--noproxy','*','-k','--resolve','homework23.test:30443:'+ip,'-fsSi','https://homework23.test:30443/']]
elif stage=='06-rbac-reader':
    pods=json.loads(subprocess.check_output(ns+['get','pods','-l','app=secure-web','-o','json'],text=True))['items']
    pod=pods[0]['metadata']['name']
    describe=shlex.join(ns+['--as=developer','describe','pod',pod,'--show-events=false'])+' | head -n 16'
    commands=[ns+['get','role','pod-reader'],ns+['get','rolebinding','developer-pod-reader'],
              ns+['get','pods','--as=developer'],
              ns+['--as=developer','logs',pod,'--tail=2'],
              ['bash','-o','pipefail','-c',describe]]
elif stage=='07-developer-access':
    dev=[k[0],'--kubeconfig','rbac/developer.kubeconfig']
    commands=[dev+['auth','whoami'],dev+['get','pods'],
              dev+['auth','can-i','get','pods/log'],
              dev+['auth','can-i','delete','pods'],
              dev+['auth','can-i','create','pods/exec'],
              dev+['auth','can-i','get','pods','-n','homework-14'],
              dev+['get','secrets']]
else:
    raise SystemExit('Unknown stage')
output=[]
for command in commands:
    shown=(['kubectl']+command[1:] if stage=='07-developer-access' else ['kubectl']+command[3:]) if command[0]==k[0] else command
    prompt='$ '+shlex.join(shown)
    print(prompt,flush=True)
    r=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,cwd=base,timeout=30)
    print(r.stdout,flush=True)
    output.append(prompt+'\n'+r.stdout)
    if r.returncode:
        expected_deny=stage=='07-developer-access' and r.returncode==1 and ('can-i' in command or command[-2:]==['get','secrets'])
        if not expected_deny: raise SystemExit(r.returncode)
        if 'can-i' in command: assert r.stdout.strip()=='no', r.stdout
        else: assert 'Forbidden' in r.stdout, r.stdout
(base/'evidence'/(stage+'.txt')).write_text('\n'.join(output))
