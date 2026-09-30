from pathlib import Path
import json,hashlib,shlex,time
root=Path('/workspace/scratch/7d2bd7b992e8/btc15/event_ground_zero/results')
raw=(root/'payload.json').read_bytes();mapping=json.loads(raw)
revision='90a24b1189a6bae8403e46149313716d19f56229'
end=int(time.time())+2100
commands={}
for mode,original in [('main','btc15_information_install_v1.py'),('v81','v81_30_45_live_feed.py')]:
 program=f'''import hashlib,json,os,sys
from pathlib import Path
from urllib.request import urlopen
try:
    with urlopen('https://raw.githubusercontent.com/yz272n2tpf-lab/Btc-15min-bot/{revision}/capture2_payload.json',timeout=15) as response:
        raw=response.read(100001)
    if hashlib.sha256(raw).hexdigest()!={hashlib.sha256(raw).hexdigest()!r}:raise ValueError('PAYLOAD_HASH')
    files=json.loads(raw)
    if set(files)!=set({list(mapping)!r}):raise ValueError('PAYLOAD_PATHS')
    for name,content in files.items():
        compile(content,name,'exec')
        if Path(name).exists() and Path(name).read_text()!=content:raise ValueError('EXISTING_CAPTURE_CONFLICT')
    for name,content in files.items():
        path=Path(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
except Exception as exc:
    print('GROUND_ZERO_BOOTSTRAP_UNAVAILABLE | '+type(exc).__name__+' | original launcher',flush=True)
    os.execv(sys.executable,[sys.executable,'-u',{original!r}])
os.environ['BTC15_CAPTURE_END_UTC']={str(end)!r}
os.environ['BTC15_CAPTURE_REVISION']={revision!r}
os.execv(sys.executable,[sys.executable,'-u','-m','capture2.install','--mode',{mode!r},'--approved-capture-only'])
'''
 compile(program,'<bootstrap>','exec')
 cmd='python -u -c '+shlex.quote(program)
 baseline=json.loads((root/f'preinstall-{mode}.json').read_text())['config']['deploy']['startCommand']
 if mode=='main':
  shell,flag,inner=shlex.split(baseline)
  assert inner.count('exec python -u btc15_information_install_v1.py')==1
  cmd=shell+' '+flag+' '+shlex.quote(inner.replace('exec python -u btc15_information_install_v1.py','exec '+cmd))
 commands[mode]=dict(startCommand=cmd,original=baseline,command_sha256=hashlib.sha256(cmd.encode()).hexdigest(),capture_revision=revision,end_utc=end)
(root/'controlled-install.json').write_text(json.dumps(commands,indent=2)+'\n')
print(json.dumps({k:{x:v[x] for x in ('capture_revision','end_utc','command_sha256')} for k,v in commands.items()}))
