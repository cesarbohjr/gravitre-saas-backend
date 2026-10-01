from app.plays.impact import play_impact_summary

class R:
    def __init__(self, data): self.data=data
class Q:
    def __init__(self, rows): self.rows=rows
    def select(self,*a,**k): return self
    def eq(self,k,v): self.rows=[r for r in self.rows if str(r.get(k))==str(v)]; return self
    def order(self,*a,**k): return self
    def limit(self,*a,**k): return self
    def execute(self): return R(self.rows)
class C:
    def __init__(self,rows): self.rows=rows
    def table(self,name): assert name=="intelligence_outcome_events"; return Q(list(self.rows))

def row(state, delta=None):
    return {"id":state,"org_id":"o","outcome_event":"play_business_result","created_at":"2026-09-30","metadata":{"play_key":"customer-rescue","verification_state":state,"metric_key":"revenue_protected","delta_value":delta,"unit":"currency","currency":"CAD"}}

def test_only_verified_success_contributes_to_impact_totals():
    out=play_impact_summary(C([row("ACTIONED",5000),row("PENDING VERIFICATION",6000),row("VERIFIED SUCCESS",7000)]),"o")
    assert out["verifiedResultCount"]==1
    assert out["pendingVerificationCount"]==1
    assert out["verifiedMetrics"][0]["value"]==7000
