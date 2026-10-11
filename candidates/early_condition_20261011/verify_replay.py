"""Portable offline verification using only checked-in normalized evidence."""
import hashlib,json
from pathlib import Path
from .study import load_data,replay,stats

out=Path('audit/early_condition_20261011')
frozen=json.loads((out/'PRE_ACCEPTANCE_FREEZE.json').read_text())
for name,expected in frozen['files'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==expected,name
profile=json.loads((out/'profile_DISABLED.json').read_text())
assert profile['enabled'] is False and profile['validated'] is False
for name,inputs in [('acceptance','acceptance'),('diagnostic_opened_holdout','diagnostic'),('development','development'),('calibration','calibration')]:
    data=load_data(out/(inputs+'_inputs.json.gz'))
    expected=json.loads((out/(name+'_evaluation.json')).read_text())['summary']
    actual=stats(replay(data,proposal=True))
    assert all(expected[k]==v for k,v in actual.items()),name
    assert len(replay(data,profile=profile)['episodes'])==0,name
    print('PASS',name,len(data),'contracts',sum(map(len,data.values())),'source observations; exact frozen replay')
print('PASS: zero economically admitted BUYs; disabled profile preserved; no network or writes')
