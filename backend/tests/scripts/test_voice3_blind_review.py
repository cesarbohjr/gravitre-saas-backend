import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"scripts"))
import voice3_blind_review as m

def fixture():
    proposal={"source_sha":"head","activation_authorized":False,"mapping":[{"candidate_id":"A"*20,"legacy_id":"B"*20}]}
    pairs=[{"pair_id":str(i),"candidate_side":"A","candidate_id":"A"*20,"legacy_id":"B"*20,
            "fixture":f,"protocol":p,"audio_sha256":{"A":"x","B":"y"}}
           for i,(f,p) in enumerate((f,p) for f,_ in m.FIXTURES for p in m.PROTOCOLS)]
    pack={"version":m.VERSION,"pairs":[{"pair_id":p["pair_id"],"audio_sha256":p["audio_sha256"]} for p in pairs]}
    key={"version":m.VERSION,"source_sha":"head","proposal_hash":m.digest(proposal),"pack_hash":m.digest(pack),"pairs":pairs}
    reviews=[{"reviewer_id":str(i),"pack_hash":m.digest(pack),"ratings":[{"pair_id":p["pair_id"],"choices":dict.fromkeys(m.DIMENSIONS,"A")} for p in pairs]} for i in range(3)]
    return proposal,pack,key,reviews

def score(p,pack,key,reviews):
    return m.evaluate(p,"head",pack,key,reviews,{"0","1","2"})["rows"]["A"*20]["status"]

def test_superiority_requires_complete_independent_reviews():
    p,pack,key,reviews=fixture()
    assert score(p,pack,key,reviews)=="PASS"
    assert score(p,pack,key,reviews[:2])=="NOT RUN"
    with pytest.raises(ValueError):
        score(p,pack,key,[reviews[0]]*3)

def test_inferior_candidate_rejected():
    p,pack,key,reviews=fixture()
    reviews[0]["ratings"][0]["choices"]["naturalness"]="B"
    assert score(p,pack,key,reviews)=="FAIL"

def test_ties_do_not_demonstrate_superiority():
    p,pack,key,reviews=fixture()
    for r in reviews:
        for rating in r["ratings"]:
            rating["choices"]=dict.fromkeys(m.DIMENSIONS,"equal")
    assert score(p,pack,key,reviews)=="BLOCKED"

def test_disagreement_blocks():
    p,pack,key,reviews=fixture()
    reviews[0]["ratings"][0]["choices"]["naturalness"]="equal"
    assert score(p,pack,key,reviews)=="BLOCKED"

def test_stale_key_and_missing_pair_rejected():
    p,pack,key,reviews=fixture()
    with pytest.raises(ValueError):
        score(p,pack,{**key,"source_sha":"old"},reviews)
    with pytest.raises(ValueError):
        score(p,pack,{**key,"pairs":key["pairs"][:-1]},reviews)
