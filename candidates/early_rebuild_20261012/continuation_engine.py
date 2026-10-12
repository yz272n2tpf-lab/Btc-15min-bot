"""Continuation selection layered on unchanged onset, origin and protection logic."""
from copy import deepcopy
from .engine import Engine
from .assessment import Rules,SAFETY
from .continuation import TARGET,causal_vector
from .resale import digest
from .underlying_history import UnderlyingHistory


def common_eligibility(a,s):
    reasons=list(a.get('recognition_blockers',[]))+list(a.get('execution_blockers',[]))
    if not s or not s.get('confirmed'):reasons.append('CONFIRMATION_LOST')
    if not .25<=a.get('ask',1)<=.55:reasons.append('PRIMARY_PRICE_WINDOW_LOST')
    return dict(eligible=not reasons,setup_id=s['id'] if s else None,reasons=reasons)


class ContinuationEngine(Engine):
    def __init__(self,estimator=None,*,underlying_history=None):
        super().__init__()  # Frozen Rules and unchanged Management. No fixture authority.
        self.continuation_estimator=estimator;self.landmarks=[];self.latest_scores={}
        self.last_landmark={};self.attempted=set();self.research_attempts=[]
        if underlying_history is not None and (not isinstance(underlying_history,UnderlyingHistory) or underlying_history.allow_observation_proxy):
            raise ValueError('NATIVE_OR_FIXTURE_UNDERLYING_INTERFACE_REQUIRED')
        self.underlying_history=deepcopy(underlying_history)

    def ingest_underlying(self,observation,now):
        if self.clock is not None and (not isinstance(now,(int,float)) or now<self.clock):
            raise ValueError('UNDERLYING_INGEST_BEFORE_ENGINE_CLOCK')
        if self.underlying_history is None:self.underlying_history=UnderlyingHistory()
        try:return self.underlying_history.ingest(observation,now)
        except ValueError:
            self.latest_scores.clear()
            for a in self.last_assessments.values():
                a['economics'].update(ready=False,diagnostic_selected=False,status='UNDERLYING_HISTORY_UNAVAILABLE')
            raise

    def continuation_context(self,side):
        """Availability only, even before new-contract onset/confirmation completes."""
        if not self.last:raise ValueError('CURRENT_CONTRACT_OBSERVATION_REQUIRED')
        if self.clock is None or self.clock>=self.last['time']+self.rules.max_age:
            raise ValueError('CURRENT_CONTRACT_SOURCE_EXPIRED')
        snapshot=self.underlying_history.snapshot() if self.underlying_history is not None else None
        if snapshot is not None:
            # A tick cannot keep an old component fresh until the next publication.
            snapshot.rows_at(dict(self.last,received=self.clock))
        return causal_vector(self.history,self.last,side,underlying_history=snapshot)

    def assess_entry_objective(self,r,side,a,s):
        empty=dict(**SAFETY,target=TARGET,ready=False,status='UNESTIMATED',probability=None,
            diagnostic_selected=False,reasons=['CONTINUATION_NOT_SUPPORTED','NO_LIVE_AUTHORITY'])
        common=common_eligibility(a,s)
        if not common['eligible']:self.latest_scores.pop(side,None);return empty
        sid=s['id'];now=r['received'];last=self.last_landmark.get(sid)
        snapshot=self.underlying_history.snapshot() if self.underlying_history is not None else None
        if snapshot is not None:
            try:snapshot.rows_at(r)
            except ValueError as exc:
                self.latest_scores.pop(side,None);empty['reasons'].append(str(exc))
        if last is not None and now-last<10:
            cached=self.latest_scores.get(side)
            if cached and now<cached['expires_at']:
                result=deepcopy(cached);result['cached_score']=True;return result
            return empty
        self.last_landmark[sid]=now
        x=a['features'];record=dict(id=digest([sid,'CONTINUATION',r['publication_id']]),setup_id=sid,
            contract=r['contract'],side=side,decision_time=now,source_time=r['time'],
            publication_id=r['publication_id'],context=x['context'],features=None,feature_error=None)
        record['feature_history_schema']='INDEPENDENT_UNDERLYING_HISTORY_V1' if snapshot is not None else 'LEGACY_SAME_CONTRACT_ROWS'
        try:record['features']=causal_vector(self.history,r,side,underlying_history=snapshot)
        except ValueError as exc:record['feature_error']=str(exc)
        score=(self.continuation_estimator.infer(r,side,self.history,x['context'],underlying_history=snapshot)
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
