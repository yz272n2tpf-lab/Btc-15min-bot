"""Verify final defensive economics correction leaves retained decisions exact."""
import hashlib,json
from .study import OUT,PRIOR,replay,load_data


def main():
    profile=json.loads((OUT/'profile_DISABLED.json').read_text())
    paths={'development':PRIOR/'development_inputs.json.gz',
           'calibration':PRIOR/'calibration_inputs.json.gz',
           'opened_oct4':PRIOR/'diagnostic_inputs.json.gz',
           'opened_oct6':PRIOR/'acceptance_inputs.json.gz',
           'acceptance_oct7':OUT/'acceptance_inputs.json.gz'}
    for name,path in paths.items():
        data=load_data(path)
        expected=json.loads((OUT/(name+'_unified_value.json')).read_text())
        expected.pop('summary')
        actual=replay(data,'unified_value')
        assert actual==expected,name
        screened=replay(data,'unified_value',profile,False)
        assert not screened['episodes'],name
        print(name,len(data),'contracts; proposal/events/invalidation replay EXACT; economically admitted=0')
    print('No strategy thresholds or historical decisions changed after acceptance; defensive cost gate only')


if __name__=='__main__':main()
