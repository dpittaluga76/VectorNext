"""Conservative attribution from independently scored observations, not an LLM judge."""


def attribute(row):
    flags=[]
    if row.get('ingested') is False: flags.append('ingestion_failure')
    if row.get('plan_correct') is False: flags.append('planning_failure')
    if row.get('candidate_support') is False and row.get('ingested') is True:
        flags.append('candidate_evidence_missing')
    if row.get('selected_support') is False and row.get('candidate_support') is True:
        flags.append('selection_lost_evidence')
    answerable=row.get('expected')=='supported'
    if answerable and row.get('selected_support') is True and row.get('assessment') in ('ambiguous','insufficient_evidence'):
        flags.append('assessment_missed_answer')
    if answerable and row.get('selected_support') is True and row.get('assessment')=='supported' and row.get('candidate_correct') is False:
        flags.append('extraction_wrong')
    if row.get('validator')=='rejected' and row.get('candidate_correct') is True:
        if row.get('proof_review')=='valid_under_contract': flags.append('validator_false_reject')
        elif row.get('proof_review')=='invalid_under_contract': flags.append('correct_value_invalid_proof')
        else: flags.append('gold_matching_rejection_unadjudicated')
    if row.get('validator')=='accepted' and row.get('candidate_correct') is False:
        flags.append('wrong_answer_accepted')
        if row.get('proof_review')=='invalid_under_contract': flags.append('validator_false_accept')
        elif row.get('proof_review')=='valid_under_contract': flags.append('semantic_error_despite_mechanical_support')
    if row.get('baseline_correct') is False and row.get('oracle_evidence_correct') is True:
        flags.append('recovered_with_oracle_evidence')
    if row.get('oracle_evidence_correct') is False and row.get('oracle_fields_correct') is True:
        flags.append('recovered_with_oracle_fields')
    if row.get('system_error'): flags.append('infrastructure_or_transport_failure')
    return {'case_id':row['case_id'],'flags':flags,'unique_root_cause_claimed':False,
            'unobserved':[k for k in ('ingested','plan_correct','candidate_support','selected_support','assessment',
                'candidate_correct','validator','proof_review','oracle_evidence_correct','oracle_fields_correct') if row.get(k) is None]}
