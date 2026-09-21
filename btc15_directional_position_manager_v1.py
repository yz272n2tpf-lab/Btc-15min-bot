from dataclasses import dataclass,asdict
@dataclass(frozen=True)
class PositionView:
 contract:str; action:str; side:object=None; entry_ask:object=None; current_bid:object=None; seconds_left:object=None; source:str="NONE"; reason:str=""; signal_only:bool=True; orders:bool=False
 def to_dict(self): return asdict(self)
def compose_position_view(contract,*,early,final,scalp,position_open=False):
 e=early.normalized();f=final.normalized();s=scalp.normalized()
 if s.state=="EXIT": return PositionView(contract,"EXIT",s.side,s.entry_ask,s.current_bid,s.seconds_left,"SCALP","protected scalp EXIT")
 if s.state=="PROTECT": return PositionView(contract,"PROTECT PROFITS",s.side,s.entry_ask,s.current_bid,s.seconds_left,"SCALP","protected scalp PROTECT")
 if position_open:
  side=e.side if e.state=="QUALIFIED" else (f.side if f.state in {"QUALIFIED","LOCK"} else s.side)
  sec=e.seconds_left if e.state=="QUALIFIED" else (f.seconds_left if f.state in {"QUALIFIED","LOCK"} else s.seconds_left)
  return PositionView(contract,"HOLD",side,None,None,sec,"PROTECTED","position already open")
 if e.state=="QUALIFIED": return PositionView(contract,"BUY",e.side,e.ask,None,e.seconds_left,"EARLY","protected EARLY QUALIFIED")
 if f.state in {"QUALIFIED","LOCK"}: return PositionView(contract,"BUY",f.side,None,None,f.seconds_left,"FINAL","protected FINAL actionable")
 if s.state=="ACTIVE": return PositionView(contract,"BUY",s.side,s.entry_ask,s.current_bid,s.seconds_left,"SCALP","protected SCALP ACTIVE")
 return PositionView(contract,"WAIT",reason="no protected actionable state")
