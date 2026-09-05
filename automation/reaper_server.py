from __future__ import annotations
import os,subprocess,sys
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app); ROOT=Path(__file__).resolve().parents[1]; SCRIPT=ROOT/'scripts'/'dirty_diaperz_fadr.py'
def body(): return request.get_json(silent=True) or {}
def bad(message,status=400): return jsonify(success=False,error=message),status
@app.errorhandler(Exception)
def unexpected(e): app.logger.exception('Unhandled error'); return bad(str(e),500)
@app.post('/health')
def health(): return jsonify(success=True,status='ok')
@app.post('/process-song')
def process_song():
    d=body(); missing=[k for k in ('source','title','out') if not d.get(k)]
    if missing:return bad('Missing required fields: '+', '.join(missing))
    source=Path(d['source']).expanduser()
    if not source.is_file():return bad(f'Source file not found: {source}')
    cmd=[sys.executable,str(SCRIPT),'--source',str(source),'--title',str(d['title']),'--out',str(d['out'])]
    for key,flag in (('artist','--artist'),('bpm','--bpm'),('scene','--scene')):
        if d.get(key) is not None:cmd.extend([flag,str(d[key])])
    try:r=subprocess.run(cmd,capture_output=True,text=True,timeout=int(os.getenv('PROCESS_TIMEOUT_SECONDS','1800')))
    except subprocess.TimeoutExpired:return bad('Song processing timed out',504)
    if r.returncode:return jsonify(success=False,error='Song processing failed',exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr),500
    return jsonify(success=True,stdout=r.stdout)
if __name__=='__main__':app.run(host='127.0.0.1',port=5001)
