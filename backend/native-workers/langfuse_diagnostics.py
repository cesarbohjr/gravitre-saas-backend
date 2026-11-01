"""Sanitized startup diagnostics for disposable, synthetic Langfuse CI only."""
import json,os,re,subprocess
from pathlib import Path

config=str(Path(os.environ['RUNNER_TEMP'])/'langfuse-cert.yml')
base=['docker','compose','-p','native-langfuse-cert','-f',config]
# No production secret is supplied to this job. Also redact the fixture values
# before displaying server startup errors so this cannot become a secret logger.
redact=[v for k,v in os.environ.items() if len(v)>5 and any(word in k for word in ('SECRET','PASSWORD','TOKEN','KEY'))]
redact+=['mysalt','miniosecret','myredissecret','mysecret']
for service in ('langfuse-web','langfuse-worker'):
    result=subprocess.run([*base,'logs','--no-color','--tail','100',service],capture_output=True,text=True,timeout=20)
    for line in (result.stdout+result.stderr).splitlines():
        if not re.search(r'error|fatal|invalid|missing|failed|migration|exception',line,re.I):continue
        if re.search(r'authorization|cookie|set-cookie',line,re.I):continue
        for value in sorted(redact,key=len,reverse=True):line=line.replace(value,'[redacted]')
        line=re.sub(r'(?:https?|postgresql?|redis)://[^\s"\']+','[redacted-route]',line)
        print(json.dumps({'fixture_service':service,'startup_error':line[:700]}))
