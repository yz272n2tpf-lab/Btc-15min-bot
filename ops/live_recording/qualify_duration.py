"""Targeted 600,000-envelope, 86,940-second synthetic reader/codec stress.

This is a declared source/codec capacity workload, not a strategy test, recorded
market history, complete live fixture, or guarantee of live feed rates.
"""
import argparse,json,resource,time
from pathlib import Path
from candidates.early_recording_20261012.archive import Archive,BUDGET
from ops.recording_workflow.policy import local_policy
from ops.recording_workflow.evidence import index_run,file_sha
from .reader import CampaignVerifier,budgets
from .policy import GiB,canonical,atomic

class CapacityVerifier(CampaignVerifier):
 def expectations(self):return {'capacity_fixture':True}
 def associate(self,scope):pass
 def complete(self,finished,scope):return False

def run(out,records=600000):
 out=Path(out);out.mkdir(parents=True,exist_ok=False);root=out/'run';root.mkdir();p=local_policy();p.update(per_archive_bytes=GiB,total_bytes=4*GiB)
 a=Archive(root/'source',evidence_class='FIXTURE',source_binding='duration-capacity:main',budget=dict(BUDGET,max_total_bytes=GiB),storage_policy=p)
 a.session='synthetic-duration-capacity-20261013';a.start();beg=time.monotonic()
 for i in range(records):
  at=1577836800+i*86940/(records-1);asset='BTC' if i%2==0 else 'BRTI'
  a.source(dict(asset=asset,value=100000.+i%101,source_ts=at,receipt_ts=at+.01,original_receipt_ts=at+.01,available_at=at+.01,feed='SYNTHETIC_CAPACITY_'+asset,epoch='SYNTHETIC',basis='ORIGINAL',accepted_by_owner=True,epoch_basis='SYNTHETIC_FIXTURE',receipt_basis='SYNTHETIC_APPLICATION_RECEIPT'))
 a.write('STOP',dict(clean=True));a.close();write_seconds=time.monotonic()-beg
 beg=time.monotonic();index_run(root,out/'index',profile='day');index_seconds=time.monotonic()-beg
 v=CapacityVerifier(root,out/'index',out/'verification',budgets('day'));summary=v.run()
 receipt=dict(schema='BTC15_SYNTHETIC_DURATION_QUALIFICATION_V1',fixture_only=True,logical_seconds=86940,input_envelopes=records,actual_envelopes=a.seq,decoded_bytes=a.journal.raw_bytes,compressed_bytes=a.journal.stored_bytes,writer_seconds=write_seconds,writer_envelopes_per_second=records/write_seconds,index_seconds=index_seconds,reader_seconds=summary['elapsed_seconds'],reader_work_db_bytes=summary['work_db_bytes'],peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,all_partitions_processed=summary['all_partitions_processed'],issue_counts=summary['issue_counts'],partitions=summary['partitions'],records_read=summary['records_read'],not_qualified=['live rates or worst feed bursts','native timing interference','private transfer','strategy/lifecycle completeness','production dependencies/free space'],segments=[dict(path=str(f.relative_to(root)),size=f.stat().st_size,sha256=file_sha(f)) for f in sorted(root.rglob('*.gz'))])
 atomic(out/'QUALIFICATION.json',receipt);print(json.dumps(receipt,sort_keys=True));return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();run(a.output)
