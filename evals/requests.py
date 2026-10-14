"""Public dev request contract. Never derive request types/constraints from gold values."""
FIELDS = {
    'q_pele_exact': {'year':'integer','goals':'integer','opponent':'string'},
    'q_wrapped': {'goals':'integer'},
    'q_followup': {'year':'integer','goals':'integer','opponent':'string'},
    'q_ambiguous': {'goals':'integer'},
    'q_missing_match': {'goals':'integer'},
    'q_null_unknown': {'assists':'integer'},
    'q_zero': {'goals':'integer'},
    'q_raw_null': {'assists':'integer'},
    'q_player_id': {'player_id':'string'},
    'q_array': {'goals':'integer'},
    'q_table': {'flow':'integer','unit':'string','water_temperature_c':'integer'},
    'q_cross_page': {'wait':'integer','unit':'string'},
    'q_scan': {'torque':'integer','unit':'string'},
}


def public_request(case):
    if case['split'] != 'dev' or case['id'] not in FIELDS:
        raise ValueError('only registered development requests may run')
    result={'question':case['question'],'fields':{k:{'kind':v} for k,v in FIELDS[case['id']].items()}}
    if case['id']=='q_raw_null': result['fields']['assists']['nullable']=True
    if 'history' in case:
        result['history']=[{'role':t['role'],'text':t['content']} for t in case['history']]
    if 'presentation' in case: result['template']=case['presentation']['template']
    return result
