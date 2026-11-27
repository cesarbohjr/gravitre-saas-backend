"""Generate and score blinded synthetic listening pairs, outside live runtime.

The private key must be held by a review coordinator, not the listeners.
A JSON reviewer ID is not authentication; coordinator verifies human identity.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import secrets
import wave
import itertools

from voice3_provider_quality import FIXTURES, synthesize, RATE
from voice3_pipecat_probe import candidate_ids

VERSION = "voice3-blind-v1"
DIMENSIONS = ("naturalness","emotion_appropriateness","warmth","emphasis","identity_continuity")
CHOICES = ("A","B","equal")
MIN_REVIEWERS = 3
PROTOCOLS = ("flash","dialogue")

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def write_json(path,value):
    path.write_text(json.dumps(value,indent=2)+"\n")

def generate(proposal,sha,key,public_dir,private_dir,client):
    candidate_ids(proposal,sha)
    if public_dir.resolve() == private_dir.resolve() or public_dir.resolve() in private_dir.resolve().parents or private_dir.resolve() in public_dir.resolve().parents:
        raise ValueError("reviewer and coordinator directories must be disjoint")
    public_dir.mkdir(parents=True,exist_ok=False)
    private_dir.mkdir(parents=True,exist_ok=False,mode=0o700)
    rng = random.SystemRandom()
    public, private = [], []
    jobs = [(row,fixture,text,protocol) for row in proposal["mapping"] if row.get("candidate_id")
            for fixture,text in FIXTURES for protocol in PROTOCOLS]
    rng.shuffle(jobs)
    for row,fixture,text,protocol in jobs:
        pair_id = secrets.token_hex(12)
        candidate_side = rng.choice(("A","B"))
        audio_hashes = {}
        for side in ("A","B"):
            is_candidate = side == candidate_side
            voice = row["candidate_id"] if is_candidate else row["legacy_id"]
            pcm,metrics = synthesize(client,key,voice,protocol if is_candidate else "flash",text)
            if metrics["integrity_failures"]:
                raise ValueError("invalid listening sample")
            filename = pair_id+"-"+side+".wav"
            with wave.open(str(public_dir/filename),"wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(RATE)
                out.writeframes(pcm)
            audio_hashes[side] = hashlib.sha256((public_dir/filename).read_bytes()).hexdigest()
        public.append({"pair_id":pair_id,"scenario":fixture,"reference":text,
                       "A":pair_id+"-A.wav","B":pair_id+"-B.wav","audio_sha256":audio_hashes})
        private.append({"pair_id":pair_id,"candidate_side":candidate_side,"candidate_id":row["candidate_id"],
                        "legacy_id":row["legacy_id"],"protocol":protocol,"fixture":fixture,
                        "audio_sha256":audio_hashes})
    pack = {"version":VERSION,"pairs":public,"dimensions":list(DIMENSIONS),"choices":list(CHOICES)}
    pack_hash = digest(pack)
    write_json(public_dir/"listening.json",pack)
    write_json(public_dir/"review-template.json",{"pack_hash":pack_hash,"reviewer_id":"",
        "ratings":[{"pair_id":p["pair_id"],"choices":{d:"" for d in DIMENSIONS}} for p in public]})
    write_json(private_dir/"key.json",{"version":VERSION,"source_sha":sha,"pack_hash":pack_hash,
        "pairs":private,"proposal_hash":digest(proposal)})
    return pack_hash

def evaluate(proposal,sha,pack,key,reviews,authorized_reviewers):
    candidate_ids(proposal,sha)
    if (key.get("source_sha") != sha or key.get("proposal_hash") != digest(proposal)
        or key.get("pack_hash") != digest(pack) or key.get("version") != VERSION
        or pack.get("version") != VERSION):
        raise ValueError("review identity mismatch")
    expected = {(r["candidate_id"],r["legacy_id"],f,p) for r in proposal["mapping"] if r.get("candidate_id")
                for f,_ in FIXTURES for p in PROTOCOLS}
    pairs = key["pairs"]
    if len(pairs)!=len(expected) or {(p["candidate_id"],p["legacy_id"],p["fixture"],p["protocol"]) for p in pairs}!=expected:
        raise ValueError("incomplete listening coverage")
    ids = {p["pair_id"] for p in pairs}
    public = {p["pair_id"]:p for p in pack["pairs"]}
    if len(ids)!=len(pairs) or len(public)!=len(pack["pairs"]) or set(public)!=ids or any(
        p["candidate_side"] not in ("A","B") or public[p["pair_id"]]["audio_sha256"]!=p["audio_sha256"]
        for p in pairs):
        raise ValueError("invalid pair binding")
    seen = set()
    votes = {pid:{d:[] for d in DIMENSIONS} for pid in ids}
    for review in reviews:
        rid = review["reviewer_id"]
        if not rid or rid not in authorized_reviewers or rid in seen or review["pack_hash"]!=digest(pack):
            raise ValueError("invalid or duplicate reviewer")
        seen.add(rid)
        ratings = review["ratings"]
        if len(ratings)!=len(ids) or {r["pair_id"] for r in ratings}!=ids:
            raise ValueError("incomplete reviewer coverage")
        for rating in ratings:
            choices = rating["choices"]
            if set(choices)!=set(DIMENSIONS) or any(v not in CHOICES for v in choices.values()):
                raise ValueError("invalid rating")
            for d in DIMENSIONS:
                votes[rating["pair_id"]][d].append(choices[d])
    results = {}
    for pair in pairs:
        voice = pair["candidate_id"]
        result = results.setdefault(voice,{"status":"PASS","pairs":[]})
        dimensions = {}
        for d,choices in votes[pair["pair_id"]].items():
            n = len(choices)
            win = choices.count(pair["candidate_side"])
            tie = choices.count("equal")
            loss = n-win-tie
            agreements = list(itertools.combinations(choices,2))
            agreement = sum(a==b for a,b in agreements)/len(agreements) if agreements else None
            # Conservative initial policy: no reviewer rates a candidate worse;
            # at least two thirds agree exactly; superiority must be demonstrated
            # on naturalness or emotion for each protocol across its fixtures.
            status = "NOT RUN" if n<MIN_REVIEWERS else (
                "FAIL" if loss else "DISAGREEMENT" if agreement<2/3 else "PASS")
            dimensions[d] = {"wins":win,"ties":tie,"losses":loss,"agreement":agreement,"status":status}
        result["pairs"].append({"fixture":pair["fixture"],"protocol":pair["protocol"],"dimensions":dimensions})
    for result in results.values():
        statuses = [v["status"] for p in result["pairs"] for v in p["dimensions"].values()]
        superior = all(any(p["protocol"]==protocol and any(p["dimensions"][d]["wins"]>p["dimensions"][d]["ties"]
                    for d in ("naturalness","emotion_appropriateness")) for p in result["pairs"]) for protocol in PROTOCOLS)
        result["status"] = "FAIL" if "FAIL" in statuses else "NOT RUN" if "NOT RUN" in statuses else (
            "BLOCKED" if "DISAGREEMENT" in statuses or not superior else "PASS")
        result["superiority_demonstrated"] = superior
    return {"version":VERSION,"source_sha":sha,"proposal_hash":digest(proposal),"pack_hash":digest(pack),
            "reviewer_count":len(seen),"rows":results,"activation_authorized":False}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    gen=sub.add_parser("generate")
    score=sub.add_parser("score")
    for cmd in (gen,score):
        cmd.add_argument("--proposal",type=Path,required=True)
    gen.add_argument("--public-dir",type=Path,required=True)
    gen.add_argument("--private-dir",type=Path,required=True)
    for name in ("pack","key","reviewers","output"):
        score.add_argument("--"+name,type=Path,required=True)
    score.add_argument("--review",type=Path,action="append",default=[])
    args=parser.parse_args()
    sha=os.environ["GITHUB_SHA"]
    proposal=json.loads(args.proposal.read_text())
    if args.command=="generate":
        import httpx
        with httpx.Client(timeout=15,follow_redirects=False) as client:
            generate(proposal,sha,os.environ["ELEVENLABS_API_KEY"],args.public_dir,args.private_dir,client)
    else:
        pack=json.loads(args.pack.read_text())
        key=json.loads(args.key.read_text())
        for p in pack["pairs"]:
            for side in ("A","B"):
                filename=p["pair_id"]+"-"+side+".wav"
                if p[side]!=filename or hashlib.sha256((args.pack.parent/filename).read_bytes()).hexdigest()!=p["audio_sha256"][side]:
                    raise ValueError("audio sample hash mismatch")
        result=evaluate(proposal,sha,pack,key,[json.loads(p.read_text()) for p in args.review],
                        set(json.loads(args.reviewers.read_text())))
        write_json(args.output,result)
        return 0 if all(r["status"]=="PASS" for r in result["rows"].values()) else 1
    return 0

if __name__=="__main__":
    raise SystemExit(main())
