"""Continuation selection layered on unchanged onset, origin and protection logic."""
from copy import deepcopy
from .engine import Engine
from .assessment import Rules,SAFETY
from .continuation import TARGET,causal_vector
from .resale import digest


def common_eligibility(a,s):
    reasons=list(a.get('recognition_blockers',[]))+list(a.get('execution_blockers',[]))
    if not s or not s.get('confirmed'):reasons.append('CONFIRMATION_LOST')
    if not .25<=a.get('ask',1)<=.55:reasons.append('PRIMARY_PRICE_WINDOW_LOST')
    return dict(eligible=not reasons,setup_id=s['id'] if s else None,reasons=reasons)


class ContinuationEngine(Engine):
    def __init__(self,estimator=None):
        super().__init__()  # Frozen Rules and unchanged Management. No fixture authority.
        self.continuation_estimator=estimator;self.landmarks=[];self.latest_scores={}
        self.last_landmark={};self.attempted=set();self.research_attempts=[]

    def assess_entry_objective(self,r,side,a,s):
        empty=dict(**SAFETY,target=TARGET,ready=False,status='UNESTIMATED',probability=None,
            diagnostic_selected=False,reasons=['CONTINUATION_NOT_SUPPORTED','NO_LIVE_AUTHORITY'])
        common=common_eligibility(a,s)
        if not common['eligible']:self.latest_scores.pop(side,None);return empty
        sid=s['id'];now=r['received'];last=self.last_landmark.get(sid)
        if last is not None and now-last<10:
            cached=self.latest_scores.get(side)
            if cached and now<cached['expires_at']:
                result=deepcopy(cached);result['cached_score']=True;return result
            return empty
        self.last_landmark[sid]=now
        x=a['features'];record=dict(id=digest([sid,'CONTINUATION',r['publication_id']]),setup_id=sid,
            contract=r['contract'],side=side,decision_time=now,source_time=r['time'],
            publication_id=r['publication_id'],context=x['context'],features=None,feature_error=None)
        try:record['features']=causal_vector(self.history,r,side)
        except ValueError as exc:record['feature_error']=str(exc)
        score=(self.continuation_estimator.infer(r,side,self.history,x['context'])
               if self.continuation_estimator else deepcopy(empty))
        score.update(score_time=now,expires_at=min(now+10,r['time']+10,self.close),cached_score=False)
        record['score']=deepcopy(score);self.landmarks.append(record);self.latest_scores[side]=score
        if score['diagnostic_selected'] and sid not in self.attempted:
            self.attempted.add(sid)
            self.research_attempts.append(dict(**SAFETY,landmark_id=record['id'],setup_id=sid,
                issued_at=now,expires_at=score['expires_at'],contract=r['contract'],side=side,
                status='EXPLORATORY_PROPOSAL_NOT_BUY_AUTHORITY'))
            self.emit('CONTINUATION_EXPLORATORY_PROPOSAL',now,landmark=record)
        return score

    def tick(self,now):
        result=super().tick(now)
        if not hasattr(self,'latest_scores'):return result
        for side,score in list(self.latest_scores.items()):
            if isinstance(now,(int,float)) and now>=score['expires_at']:
                self.latest_scores.pop(side,None)
                if side in self.last_assessments:
                    econ=self.last_assessments[side]['economics']
                    econ.update(diagnostic_selected=False,status='EXPIRED_CONTINUATION_SCORE',ready=False)
        return self.output(result['reasons'])
