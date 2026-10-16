"""Live schemas atop the preserved independent SQLite reader and book replay.

Recorded receipt/acceptance cutoffs are never inferred from an exchange clock.
Retain only current expanded vectors and compact verified proofs, avoiding
quadratic full-proof histories; original vector deltas stay in immutable raw.
"""
import base64,json,sqlite3,time
from decimal import Decimal
from pathlib import Path
from ops.recording_workflow.whole_run import Verifier,LIMITS,require,timestamp,number
from ops.recording_workflow.lifecycle import rows,ref,source,metadata,frame_links,verify_proof,one
from .policy import PROFILES,canonical,sha,file_sha

def budgets(profile):
 p=PROFILES[profile];return dict(LIMITS,decoded_bytes=p['decoded'],compressed_bytes=sum(p['compressed'].values()),records=p['records'],work_db_bytes=p['db'],index_bytes=p['index'],ledger_bytes=512*1024**2,seconds=p['reader_seconds'])

class CampaignVerifier(Verifier):
 def __init__(self,*a,**kw):
  super().__init__(*a,**kw);self.current_vectors={};self.lifecycle={};self.pending={};self.source_scope={};self.outcome_status={};self.contracts={}
  self.db.executescript('''CREATE TABLE response(h TEXT,at REAL,endpoint TEXT,s TEXT,q INTEGER,p INTEGER,v BLOB);CREATE INDEX response_hash ON response(h,at);
   CREATE TABLE candles(h TEXT,at REAL,s TEXT,q INTEGER,p INTEGER,v BLOB,original_http INTEGER);CREATE INDEX candle_hash ON candles(h,at);
   CREATE TABLE candle_raw(h TEXT,at REAL,s TEXT,q INTEGER,p INTEGER);CREATE INDEX candle_raw_hash ON candle_raw(h,at);
   CREATE TABLE live_inputs(h TEXT,at REAL,s TEXT,q INTEGER,p INTEGER,v BLOB,attempt TEXT);CREATE INDEX live_input_hash ON live_inputs(h,attempt,at);
   CREATE TABLE brti_reads(h TEXT,at REAL,s TEXT,q INTEGER,p INTEGER,v BLOB,original_sha TEXT);CREATE INDEX brti_read_hash ON brti_reads(original_sha,at);
   CREATE TABLE official(ticker TEXT,opened REAL,closed REAL,target REAL,at REAL,s TEXT,q INTEGER,p INTEGER);CREATE INDEX official_identity ON official(ticker,opened,closed,target,at);
   CREATE TABLE book_quotes(epoch TEXT,ticker TEXT,market TEXT,sid INTEGER,seq INTEGER,ts INTEGER,at REAL,s TEXT,q INTEGER,p INTEGER,quotes BLOB);CREATE INDEX book_exact ON book_quotes(epoch,ticker,market,sid,seq,ts);
   CREATE INDEX native_attempt ON facts(t,json_extract(v,'$.native.product.attempt_id'));
   CREATE INDEX native_origin ON facts(t,json_extract(v,'$.native.origin_id'));
   CREATE INDEX native_cut ON facts(t,json_extract(v,'$.native.evidence.captured_ts'));
   CREATE INDEX response_btc ON response(json_extract(v,'$.time'),at);
   CREATE INDEX journal_sequence ON journals(seq);
  ''')
 def unresolved(self,s,t,id,q,p):
  # Recorder stop is not a websocket disconnect. Preserve the open-stream tail.
  if t=='stream':self.metrics['streams_open_at_recording_stop']+=1;return
  z=self.dep(s,t,id);blob=self.dep(s,'QUOTE_BYTES',z['raw_sha256']);event=json.loads(base64.b64decode(blob['raw_base64']))
  if event.get('type') not in ('orderbook_snapshot','orderbook_delta'):self.metrics['protocol_messages_not_depth']+=1
  else:self.issue('QUOTE_RECEIVED_WITHOUT_OWNER_ACCEPTANCE',session=s,sequence=q)
 def record(self,r):
  k=r['kind'];v=r['payload'];s,q,p=r['session'],r['sequence'],r['_part']
  if k in ('RECORDING_BOUNDARY','RECORDING_HEALTH'):
   self.fact(k,s,r,v);return
  if k=='INFORMATION_FAILURE' and v.get('reason') in ('INPUT_NOT_PUBLISHED','PUBLISHER_EXCEPTION'):
   self.metrics['information_not_published']+=1;self.fact('native_information_unavailable',s,r,v);return
  if k=='QUOTE_REQUEST':
   raw=self.dep(s,'QUOTE_BYTES',v['raw_sha256'],q,p);request=json.loads(base64.b64decode(raw['raw_base64']))
   require(number(v['sent_at']),'QUOTE_SEND_TIME');self.put(s,'request',canonical([v['epoch'],request['id']]).decode(),q,p,dict(v,request=request));return
  if k=='QUOTE_ACCEPT':
   blob=self.dep(s,'QUOTE_BYTES',v['raw_sha256'],q,p);event=json.loads(base64.b64decode(blob['raw_base64']))
   key=sha(canonical([v['epoch'],v['ticker']]));old=self.db.execute('SELECT v FROM deps WHERE s=? AND t="book" AND id=?',(s,key)).fetchone()
   rebasing=old and event.get('type')=='orderbook_snapshot' and event!=json.loads(old[0])['last']
   if rebasing or event.get('type')=='ok':
    request=self.dep(s,'request',canonical([v['epoch'],event.get('id')]).decode(),q,p)
    require(request['sent_at']<=v['received_at']<=v['accepted_at'],'REQUEST_RECEIVE_ACCEPT_ORDER')
    cmd=request['request'];require(cmd['cmd']=='update_subscription' and cmd['params']['action']=='get_snapshot' and cmd['params']['market_tickers']==[v['ticker']],'ORIGINAL_SNAPSHOT_REQUEST')
    if rebasing:
     z=json.loads(old[0]);require(event['sid']==z['sid']==cmd['params']['sid'] and event['seq']==z['seq']+1 and event['msg']['market_id']==z['market_id'],'SNAPSHOT_REBASE_CONTINUITY')
     self.db.execute('DELETE FROM deps WHERE s=? AND t="book" AND id=?',(s,key));self.metrics['verified_snapshot_rebases']+=1
    elif 'seq' not in event and 'sid' not in event:
     id=sha(canonical([v['epoch'],v['ticker'],v['raw_sha256'],v['received_at']]))
     self.dep(s,'receive',id,q,p);self.put(s,'accepted_receive',id,q,p,v);self.metrics['unsequenced_snapshot_acknowledgements']+=1;return
  if k in ('ORIGINAL_RESPONSE','CANDLE_ACCEPTANCE','V81_INPUT','BRTI_READ','OUTCOME_ACCEPTANCE','CLOSEOUT_ACCEPTANCE','NATIVE_FRAME'):
   raw=base64.b64decode(v['raw_base64'],validate=True) if k=='ORIGINAL_RESPONSE' else v['raw'].encode();require(sha(raw)==v['sha256'],'LIVE_RAW_HASH')
   try:z=json.loads(raw)
   except (ValueError,UnicodeDecodeError):
    require(k=='ORIGINAL_RESPONSE','DOCUMENT_NOT_JSON');self.metrics['original_non_json_http_responses']+=1;self.fact('original_non_json_response',v['sha256'],r,v);return
   if k=='ORIGINAL_RESPONSE':
    require(number(v['received_at']),'RESPONSE_RECEIPT');self.db.execute('INSERT INTO response VALUES (?,?,?,?,?,?,?)',(v['sha256'],v['received_at'],v['endpoint'],s,q,p,raw))
    if v['endpoint'].endswith('/candles'):
     require(isinstance(z,list) and len(z)<=1000,'CANDLE_RESPONSE_SCHEMA')
     for row in z:
      require(len(row)==6,'COINBASE_CANDLE_SCHEMA');st,lo,hi,op,cl,vol=row
      self.db.execute('INSERT INTO candle_raw VALUES (?,?,?,?,?)',(sha(canonical([float(x) for x in (st,op,hi,lo,cl,vol)])),v['received_at'],s,q,p))
   elif k=='CANDLE_ACCEPTANCE':
    require(number(v['accepted_at']) and isinstance(z,list) and len(z)<=256,'CANDLE_ACCEPTANCE_SCHEMA')
    for row in z:
     require(len(row)==7 and row[0]==row[1]+60,'COMPLETED_CANDLE_END_CLOCK')
     candidates=self.db.execute('SELECT s,q,p FROM candle_raw WHERE h=? AND at<=?',(sha(canonical(row[1:])),v['accepted_at'])).fetchall()
     self.db.execute('INSERT INTO candles VALUES (?,?,?,?,?,?,?)',(sha(canonical(row)),v['accepted_at'],s,q,p,canonical(row),int(bool(candidates))))
     self.metrics['original_completed_candles' if candidates else 'completed_cache_rows_upstream_receipt_unknown']+=1
   elif k=='BRTI_READ':
    require(number(v['received_at']) and z.get('owner_epoch') and type(z.get('sequence')) is int,'BRTI_ORIGINAL_IDENTITY')
    key={x:z.get(x) for x in ('value','source_ts_ms','owner_epoch','sequence','status','clean_for_qualification')}
    self.db.execute('INSERT INTO brti_reads VALUES (?,?,?,?,?,?,?)',(sha(canonical(key)),v['received_at'],s,q,p,raw,v['sha256']))
   elif k=='V81_INPUT':
    require(z['input_provenance']['schema']=='V81_TIMESTAMPED_INPUTS_V1' and z['ts']<=v['accepted_at'],'V81_ACCEPTANCE_SCHEMA')
    self.db.execute('INSERT INTO live_inputs VALUES (?,?,?,?,?,?,?)',(sha(canonical(z['input_provenance'])),v['accepted_at'],s,q,p,canonical(dict(row=z,receipts={key:v[key] for key in ('btc_response_sha256','btc_received_at','brti_observation_sha256','brti_received_at')})),v['attempt_id']))
   else:self.fact(k,v['sha256'],r,dict(v,value=z))
   return
  super().record(r)
  if k=='HTTP_RESPONSE':
   data=self.db.execute('SELECT v FROM facts WHERE t="metadata" AND s=? AND q=?',(s,q)).fetchone()
   if data:
    m=json.loads(data[0])['market']
    if number(m.get('floor_strike')):self.db.execute('INSERT INTO official VALUES (?,?,?,?,?,?,?,?)',(m['ticker'],timestamp(m['open_time']),timestamp(m['close_time']),m['floor_strike'],v['received_at'],s,q,p))
  if k=='VECTOR':
   self.current_vectors[(s,v['name'])]=v['id']
   keep=[h for (session,_),h in self.current_vectors.items() if session==s]
   self.db.execute('DELETE FROM deps WHERE s=? AND t="vector" AND id NOT IN ('+','.join('?' for _ in keep)+')',[s,*keep])
  if k=='QUOTE_ACCEPT':
   key=sha(canonical([v['epoch'],v['ticker']]));z=self.dep(s,'book',key)
   # Same replayed book, pure displayed prices. No fill or execution inference.
   levels={side:{Decimal(a):Decimal(b) for a,b in values} for side,values in z['levels'].items()}
   if levels['yes'] and levels['no']:
    up=max(levels['yes']);dn=max(levels['no']);quotes=[float(up),float(1-dn),float(dn),float(1-up)]
    self.db.execute('INSERT INTO book_quotes VALUES (?,?,?,?,?,?,?,?,?,?,?)',(v['epoch'],v['ticker'],z['market_id'],z['sid'],z['seq'],z['ts_ms'],v['accepted_at'],s,q,p,canonical(quotes)))
  if k=='QUOTE_PROOF':
   z=json.loads(self.db.execute('SELECT v FROM facts WHERE t=? AND s=? AND q=?',(k,s,q)).fetchone()[0])
   try:verify_proof(self,(s,q,p),z)
   except Exception as e:self.issue('PROOF_ASSOCIATION',record=ref((s,q,p)),detail=str(e))
   self.db.execute('DELETE FROM facts WHERE t=? AND s=? AND q=?',(k,s,q))
  if k=='INFORMATION_INPUT':
   z=json.loads(self.db.execute('SELECT v FROM facts WHERE t=? AND s=? AND q=?',(k,s,q)).fetchone()[0])
   try:self.information((s,q,p),z)
   except Exception as e:self.issue('INFORMATION_ASSOCIATION',record=ref((s,q,p)),detail=str(e))
   self.db.execute('DELETE FROM facts WHERE t=? AND s=? AND q=?',(k,s,q))
 def information(self,loc,z):
  f=z['value'];a=f['anchor'];cut=f['cut'];b=f['brti'];proof=f['proof']
  require(f['anchor_id']==sha(canonical(a)),'ANCHOR_HASH');require(a['opened']<=a['decision']<=a['captured']<=cut<a['closed'],'INFORMATION_CUTOFF')
  for row in a['completed']:
   require(self.db.execute('SELECT 1 FROM candles WHERE h=? AND at<=? AND original_http=1 LIMIT 1',(sha(canonical(row)),a['decision'])).fetchone(),'CANDLE_NOT_AVAILABLE_WITH_ORIGINAL_HTTP_AT_DECISION')
  require(0<len(a['ticks'])<=4096,'TICK_HISTORY_BOUND')
  for st,rt,val in a['ticks']:source(self,'BTC',st,rt,val,None,a['decision'],loc[2])
  require(a['ticks'][-1]==[a['btc']['source'],a['btc']['received'],a['btc']['value']],'LAST_ANCHOR_TICK')
  links=dict(BRTI=source(self,'BRTI',b['source'],b['received'],b['value'],b['epoch'],cut,loc[2]),metadata=metadata(self,a['ticker'],a['opened'],a['closed'],a['target'],cut,loc[2]))
  w=dict(ticker=proof['ticker'],epoch=proof['epoch'],source_time=proof['source_time'],consumed_ms=proof['consumed_ms'],close_ms=int(a['closed']*1000),**dict(zip(('market_id','sid','seq','exchange_ts_ms'),proof['identity'])))
  raw=json.dumps({x:proof[x] for x in ('source_time','ticker','epoch','consumed_ms','identity','events')},separators=(',',':'),allow_nan=False).encode()
  verify_proof(self,loc,dict(value=proof,witness=w,proof_sha256=sha(raw)))
  require(proof['consumed_ms']/1000<=f['quote_received']<=cut,'INFO_PROOF_CUTOFF')
  self.emit(self.fassoc,dict(record=ref(loc),status='VERIFIED_INDEPENDENT_INFORMATION',input_sha256=z['input_sha256'],links=links,completed_candles=len(a['completed']),ticks=len(a['ticks']),native_consumption='NOT_CLAIMED'))
  self.metrics['information_associations']+=1
 def fast_metadata(self,ticker,opened,closed,target,cut,part):
  args=(ticker,opened,closed,target,cut);where='ticker=? AND opened=? AND closed=? AND target=? AND at<=?'
  row=self.db.execute('SELECT s,q,p FROM official WHERE '+where+' ORDER BY at LIMIT 1',args).fetchone();require(row,'MISSING_EXACT_METADATA')
  n=self.db.execute('SELECT count(*) FROM official WHERE '+where,args).fetchone()[0]
  if row[2]!=part:self.metrics['cross_partition_associations']+=1
  return dict(ref(row),equivalent_observations=n,basis='EXACT_OFFICIAL_IDENTITY_TUPLE_NOT_CONSUMED_HTTP_HASH')
 def expectations(self):
  scope=json.loads((self.root/'campaign-scope.json').read_bytes());self.scope=scope
  require(scope['schema']=='BTC15_CAMPAIGN_SCOPE_V1','CAMPAIGN_SCOPE')
  expected={e['session']:e for e in scope['seals']}
  require(len(expected)==len(scope['seals'])==3 and {e['role'] for e in scope['seals']}=={'main','v81','information'},'ALL_ROLES_REQUIRED')
  require(set(expected)=={x[0] for x in self.db.execute('SELECT s FROM sessions')},'EXACT_CAMPAIGN_SESSION_SET')
  for s,e in expected.items():
   got=self.db.execute('SELECT n,h,class FROM sessions WHERE s=?',(s,)).fetchone();expected_class='FIXTURE' if e['identity']['mode']=='OFFLINE_FIXTURE' else 'NATIVE_CAPTURE';require(got==(e['last_sequence'],e['last_sha256'],expected_class),'ROLE_SEAL_CHAIN_OR_CLASS')
   require(e['run_id']==scope['run_id'] and e['status']=='SEALED','ROLE_RUN_OR_INCOMPLETE')
   binding=json.loads(self.db.execute('SELECT v FROM facts WHERE t="session" AND id=?',(s,)).fetchone()[0])['binding']
   require(binding==scope['run_id']+':'+e['role'],'ROLE_SOURCE_BINDING')
   for jid,j in e['journals'].items():
    actual=self.db.execute('SELECT min(seq),max(seq),count(*) FROM journals WHERE id=?',(jid,)).fetchone()
    require(actual==(j['first'],j['last'],j['attempted']) and j['attempted']==j['accepted']==j['last']-j['first']+1,'ORIGINAL_JOURNAL_MIRROR_RANGE')
    self.metrics['original_journal_records_verified']+=j['accepted']
  for asset in ('BTC','BRTI'):
   first=prior=None;max_gap=0;n=0
   for at, in self.db.execute('SELECT DISTINCT available FROM sources WHERE asset=? AND basis="ORIGINAL" AND accepted=1 ORDER BY available',(asset,)):
    first=at if first is None else first
    if prior is not None:max_gap=max(max_gap,at-prior)
    prior=at;n+=1
   self.source_scope[asset]=dict(first=first,last=prior,count=n,max_gap=max_gap)
   if n<2 or max_gap>15:self.issue('SOURCE_COVERAGE',asset=asset,**self.source_scope[asset])
  return scope
 def associate(self,scope):
  # Producer journal ranges above prove only the declared recording interval.
  for identity,n in self.db.execute('SELECT id,count(*) FROM facts WHERE t="decision" AND json_extract(v,"$.native.unavailable_reason") IS NULL GROUP BY id HAVING count(*)>1'):
   self.issue('DUPLICATE_NATIVE_DECISION_IDENTITY',identity=identity,count=n)
  for loc,z in rows(self,'decision'):
   n=z['native'];f=n['evidence']
   try:
    require(n['contract']==f['contract'] and f['captured_ts']<=n['published_ts']<=z['committed_at'],'NATIVE_CHRONOLOGY')
    if n.get('unavailable_reason'):self.metrics['legitimate_unavailable']+=1;continue
    links=frame_links(self,f,loc[2]);self.native_lifecycle(loc,z,links)
    self.metrics['native_associations']+=1
   except Exception as e:self.issue('NATIVE_ASSOCIATION',record=ref(loc),detail=str(e))
  for loc,z in rows(self,'native_other'):
   try:
    n=z['native'];kind=n.get('kind');schema=n.get('schema','')
    if z['record_basis']=='POST_ADMIN_COMMIT_APPLICATION_CLOCK':self.admin(loc,z)
    elif kind=='SCALP_OBSERVATION':self.scalp(loc,z)
    elif kind in ('SETTLEMENT','BRTI_CLOSEOUT'):self.outcome(loc,z)
    elif kind=='UNAVAILABLE' and n.get('unavailable_reason'):self.metrics['legitimate_unavailable']+=1
    else:raise ValueError('UNSUPPORTED_NATIVE_SCHEMA:'+str(kind)+':'+schema)
   except Exception as e:self.issue('NATIVE_ASSOCIATION',record=ref(loc),detail=str(e))
  if not self.metrics['native_associations']:self.issue('MAIN_APPLICABLE_DECISION_LINKS_MISSING')
  if not self.metrics['scalp_associations']:self.issue('V81_APPLICABLE_DECISION_LINKS_MISSING')
  if not self.metrics['information_associations']:self.issue('INFORMATION_LINKS_MISSING')
  if self.metrics['origins_outside_recorded_journal_interval'] or self.metrics['terminals_outside_recorded_interval']:
   self.issue('MAIN_LIFECYCLE_OUTSIDE_RECORDED_INTERVAL')
 def native_lifecycle(self,loc,z,links):
  n=z['native'];f=n['evidence'];o=n.get('origin');oid=n.get('origin_id');terminal=n.get('terminal');final=n.get('final');management=n.get('management')
  from btc15_ladder_journal_v1 import digest
  require([f[k] for k in ('up_bid','up_ask','down_bid','down_ask')]==list(f['quote']['quotes']),'MAIN_FRAME_QUOTE_PRICES')
  if o:
   require(n.get('event')=='BUY','ORIGIN_WITHOUT_NATIVE_BUY')
   require(o['origin_id']==digest([n['candidate'],o['contract'],[o['native_epoch'],o['native_sequence']],o['side']]),'MAIN_ORIGIN_HASH')
   require(o['origin_id']==oid and o['contract']==n['contract']==f['contract'] and o['side'] in ('UP','DOWN'),'MAIN_ORIGIN_IDENTITY')
   require((o['native_epoch'],o['native_sequence'])==(f['native_epoch'],f['native_sequence']),'MAIN_ORIGIN_NATIVE_CLOCK')
   require(o['entry_provenance']==f,'ORIGIN_SOURCE_FRAME')
   require(number(o.get('original_ask')) and o['original_ask']==f[o['side'].lower()+'_ask'],'MAIN_ORIGIN_SIGNAL_ASK')
  origin=None
  self.contracts[f['contract']]=dict(opened=f['official_open'],closed=f['official_close'],target=f['target'])
  if oid:
   origins=list(self.db.execute('SELECT s,q,p,v FROM facts WHERE t="decision" AND json_extract(v,"$.native.origin.origin_id")=? AND json_extract(v,"$.original_journal")=? AND json_extract(v,"$.native.candidate")=? AND json_extract(v,"$.sequence")<=?',(oid,z['original_journal'],n['candidate'],z['sequence'])))
   if origins:
    require(len(origins)==1,'AMBIGUOUS_NATIVE_ORIGIN');oz=json.loads(origins[0][3]);origin=oz['native']['origin'];require(origin['entry_provenance']['captured_ts']<=f['captured_ts'] and oz['committed_at']<=z['committed_at'] and origin['contract']==f['contract'],'ORIGIN_CHRONOLOGY_OR_CONTRACT');links['origin']=ref(origins[0])
   else:
    # Native may carry a prior deployed origin into the initial recording slot.
    links['origin']=dict(origin_id=oid,status='ORIGINAL_ENTRY_NOT_IN_RECORDED_INTERVAL');self.metrics['origins_outside_recorded_journal_interval']+=1
   require(final and final.get('early_origin_id')==oid,'FINAL_ORIGIN_IDENTITY')
  if final:require(final['publication_id']==digest([n['candidate'],'FINAL',[f['native_epoch'],f['native_sequence']]]),'FINAL_IDENTITY')
  if management:
   require(oid and management.get('state') in ('ENTER','WATCH','HOLD','PROTECT','EXIT'),'MAIN_MANAGEMENT_IDENTITY')
   if management.get('state')=='EXIT':require(terminal is not None,'MAIN_EXIT_WITHOUT_TERMINAL')
   if origin and management.get('economics'):
    economics=management['economics'];side=origin['side'].lower()
    require(economics.get('original_signal_ask')==origin['original_ask'] and economics.get('current_bid')==f[side+'_bid'],'MAIN_MANAGEMENT_PRICE_BINDING')
  if terminal:
   require(terminal['origin_id']==oid and terminal['contract']==f['contract'] and terminal['decision_ts']<=f['captured_ts'],'TERMINAL_IDENTITY')
   require(management and management.get('terminal')==terminal,'TERMINAL_MANAGEMENT')
   require(terminal.get('state')=='EXIT' and management.get('state')=='EXIT','MAIN_TERMINAL_STATE')
   if origin:require(terminal.get('side')==origin['side'] and terminal.get('original_ask')==origin['original_ask'],'MAIN_TERMINAL_ORIGIN_PRICE')
   owners=list(self.db.execute('SELECT s,q,p,v FROM facts WHERE t="decision" AND json_extract(v,"$.native.evidence.captured_ts")=? AND json_extract(v,"$.native.origin_id")=? AND json_extract(v,"$.original_journal")=? AND json_extract(v,"$.native.candidate")=? AND json_extract(v,"$.sequence")<=?',(terminal['decision_ts'],oid,z['original_journal'],n['candidate'],z['sequence'])))
   owners=[x for x in owners if json.loads(x[3])['native']['evidence']['quote']==terminal['quote']]
   if owners:
    require(len(owners)==1,'AMBIGUOUS_TERMINAL_DECISION');owner=json.loads(owners[0][3]);tf=owner['native']['evidence']
    require(owner['committed_at']<=z['committed_at'],'MAIN_TERMINAL_COMMIT_ORDER')
    require(number(terminal.get('executable_exit_bid')) and terminal['executable_exit_bid']>0 and terminal['executable_exit_bid']==tf[terminal['side'].lower()+'_bid'],'MAIN_TERMINAL_EXECUTABLE_BID')
    links['terminal_decision']=ref(owners[0]);self.metrics['terminal_associations']+=1
   else:links['terminal_decision']=dict(status='ORIGINAL_EXIT_DECISION_NOT_IN_RECORDED_INTERVAL');self.metrics['terminals_outside_recorded_interval']+=1
  if o:
   previous=self.db.execute('SELECT s,q,p,v FROM facts WHERE t="decision" AND json_extract(v,"$.original_journal")=? AND json_extract(v,"$.sequence")<? AND json_extract(v,"$.native.contract")=? AND json_extract(v,"$.native.origin_id") IS NOT NULL ORDER BY CAST(json_extract(v,"$.sequence") AS INTEGER) DESC LIMIT 1',(z['original_journal'],z['sequence'],f['contract'])).fetchone()
   if previous and json.loads(previous[3])['native']['origin_id']!=oid:
    links['prior_native_origin']=dict(ref(previous),basis='DERIVED_SAME_JOURNAL_CONTRACT_ORDER; NO_PREDECESSOR_ID_IN_MAIN_SCHEMA');self.metrics['main_reentry_relationships']+=1
  # Retain literal emitted labels; an absent label is not synthesized.
  labels={k:n[k] for k in ('kind','event','origin_id','continuity') if k in n}
  labels.update(final_state=(final or {}).get('state'),management_state=(management or {}).get('state'),terminal_state=(terminal or {}).get('state'))
  for label in (n.get('event'),labels['management_state'],labels['final_state'],labels['terminal_state']):
   if label:self.lifecycle[label]=self.lifecycle.get(label,0)+1
  self.emit(self.fassoc,dict(record=ref(loc),journal_id=z['original_journal'],journal_sequence=z['sequence'],status='VERIFIED_NATIVE_SOURCE_LINKS',links=links,emitted=labels,cutoff=f['feature_cutoff']))
 def admin(self,loc,z):
  n=z['native'];schema=n.get('schema','');require(schema.startswith('BTC15_'),'ADMIN_SCHEMA')
  if schema=='BTC15_PUBLICATION_TIMING_R1':
   seq=n['journal_sequence'];attempt=n.get('attempt_id');lane=n['lane']
   matching=[]
   for jid,s,q,p,data in self.db.execute('SELECT id,s,q,p,v FROM journals WHERE seq=?',(seq,)):
    m=json.loads(data);raw=json.loads(m['raw'])
    if m['record_basis']=='POST_ORIGINAL_COMMIT' and m['lane']==lane and raw.get('product',{}).get('attempt_id')==attempt:matching.append((s,q,p))
   require(len(matching)==1,'ADMIN_NATIVE_EXACT_ASSOCIATION')
   self.emit(self.fassoc,dict(record=ref(loc),status='VERIFIED_ADMIN_ASSOCIATION',native=ref(matching[0]),attempt_id=attempt))
   self.metrics['admin_associations']+=1
  else:self.metrics['admin_records_retained']+=1
 def scalp(self,loc,z):
  n=z['native']
  if n.get('unavailable_reason'):self.metrics['legitimate_unavailable']+=1;return
  p=n['provenance'];key=sha(canonical(p));candidates=list(self.db.execute('SELECT s,q,p,v,at FROM live_inputs WHERE h=? AND attempt=? AND at<=?',(key,n['product']['attempt_id'],n['published_ts'])))
  self.contracts[p['ticker']]=dict(opened=p['open_ts'],closed=p['close_ts'],target=p['target'])
  require(len(candidates)==1,'V81_EXACT_ATTEMPT_ACCEPTANCE_MISSING_OR_AMBIGUOUS')
  # Identical qualified provenance may recur; verify every distinct row/cut explicitly.
  saved=json.loads(candidates[0][3]);row=saved['row'];receipts=saved['receipts'];cut=row['ts'];require(cut<=candidates[0][4]<=n['published_ts']<=z['committed_at'],'SCALP_CUTOFF')
  require(row['ticker']==p['ticker']==n['contract'] and row['target']==p['target'] and row['brti']==p['brti']['value'] and p['close_ts']-p['open_ts']==900 and p['open_ts']<=cut<p['close_ts'],'SCALP_NATIVE_INPUT_IDENTITY')
  require(all(row[k]==p['quote'][k] for k in ('up_bid','up_ask','down_bid','down_ask')),'SCALP_NATIVE_PRICES')
  q=p['quote'];matches=list(self.db.execute('SELECT s,q,p,quotes,at FROM book_quotes WHERE epoch=? AND ticker=? AND market=? AND sid=? AND seq=? AND ts=? AND at<=?',(q['epoch'],q['ticker'],q['market_id'],q['sid'],q['sequence'],q['source_ts_ms'],q['validated_at_ms']/1000)))
  require(matches and all(json.loads(x[3])==[q[k] for k in ('up_bid','up_ask','down_bid','down_ask')] for x in matches),'SCALP_EXACT_ACCEPTED_DEPTH')
  require(q['validated_at_ms']/1000<=cut,'SCALP_QUOTE_CUTOFF')
  require(receipts['btc_received_at']<=cut and receipts['brti_received_at']<=cut,'V81_ORIGINAL_RECEIPT_CUTOFF')
  require(timestamp(p['btc_source_utc'])<=receipts['btc_received_at'] and p['brti']['source_ts_ms']/1000<=receipts['brti_received_at'],'V81_SOURCE_RECEIPT_CHRONOLOGY')
  b=list(self.db.execute('SELECT s,q,p FROM brti_reads WHERE original_sha=? AND at=? AND s=? AND h=?',(receipts['brti_observation_sha256'],receipts['brti_received_at'],candidates[0][0],sha(canonical(p['brti'])))));require(len(b)==1,'SCALP_ORIGINAL_BRTI')
  btc=[]
  for s,rq,rp,raw,at in self.db.execute('SELECT s,q,p,v,at FROM response WHERE h=? AND at=? AND s=? AND endpoint LIKE ?',(receipts['btc_response_sha256'],receipts['btc_received_at'],candidates[0][0],'%/products/BTC-USD/ticker')):
   v=json.loads(raw)
   if v.get('time')==p['btc_source_utc'] and float(v.get('price','nan'))==row['btc']:btc.append((s,rq,rp))
  require(len(btc)==1,'SCALP_ORIGINAL_BTC')
  links=dict(accepted_input=ref(candidates[0]),quote=ref(matches[0]),BRTI=ref(b[0]),BTC=ref(btc[0]),metadata=metadata(self,p['ticker'],p['open_ts'],p['close_ts'],p['target'],cut,loc[2]))
  o=n.get('origin');terminal=n.get('terminal')
  if o:
   from btc15_ladder_journal_v1 import digest
   require(o['origin_id']==digest([n['candidate'],o['contract'],o['side'],o['signal_ts'],o['entry_provenance']['quote']['epoch'],o['entry_provenance']['quote']['sequence']]),'SCALP_ORIGIN_HASH')
   require(o['entry_provenance']==p and o['original_ask']==p['quote'][o['side'].lower()+'_ask'],'SCALP_ORIGIN_PROVENANCE')
   if o.get('predecessor_id'):
    require(n.get('predecessor_exit',{}).get('origin',{}).get('origin_id')==o['predecessor_id'],'REENTRY_PREDECESSOR');self.metrics['scalp_reentry_relationships']+=1
  if terminal:require(terminal['origin']['origin_id']==n['origin_id'] and terminal['ts']<=n['published_ts'],'SCALP_TERMINAL')
  for label in (n.get('event'),n.get('guidance'),(terminal or {}).get('state')):
   if label:self.lifecycle[label]=self.lifecycle.get(label,0)+1
  self.emit(self.fassoc,dict(record=ref(loc),status='VERIFIED_SCALP_LINKS',links=links,event=n.get('event'),guidance=n.get('guidance'),terminal=(terminal or {}).get('state')));self.metrics['scalp_associations']+=1
 def outcome(self,loc,z):
  n=z['native'];kind=n['kind'];out=n['settlement' if kind=='SETTLEMENT' else 'brti_closeout'];contract=n['contract']
  require(number(n.get('published_ts')) and number(z.get('committed_at')) and n['published_ts']<=z['committed_at'],'OUTCOME_PUBLICATION_COMMIT_ORDER')
  self.lifecycle[kind]=self.lifecycle.get(kind,0)+1
  if kind=='SETTLEMENT':
   if out['status']=='UNAVAILABLE':self.pending[contract]=out['status'];return
   match=[(a,b) for a,b in rows(self,'OUTCOME_ACCEPTANCE') if a[0]==loc[0] and a[1]<loc[1] and b['value']==out and out['received_ts']<=b['accepted_at']<=n['published_ts']]
   require(match,'ORIGINAL_OUTCOME_ACCEPTANCE_MISSING');a,b=match[0]
   response=self.db.execute('SELECT v,at FROM response WHERE h=? AND at<=? AND s=? AND q<? AND endpoint=?',(b['response_sha256'],out['received_ts'],a[0],a[1],out['endpoint'])).fetchone();require(response,'ORIGINAL_OUTCOME_RESPONSE_MISSING')
   from btc15_ladder_settlement_v2 import receipt
   require(receipt(contract,out['open_ts'],json.loads(response[0]),out['received_ts'])==out,'OUTCOME_RESPONSE_ACCEPTANCE_MISMATCH')
   if contract in self.contracts:
    identity=self.contracts[contract]
    require((out['open_ts'],out['close_ts'],out['target'])==(identity['opened'],identity['closed'],identity['target']),'OUTCOME_NATIVE_CONTRACT_IDENTITY')
   self.outcome_status[contract]=out['status']
   if out['status']!='AUTHORITATIVE':self.pending[contract]=out['status']
   else:self.pending.pop(contract,None)
  else:
   match=[(a,b) for a,b in rows(self,'CLOSEOUT_ACCEPTANCE') if b['value']['cohort']['brti']==out and b['accepted_at']<=n['published_ts']]
   require(match,'ORIGINAL_CLOSEOUT_ACCEPTANCE_MISSING');a,b=match[0]
   require(out.get('final60_count')==60 and out.get('final60_complete') is True,'BRTI_CLOSEOUT_SCHEMA')
  self.emit(self.fassoc,dict(record=ref(loc),status='VERIFIED_ORIGINAL_OUTCOME',original_acceptance=ref(a),kind=kind));self.metrics['outcome_associations']+=1
 def complete(self,finished,scope):return bool(finished and scope and not self.errors)
 def result(self,value,complete):
  for ticker,identity in self.contracts.items():
   if self.outcome_status.get(ticker)!='AUTHORITATIVE':self.pending.setdefault(ticker,'NO_AUTHORITATIVE_OUTCOME_RECORDED; MAY_BE_OPEN_OR_PENDING')
  value.update(fixture_complete=complete and self.classes=={'FIXTURE'},complete_supplied_scope=complete,actual_production_complete=False,recording_scope='SEALED_ROLE_INTERVALS_ONLY',coverage=self.source_scope,lifecycle_emitted=self.lifecycle,pending_outcomes=self.pending,absent_lifecycle_basis='NOT_PRODUCED_WITHIN_VERIFIED_JOURNAL_INTERVAL' if complete else 'UNKNOWN_MISSING_RECORDING_OR_NOT_PRODUCED',live_transport_verified=False)
  value['contract_boundaries']=self.contracts
  return value

def run(root,index,output,profile):return CampaignVerifier(root,index,output,budgets(profile)).run()
