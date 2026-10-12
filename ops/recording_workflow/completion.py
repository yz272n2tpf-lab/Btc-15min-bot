"""Prepared automatic completion callback, no timer or collection started here."""
from pathlib import Path
import json,sys
from .operator import finalize
from .transfer import package
from .policy import validate_config
from candidates.early_recording_20261012.archive import canonical

class Completion:
    """Call from an approved supervisor OFF the decision path.

    This class starts no thread or clock. Native owners must have stopped offering
    before close/finalize. A future supervisor must invoke finish on deadline,
    owner failure and shutdown. No schedule/service is installed by this module.
    """
    def __init__(self,c,output,store):
        self.config=validate_config(c);self.output=Path(output);self.store=Path(store);self.done=None

    def finish(self,capture,reason):
        if self.done is not None:return self.done
        try:
            clean=capture.close();health=capture.status()
            data=finalize(self.config['root'],self.output,health=health)
            result=package(self.config['root'],self.output/'index',self.store,
                quota=self.config['storage']['backlog_bytes'],
                identity=json.loads((Path(self.config['root'])/'identity.json').read_bytes()),
                report=self.output/'report/quality.json')
            self.done=dict(status='COMPLETED_OFFLINE' if clean and health['status']!='INCOMPLETE' else 'INCOMPLETE',
                reason=reason,report=str(self.output/'report/REPORT.txt'),package=result,
                complete_evidence=data['report']['complete_evidence'],long_test='NO_GO')
        except Exception as exc:
            self.done=dict(status='FAILED',reason=reason,error=type(exc).__name__,details=str(exc)[:160],
                complete_evidence=False,long_test='NO_GO')
        # Available independently of archive/report disk. An approved service
        # action can return this small receipt, then retrieve bounded objects.
        print('BTC15_AUTOMATIC_COMPLETION '+json.dumps(self.done,sort_keys=True),file=sys.stderr,flush=True)
        return self.done
