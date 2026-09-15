#!/usr/bin/env python3
"""Render the inactive A1 workflow to stdout; does not connect or deploy."""
from __future__ import annotations

import json


def workflow():
    prepare = """const n=new Date();
return [{json:{capture_id:`bls-n8n-${$execution.id}`,year:n.getUTCFullYear(),month:n.getUTCMonth()+1,started_at_utc:n.toISOString()}}];"""
    envelope = """const p=$('Prepare capture').first().json;
const r=$input.first().json;
const b=await this.helpers.getBinaryDataBuffer(0,'publisher_html');
if(b.length===0||b.length>2097152) throw Error('BLS body outside retention limit');
if(r.statusCode!==200||typeof r.headers?.['content-type']!=='string') throw Error('BLS response not HTML success');
const ct=r.headers['content-type'];
if(!['text/html','application/xhtml+xml'].includes(ct.split(';')[0].trim().toLowerCase())) throw Error('BLS content type refused');
return [{json:{...p,completed_at_utc:new Date().toISOString(),status_code:r.statusCode,content_type:ct,body_base64:b.toString('base64'),body_complete:true}}];"""
    specs = [
        ('manual', 'Manual A1 capture', 'manualTrigger', 1, {}),
        ('prepare', 'Prepare capture', 'code', 2, {'jsCode': prepare}),
        ('fetch', 'Fetch BLS', 'httpRequest', 4.2, {
            'method': 'GET',
            'url': "={{'https://www.bls.gov/schedule/'+$json.year+'/'+String($json.month).padStart(2,'0')+'_sched_list.htm'}}",
            'options': {'redirect': {'redirect': {'followRedirects': False}}, 'timeout': 35000,
                        'response': {'response': {'fullResponse': True, 'neverError': False,
                                     'responseFormat': 'file', 'outputPropertyName': 'publisher_html'}}}}),
        ('envelope', 'Prepare observed envelope', 'code', 2, {'jsCode': envelope}),
        ('retain', 'Retain BLS', 'httpRequest', 4.2, {
            'method': 'POST', 'url': 'http://127.0.0.1:8091/forex/a1/retain-bls',
            'authentication': 'genericCredentialType', 'genericAuthType': 'httpHeaderAuth',
            'sendBody': True, 'specifyBody': 'json', 'jsonBody': '={{JSON.stringify($json)}}',
            'options': {'redirect': {'redirect': {'followRedirects': False}}, 'timeout': 35000}}),
    ]
    nodes = [{'id': ident, 'name': name, 'type': 'n8n-nodes-base.'+kind,
              'typeVersion': version, 'position': [i*240, 0], 'parameters': parameters,
              'retryOnFail': False} for i, (ident, name, kind, version, parameters) in enumerate(specs)]
    return {'name': 'Forex A1 BLS immutable capture', 'active': False,
            'settings': {'executionOrder': 'v1', 'timezone': 'UTC', 'executionTimeout': 90,
                         'saveDataSuccessExecution': 'none', 'saveDataErrorExecution': 'none'},
            'nodes': nodes, 'connections': {nodes[i]['name']: {'main': [[{
                'node': nodes[i+1]['name'], 'type': 'main', 'index': 0}]]} for i in range(len(nodes)-1)}}


if __name__ == '__main__':
    print(json.dumps(workflow(), indent=2))
