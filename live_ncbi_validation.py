"""Live PubMed production smoke test. No mocks: exits nonzero on failure."""
import json, sys, time, datetime, traceback
from pathlib import Path
import requests
from xml.etree import ElementTree as ET

BASE='https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
EXPECTED={
 '38801022': ('10.1002/mus.28114','management of immune-mediated necrotizing myopathy'),
 '29480216': ('10.3233/jnd-170282','anti-hmgcr myopathy'),
 '34449189': ('10.1056/nejmoa2107038','empagliflozin in heart failure with a preserved ejection fraction'),
 '31535829': ('10.1056/nejmoa1911303','dapagliflozin in patients with heart failure and reduced ejection fraction'),
}
def get(session,path,params):
    for attempt in range(3):
        try:
            r=session.get(BASE+path,params=params,timeout=20,headers={'User-Agent':'medical-research-ai-validation/1.0'})
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt==2: raise
            time.sleep(attempt+1)

def run():
    report={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':[],'outcome':'FAIL'}
    s=requests.Session()
    try:
        r=get(s,'esearch.fcgi',{'db':'pubmed','term':'anti-HMGCR[Title/Abstract]','retmax':5,'retmode':'json'})
        payload=r.json()['esearchresult']; ids=payload['idlist']
        assert ids and int(payload['count'])>0, 'esearch returned no records'
        report['checks'].append({'test':'live_esearch','status':'PASS','count':payload['count'],'ids':ids})
        time.sleep(.4)
        for pmid,(doi,title) in EXPECTED.items():
            r=get(s,'efetch.fcgi',{'db':'pubmed','id':pmid,'retmode':'xml'})
            root=ET.fromstring(r.content)
            citation=root.find('.//MedlineCitation')
            assert citation is not None,'missing MedlineCitation'
            actual_pmid=(citation.findtext('PMID') or '').strip()
            title_elem=citation.find('.//ArticleTitle')
            actual_title=''.join(title_elem.itertext()).strip() if title_elem is not None else ''
            dois=[(e.text or '').strip().lower() for e in root.findall('.//ArticleId') if e.attrib.get('IdType')=='doi']
            assert actual_pmid==pmid,(actual_pmid,pmid)
            assert doi in dois,(doi,dois)
            assert title.lower() in actual_title.lower(),(title,actual_title)
            report['checks'].append({'test':'live_efetch_identity','status':'PASS','pmid':pmid,'doi':doi,'title':actual_title})
            time.sleep(.4)
        report['outcome']='PASS'
    except Exception as exc:
        report['checks'].append({'test':'live_ncbi','status':'FAIL','error':type(exc).__name__+': '+str(exc)})
    Path('ncbi_live_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['outcome']=='PASS' else 1
if __name__=='__main__':sys.exit(run())
