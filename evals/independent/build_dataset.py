"""Explicit label authoring from acquired sources; never called by tests or the runner."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import pdfplumber

ROOT=Path(__file__).resolve().parent


def save(name,value): (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def build():
    if (ROOT/'freeze.json').exists(): raise ValueError('comparison is frozen; do not regenerate')
    sources=json.loads((ROOT/'sources-draft.json').read_text(encoding='utf-8'))
    documents=[{k:s[k] for k in ('id','path','media_type','sha256')} for s in sources]
    data={'schema_version':'1.0','provenance':{'synthetic':False,'description':'T11 NASA mission and USGS earthquake source snapshots. Provenance in sources.json/README.md. Codex-authored questions and labels prepared before inference, independent of T01 synthetic data; not independently administered. No T01 sources or labels reused.'},'documents':documents,'evidence':[],'cases':[]}
    requests={}
    def text(id,doc,needle):
        raw=(ROOT/'fixtures'/(doc+'.txt')).read_bytes();target=needle.encode()
        start=raw.index(target);end=start+len(target)
        data['evidence'].append({'id':id,'document_id':doc,'locator':{'kind':'text','byte_start':start,'byte_end':end,'line_start':raw[:start].count(b'\n')+1,'line_end':raw[:end-1].count(b'\n')+1},'expected':needle})
        return id
    def line(id,doc,needle):
        lines=(ROOT/'fixtures'/(doc+'.txt')).read_text(encoding='utf-8').splitlines()
        found=[x for x in lines if needle in x]
        if not found: raise ValueError((doc,needle))
        return text(id,doc,found[0])
    def pdf(id,doc,page,box):
        with pdfplumber.open(ROOT/'fixtures'/(doc+'.pdf')) as p: value=p.pages[page-1].crop(box).extract_text()
        data['evidence'].append({'id':id,'document_id':doc,'locator':{'kind':'pdf','page':page,'bbox':box,'method':'native'},'expected':value})
        return id
    def pointer(id,doc,path):
        value=json.loads((ROOT/'fixtures'/(doc+'.json')).read_text(encoding='utf-8'))
        for part in path.split('/')[1:]: value=value[int(part)] if isinstance(value,list) else value[part]
        data['evidence'].append({'id':id,'document_id':doc,'locator':{'kind':'json','pointer':path},'expected':value})
        return id
    def case(id,question,fields,values,refs,tags,template=None,history=None):
        field_sources={k:v if isinstance(v,list) else [v] for k,v in refs.items()}
        support=[]
        for combination in itertools.product(*field_sources.values()):
            group=sorted(set(combination))
            if group not in support:support.append(group)
        c={'id':id,'split':'comparison','question':question,'tags':tags,'expected':{'status':'supported','fields':values,'field_sources':field_sources,'support_sets':support}}
        request={'question':question,'fields':{k:({'kind':v} if isinstance(v,str) else v) for k,v in fields.items()}}
        if template:
            request['template']=template;c['presentation']={'template':template,'expected_text':template.format_map(values)}
        if history:
            request['history']=history;c['history']=[{'role':t['role'],'content':t['text']} for t in history]
        data['cases'].append(c);requests[id]=request
    def nonanswer(id,question,fields,expected,tags):
        data['cases'].append({'id':id,'split':'comparison','question':question,'tags':tags,'expected':expected})
        requests[id]={'question':question,'fields':{k:{'kind':v} for k,v in fields.items()}}

    launches={}
    for doc in ('voyager1','voyager2','pioneer10','pioneer11','new_horizons','stardust','deep_impact','viking1'):
        launches[doc]=line(doc+'_launch',doc,'Launch Date and Time |')
    for doc,date in [('juno','Aug. 5, 2011'),('cassini','Oct. 15, 1997'),('dawn','Sept. 27, 2007')]:
        launches[doc]=text(doc+'_launch',doc,'Launch\n\n'+date)
    jup=line('voyager1_jupiter','voyager1','March 5, 1979: Jupiter')
    sat=line('voyager1_saturn','voyager1','Nov. 12, 1980: Saturn')
    jup_alt=text('voyager1_jupiter_prose','voyager1','The spacecraft’s closest encounter with Jupiter was at 12:05 UT on March 5, 1979, at a range of 174,000 miles (280,000 km),')
    sat_alt=text('voyager1_saturn_prose','voyager1','Voyager 1’s closest approach to Saturn was at 23:46 UT on Nov. 12, 1980, at a range of about 78,000 miles (126,000 km).')
    launch_alt=text('voyager1_launch_intro','voyager1',"No spacecraft has gone farther than NASA's Voyager 1. Launched in 1977 to fly by Jupiter and Saturn, Voyager 1 crossed into interstellar space in August 2012 and continues to collect data.")
    case('voyager_timeline','In which year was Voyager 1 launched, and in which years did it fly past Jupiter and Saturn?',
        {'launch_year':'integer','jupiter_year':'integer','saturn_year':'integer'},
        {'launch_year':1977,'jupiter_year':1979,'saturn_year':1980},
        {'launch_year':[launches['voyager1'],launch_alt],'jupiter_year':[jup,jup_alt],'saturn_year':[sat,sat_alt]},['txt','timeline','readme'],
        'Voyager 1 | Launch: {launch_year} | Jupiter: {jupiter_year} | Saturn: {saturn_year}')
    record=line('golden_record','voyager1','Audio on the disc includes greetings')
    case('golden_record_counts',"According to the Voyager 1 page, how many languages, sounds from life on Earth, and images are included on the Golden Record?",
        {'languages':'integer','sounds':'integer','images':'integer'},{'languages':55,'sounds':35,'images':115},dict.fromkeys(['languages','sounds','images'],record),['txt','close_numeric_distractors'])
    nitrogen=line('titan_nitrogen','voyager1','Images of Titan showed')
    case('titan_nitrogen','What nitrogen percentage did Voyager 1 report for Titan\'s atmosphere?',{'nitrogen_percent':'integer'},{'nitrogen_percent':90},{'nitrogen_percent':nitrogen},['txt','units'])
    ura=line('voyager2_uranus','voyager2','Jan 24, 1986: Uranus')
    nep=line('voyager2_neptune','voyager2','Aug 25, 1989: Neptune')
    case('ice_giant_years','In which years did Voyager 2 fly past Uranus and Neptune?',{'uranus_year':'integer','neptune_year':'integer'},{'uranus_year':1986,'neptune_year':1989},{'uranus_year':ura,'neptune_year':nep},['txt','timeline'])
    mass={d:line(d+'_mass',d,'Spacecraft Mass |') for d in ['pioneer11','new_horizons','stardust','deep_impact','viking1']}
    case('pioneer_mass','What spacecraft mass in kilograms is listed for Pioneer 11?',{'mass_kg':'number'},{'mass_kg':258.5},{'mass_kg':mass['pioneer11']},['txt','table','decimal','similar_mission'])
    case('new_horizons_mass','What spacecraft mass in kilograms is listed for New Horizons?',{'mass_kg':'integer'},{'mass_kg':478},{'mass_kg':mass['new_horizons']},['txt','table','units'])
    path_launch=line('pathfinder_launch','mars_pathfinder','Launch |')
    path_land=line('pathfinder_land','mars_pathfinder','Mars Landing |')
    rover=line('pathfinder_rover','mars_pathfinder','first-ever robotic rover, Sojourner')
    case('pathfinder_timeline','Which year did Mars Pathfinder launch, which year did it land on Mars, and what was its rover called?',
        {'launch_year':'integer','landing_year':'integer','rover':'string'},{'launch_year':1996,'landing_year':1997,'rover':'Sojourner'},
        {'launch_year':path_launch,'landing_year':path_land,'rover':rover},['txt','distant_passages'])
    galileo=line('galileo_shuttle','galileo','Launched into Earth orbit from the Space Shuttle Atlantis in 1989')
    case('galileo_orbits','Which space shuttle carried Galileo into Earth orbit, and how many times did the mission orbit Jupiter?',
        {'shuttle':'string','orbits':'integer'},{'shuttle':'Atlantis','orbits':34},{'shuttle':galileo,'orbits':galileo},['txt','distractors'])
    case('three_launch_years','Give the individual launch years of Juno, Cassini and Dawn.',
        {'juno_year':'integer','cassini_year':'integer','dawn_year':'integer'},
        {'juno_year':2011,'cassini_year':1997,'dawn_year':2007},
        {'juno_year':launches['juno'],'cassini_year':launches['cassini'],'dawn_year':launches['dawn']},['txt','multi_document','three_sources'])
    case('three_spacecraft_masses','Give the listed spacecraft masses in kilograms for Stardust, Deep Impact and New Horizons separately.',
        {'stardust_kg':'integer','deep_impact_kg':'integer','new_horizons_kg':'integer'},
        {'stardust_kg':385,'deep_impact_kg':650,'new_horizons_kg':478},
        {'stardust_kg':mass['stardust'],'deep_impact_kg':mass['deep_impact'],'new_horizons_kg':mass['new_horizons']},['txt','multi_document','three_sources','units'])
    case('four_launch_years','Give the launch years of Pioneer 10, Pioneer 11, Voyager 1 and Voyager 2 separately.',
        {d+'_year':'integer' for d in ['pioneer10','pioneer11','voyager1','voyager2']},
        {'pioneer10_year':1972,'pioneer11_year':1973,'voyager1_year':1977,'voyager2_year':1977},
        {d+'_year':launches[d] for d in ['pioneer10','pioneer11','voyager1','voyager2']},['txt','multi_document','four_sources','similar_mission'])
    pads={d:line(d+'_pad',d,'Launch Site |') for d in ['pioneer10','pioneer11','stardust']}
    case('three_launch_pads','Give only the launch-complex identifiers for Pioneer 10, Pioneer 11 and Stardust, retaining each letter suffix.',
        {d+'_pad':'string' for d in pads},{'pioneer10_pad':'36A','pioneer11_pad':'36B','stardust_pad':'17A'},
        {d+'_pad':v for d,v in pads.items()},['txt','multi_document','three_sources','exact_string'])
    dims=pdf('perseverance_dimensions','perseverance_pdf',2,[310,76,570,184])
    timeline=pdf('perseverance_timeline','perseverance_pdf',1,[44,623,250,691])
    moxie=pdf('perseverance_moxie','perseverance_pdf',2,[43,386,292,482])
    case('perseverance_mass','In the December 2020 Perseverance fact sheet, what is the rover mass in kilograms? Return the printed numeric text with its comma.',
        {'mass_kg_text':'string'},{'mass_kg_text':'1,025'},{'mass_kg_text':dims},['pdf','units','exact_string'])
    case('perseverance_dimensions','What length, width and height in meters does the December 2020 fact sheet give for Perseverance, excluding its arm?',
        {'length_m':'integer','width_m':'number','height_m':'number'},
        {'length_m':3,'width_m':2.7,'height_m':2.2},dict.fromkeys(['length_m','width_m','height_m'],dims),['pdf','units','multi_column'])
    case('moxie_gases','According to the Perseverance fact sheet, which atmospheric gas does MOXIE use, and which gas does it produce?',
        {'input_gas':'string','output_gas':'string'},{'input_gas':'carbon dioxide','output_gas':'oxygen'},dict.fromkeys(['input_gas','output_gas'],moxie),['pdf','technical_terms'])
    case('perseverance_cross_page','Using the December 2020 Perseverance fact sheet, give the planned landing year and rover mass in kilograms as printed, including the comma in the mass.',
        {'planned_landing_year':'integer','mass_kg_text':'string'},{'planned_landing_year':2021,'mass_kg_text':'1,025'},
        {'planned_landing_year':timeline,'mass_kg_text':dims},['pdf','cross_page'])
    samples=pdf('apollo_samples','apollo11_pdf',2,[35,444,272,469])
    module=pdf('apollo_module','apollo11_pdf',2,[35,141,273,279])
    retro=pdf('apollo_reflector','apollo11_pdf',2,[531,144,760,201])
    case('apollo_sample_and_module','According to the Apollo 11 anniversary sheet, how many kilograms of samples were collected, and what was the command module called?',
        {'sample_mass_kg':'number','command_module':'string'},{'sample_mass_kg':21.7,'command_module':'Columbia'},
        {'sample_mass_kg':samples,'command_module':module},['pdf','distant_passages','units'])
    case('apollo_reflector','Which Apollo 11 experiment used cube-shaped mirrors to reflect laser pulses directly back to Earth?',
        {'experiment':'string'},{'experiment':'Lunar Ranging Retroreflector'},{'experiment':retro},['pdf','technical_terms'])
    for doc,name,mag,depth in [('tohoku_json','2011 Great Tohoku Earthquake, Japan',9.1,29),('maule_json','2010 Maule, Chile Earthquake',8.8,22.9)]:
        m=pointer(doc+'_mag',doc,'/features/0/properties/mag');dep=pointer(doc+'_depth',doc,'/features/0/geometry/coordinates/2')
        case(doc+'_magnitude_depth','In the USGS snapshot for '+name+', what are the magnitude and hypocentral depth in kilometers?',
            {'magnitude':'number','depth_km':'integer' if doc=='tohoku_json' else 'number'},
            {'magnitude':mag,'depth_km':depth},{'magnitude':m,'depth_km':dep},['json','typed_numbers','similar_record'])
    tz=pointer('tohoku_timezone','tohoku_json','/features/0/properties/tz')
    flag=pointer('tohoku_tsunami','tohoku_json','/features/0/properties/tsunami')
    dmin=pointer('tohoku_dmin','tohoku_json','/features/0/properties/dmin')
    case('raw_timezone_null','What is the raw tz property in the supplied USGS Tohoku event record? Return its stored value, including null.',
        {'tz':{'kind':'integer','nullable':True}},{'tz':None},{'tz':tz},['json','raw_null'])
    case('raw_tsunami_flag','What is the raw integer tsunami property in the supplied USGS Tohoku event record? This asks for the stored flag, not whether a tsunami occurred.',
        {'tsunami_flag':'integer'},{'tsunami_flag':0},{'tsunami_flag':flag},['json','zero','raw_field_semantics'])
    nonanswer('unknown_station_distance','What is the numeric distance to the nearest station, dmin, in the supplied USGS Tohoku event record?',
        {'dmin':'number'},{'status':'insufficient_evidence','reason':'The source dmin is null; an unknown distance is not numeric zero.'},['json','unknown_value'])
    nonanswer('ambiguous_voyager','On what date did Voyager launch?',{'launch_date':'string'},
        {'status':'ambiguous','clarification_fields':['mission'],'alternatives':[
            {'fields':{'mission':'Voyager 1','launch_date':'Sept. 5, 1977'},'support_set':[launches['voyager1']]},
            {'fields':{'mission':'Voyager 2','launch_date':'Aug. 20, 1977'},'support_set':[launches['voyager2']]}]},['txt','ambiguous','similar_mission'])
    two=line('voyager_two_instruments','voyager1','On April 17, engineers')
    four=line('voyager_four_instruments','voyager1','four still-functioning instruments')
    nonanswer('conflicting_instruments','How many science instruments are still operating on Voyager 1 according to the supplied page? Resolve any conflicting statements before giving a count.',
        {'operating_instruments':'integer'},{'status':'ambiguous','clarification_fields':['operating_instruments'],'alternatives':[
            {'fields':{'operating_instruments':2},'support_set':[two]},
            {'fields':{'operating_instruments':4},'support_set':[four]}]},['txt','conflicting_source','distant_passages'])
    nonanswer('missing_computer_serial',"What serial number is printed on Voyager 1's onboard flight computer?",{'serial_number':'string'},
        {'status':'insufficient_evidence','reason':'No supplied source records the flight computer serial number.'},['txt','missing_evidence'])
    nonanswer('missing_tsunami_height','According to the supplied USGS Tohoku event record, what was the maximum tsunami run-up height in meters?',{'runup_meters':'number'},
        {'status':'insufficient_evidence','reason':'The raw tsunami flag is not a run-up measurement; no run-up height is supplied.'},['json','missing_evidence','zero_distractor'])
    case('voyager_followup','In which year did that encounter take place?',{'encounter_year':'integer'},{'encounter_year':1986},{'encounter_year':ura},['txt','conversation'],
        history=[{'role':'user','text':"I am asking about Voyager 2's flyby of Uranus."}])

    schema=json.loads((ROOT.parent/'dataset.schema.json').read_text(encoding='utf-8'))
    schema['title']='VectorNext independent public-source dataset v1'
    schema['properties']['provenance']['properties']['synthetic']['const']=False
    schema['$defs']['case']['properties']['split']['enum']=['comparison']
    save('dataset.schema.json',schema);save('dataset.json',data);save('requests.json',requests);save('sources.json',sources)
    request_path=ROOT.parents[1]/'tests/fixtures/answers/voyager.json'
    request_path.write_text(json.dumps(requests['voyager_timeline'],indent=2)+'\n',encoding='utf-8')
    print(len(documents),'documents;',len(data['evidence']),'source references;',len(data['cases']),'comparison questions')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--author',action='store_true',required=True);p.parse_args();build()
