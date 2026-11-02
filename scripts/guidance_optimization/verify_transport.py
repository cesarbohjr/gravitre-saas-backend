"""Actual DSPy/LiteLLM/OpenAI HTTP path against a local fixture, never quality proof."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import sys

from optimize import compile_candidates, evaluate, sdk

dspy=sdk()
original=dspy.LM
requests=[]

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_POST(self):
        request=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        requests.append(request)
        if request["model"]=="judge-fixture":
            data=json.loads(request["messages"][-1]["content"])
            content=json.dumps({"score":int(data["response"]=="controlled candidate reply"),"security_violation":False})
        else:
            content="controlled candidate reply" if len(request["messages"])>2 else "controlled baseline reply"
        result={"id":"fixture-response","object":"chat.completion","created":1,"model":request["model"],
                "choices":[{"index":0,"message":{"role":"assistant","content":content},"finish_reason":"stop"}],
                "usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}
        body=json.dumps(result).encode()
        self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)

server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()

def local_lm(model,**kwargs):
    return original(model,api_base=f"http://127.0.0.1:{server.server_port}/v1",api_key="fixture-only-not-a-credential",**kwargs)

dspy.LM=local_lm
try:
    result=evaluate(compile_candidates(),"openai/generation-fixture","openai/judge-fixture",evidence_mode="transport_fixture")
    assert len(result["rows"])==40 and len(requests)==80
    assert result["promotion_eligible"] is False
    assert result["production_certified"] is False
    assert {r["split"] for r in result["rows"]}=={"validation","holdout"}
    report={"status":"SDK_LOCAL_TRANSPORT_PASS","evidence_mode":"transport_fixture","requests":len(requests),
            "evaluated_rows":len(result["rows"]),"promotion_eligible":False,"provider_quality":"NOT_RUN","physical_voice":"NOT_RUN"}
    Path(sys.argv[1]).write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))
finally:
    dspy.LM=original
    server.shutdown();server.server_close();thread.join(timeout=5)
