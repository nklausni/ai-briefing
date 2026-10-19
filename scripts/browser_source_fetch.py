#!/usr/bin/env python3
"""Bounded public-page Chrome fetch. No login, paywall removal or stealth scripts."""
import argparse
import json
import subprocess
import shlex
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'
EXPR = 'JSON.stringify({url:location.href,title:document.title,ua:navigator.userAgent,text:document.body?.innerText,links:Array.from(document.querySelectorAll("a[href]")).map(a=>({text:a.innerText,url:a.href}))})'

def command(url, session):
    if urlparse(url).scheme not in ('http', 'https'):
        raise ValueError('Only public HTTP(S) source URLs are supported')
    return ['npx', '--yes', 'agent-browser', '--session', session, '--user-agent', UA,
            'batch', 'open '+shlex.quote(url), 'wait 3000', 'eval '+shlex.quote(EXPR), 'close']

def decode(raw):
    for line in raw.splitlines():
        try:
            obj = json.loads(line)
            if isinstance(obj, str):
                obj = json.loads(obj)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and obj.get('url','').startswith(('https://','http://')) and obj.get('text','').strip():
            return obj
    raise ValueError('No nonempty navigated page; do not claim source checked')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--session', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        result = subprocess.run(command(args.url,args.session), capture_output=True,text=True,timeout=60,check=True)
        page = decode(result.stdout)
        page['retrieved_at'] = datetime.now(timezone.utc).isoformat()
        out = Path(args.output)
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(page,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'cache':str(out),'url':page['url'],'title':page.get('title'),'characters':len(page['text']), 'note':'Fetch only; inspect content/date/access wall before claiming readable source.'},ensure_ascii=False))
    finally:
        subprocess.run(['npx','--yes','agent-browser','--session',args.session,'close'], capture_output=True,timeout=15)
