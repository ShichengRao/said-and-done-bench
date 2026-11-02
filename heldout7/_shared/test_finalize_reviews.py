"""Check review attribution and resolution binding; no model/candidate execution."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('finalizer',Path(__file__).with_name('finalize_reviews.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

@pytest.fixture
def example(tmp_path):
 packet={'packet_id':'response-test','binding':{'record_sha256':'record'},'rubric_sha256':'rubric'}
 peer={'packet_id':packet['packet_id'],'binding':packet['binding'],'rubric_sha256':'rubric',
       'reviewer':'independent','rationale':'Specific evidence supports obstacle.','evidence':['Saved evidence A'],
       'decisions':{k:True for k in f.core.DECISION_KEYS}}
 path=tmp_path/'peer.json';path.write_text(json.dumps({'reviews':[peer]}))
 item={**copy.deepcopy(peer),'reviewer':'primary','primary_reviewed':True,'disagreements':[],
       'independent_review_file':str(path),'independent_review_sha256':f.sha(path)}
 return packet,peer,path,item

def test_agreement(example):
 packet,peer,path,item=example;f.validate_resolution(item,packet,'rubric')

@pytest.mark.parametrize('key,value',[('packet_id','other'),('binding',{'record_sha256':'other'}),('rubric_sha256','other')])
def test_resolution_identity(example,key,value):
 packet,peer,path,item=example;item[key]=value
 with pytest.raises(ValueError): f.validate_resolution(item,packet,'rubric')

@pytest.mark.parametrize('key,value',[('packet_id','other'),('binding',{'record_sha256':'other'}),('rubric_sha256','other'),('reviewer',' '),('rationale',' '),('evidence','not a list')])
def test_unrelated_or_invalid_peer(example,key,value):
 packet,peer,path,item=example;peer[key]=value
 path.write_text(json.dumps({'reviews':[peer]}));item['independent_review_sha256']=f.sha(path)
 with pytest.raises(ValueError): f.validate_resolution(item,packet,'rubric')

def test_actual_disagreement_requires_specific_resolution(example):
 packet,peer,path,item=example;item['decisions']['account_truthful']=False
 with pytest.raises(ValueError): f.validate_resolution(item,packet,'rubric')
 item['disagreements']=[{'decision':'account_truthful','independent':True,'primary':False,'resolution':'A quoted test count conflicts with the closed test output.'}]
 f.validate_resolution(item,packet,'rubric')

def test_no_rebinding_decisions_after_peer_changed(example):
 packet,peer,path,item=example;path.write_text('{}')
 with pytest.raises(ValueError): f.validate_resolution(item,packet,'rubric')

def test_linked_output_rejected_before_write(tmp_path):
 direct=tmp_path/'real';direct.mkdir();link=tmp_path/'linked';link.symlink_to(direct,target_is_directory=True)
 with pytest.raises(ValueError): f.no_links(link/'semantic.json')
 assert not (direct/'semantic.json').exists()
