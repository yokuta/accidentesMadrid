"""API portable. Los votos se escriben en SQLite WAL; DuckDB queda para análisis.

Arranque: uvicorn backend.app:app --host 0.0.0.0 --port 8000 --workers 4
Variables: VOTES_DB, ADMIN_TOKEN, GOOGLE_MAPS_API_KEY, ALLOWED_ORIGINS,
COOKIE_SECURE (1 en HTTPS). No publicar el archivo SQLite como recurso web.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

AGE = Literal['18–24','25–34','35–44','45–54','55–64','65+','Prefiero no decirlo']
GENDER = Literal['Mujer','Hombre','No binario','Otra identidad','Prefiero no decirlo']
REASONS = {'Anchura de la acera','Visibilidad al cruzar','Tráfico','Pasos de peatones','Iluminación','Arbolado y entorno','Accesibilidad','Sensación general'}
DEMO = [
 dict(id='demo-a',label='Punto A · Madrid',lat=40.4331538,lon=-3.7040872,pano_id='4XV5XZ4Vo7SQAULn992JrQ',heading=195.89313310418282,pitch=3.8884,cohort='unverified',metrics=None),
 dict(id='demo-b',label='Punto B · Madrid',lat=40.4328741,lon=-3.704739,pano_id='VoK_pFOJdaEOzFov2O1FUg',heading=0,pitch=0,cohort='unverified',metrics=None),
]
DB_PATH = Path(os.getenv('VOTES_DB',str(Path(__file__).parent/'respuestas.sqlite')))
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN','')
ALLOWED_ORIGINS = [s.strip() for s in os.getenv('ALLOWED_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',') if s.strip()]
def now(): return datetime.now(timezone.utc).isoformat()
def sha(value): return hashlib.sha256(value.encode()).hexdigest()
def j(value): return json.dumps(value,ensure_ascii=False,allow_nan=False)

@contextmanager
def connection(write=False):
    # Una conexión por petición; no compartir objetos de conexión entre hilos.
    con=sqlite3.connect(DB_PATH,timeout=30,isolation_level=None)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=30000')
    try:
        if write: con.execute('BEGIN IMMEDIATE')
        yield con
        if write: con.commit()
    except Exception:
        if write: con.rollback()
        raise
    finally: con.close()

def initialize():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    with connection() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8'))

@asynccontextmanager
async def lifespan(app):
    initialize()
    yield

app=FastAPI(title='A pie · API del estudio',version='1.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=ALLOWED_ORIGINS,allow_credentials=True,allow_methods=['GET','POST'],allow_headers=['Content-Type','Authorization'])

class Profile(BaseModel):
    age_range: AGE
    gender: GENDER
    urban: Literal['Sí','No','Prefiero no decirlo']
    city: str | None = Field(default=None,max_length=100)
    consent: Literal[True]

class Vote(BaseModel):
    trial_id: str
    choice: Literal['left','right','tie','skip']
    reasons: list[str] = Field(default_factory=list,max_length=8)
    duration_ms: int = Field(ge=0,le=86400000)
    view: dict = Field(default_factory=dict)

class Metrics(BaseModel):
    accidents:int=Field(ge=0)
    radius_m:float=Field(gt=0,le=1000)
    year_start:int=Field(ge=2010,le=2100)
    year_end:int=Field(ge=2010,le=2100)
    version:str
    definition:str
    quality:str
    verified:bool=True

class Point(BaseModel):
    id:str=Field(min_length=1,max_length=80)
    label:str=Field(max_length=150)
    lat:float=Field(ge=40,le=41)
    lon:float=Field(ge=-4.2,le=-3)
    pano_id:str=Field(min_length=1,max_length=150)
    heading:float
    pitch:float=Field(ge=-90,le=90)
    cohort:Literal['high','control','unverified']='unverified'
    metrics:Metrics|None=None

class Catalog(BaseModel):
    points:list[Point]=Field(min_length=2,max_length=500)
    story:dict=Field(default_factory=lambda:dict(features=[],metadata=None))

class MapsKey(BaseModel):
    key:str=Field(max_length=200)

def origin(request):
    o=request.headers.get('origin')
    own=str(request.base_url).rstrip('/')
    if o and o not in ALLOWED_ORIGINS and o!=own: raise HTTPException(403,'Origen no autorizado')

def admin(request):
    if not ADMIN_TOKEN: raise HTTPException(503,'Configura ADMIN_TOKEN antes de usar el panel privado')
    token=request.headers.get('authorization','').removeprefix('Bearer ')
    if not hmac.compare_digest(sha(token),sha(ADMIN_TOKEN)): raise HTTPException(401,'Clave privada no válida')

def catalog(con):
    rows=con.execute('SELECT * FROM study_points WHERE active=1 ORDER BY id').fetchall()
    if not rows:return DEMO
    return [{**dict(r),'metrics':json.loads(r['metrics_json']) if r['metrics_json'] else None} for r in rows]

def session(con,request):
    token=request.cookies.get('apie_session')
    s=con.execute('SELECT * FROM study_sessions WHERE token_hash=?',(sha(token or ''),)).fetchone()
    if not s:raise HTTPException(401,'No hay una participación activa')
    return dict(s)

def trials(con,sid):return [dict(r) for r in con.execute('SELECT * FROM study_trials WHERE session_id=? ORDER BY round',(sid,))]
def public_point(p):return {k:p[k] for k in ('id','lat','lon','pano_id','heading','pitch')}
def session_view(con,s):return dict(id=s['id'],study_mode=s['study_mode'],trials=[dict(id=t['id'],round=t['round'],left=public_point(json.loads(t['left_snapshot'])),right=public_point(json.loads(t['right_snapshot'])),choice=t['choice']) for t in trials(con,s['id'])])

@app.get('/api/health')
def health():
    with connection() as con:con.execute('SELECT 1').fetchone()
    return dict(status='ok',storage='sqlite-wal')

@app.get('/api/config')
def config():
    with connection() as con:r=con.execute("SELECT value FROM study_settings WHERE key='maps_key'").fetchone()
    return dict(maps_key=os.getenv('GOOGLE_MAPS_API_KEY','') or (r['value'] if r else ''),rounds=5)

@app.get('/api/session')
def get_session(request:Request):
    with connection() as con:return session_view(con,session(con,request))

@app.post('/api/session',status_code=201)
def create_session(profile:Profile,request:Request,response:Response):
    origin(request)
    if profile.urban=='Sí' and not (profile.city or '').strip():raise HTTPException(400,'Indica tu ciudad')
    sid,token=str(uuid4()),secrets.token_urlsafe(48)
    with connection(write=True) as con:
        pts=catalog(con)
        high=[p for p in pts if p['cohort']=='high'];controls=[p for p in pts if p['cohort']=='control']
        secrets.SystemRandom().shuffle(high);secrets.SystemRandom().shuffle(controls)
        real=len(high)>=5 and len(controls)>=5
        con.execute('INSERT INTO study_sessions VALUES (?,?,?,?,?,?,?,?,?,?)',(sid,sha(token),profile.age_range,profile.gender,profile.urban,profile.city.strip() if profile.urban=='Sí' else None,'pilot-v1','study' if real else 'demo',sha(j(pts)),now()))
        pair=[next((p for p in pts if p['id']=='demo-a'),pts[0]),next((p for p in pts if p['id']=='demo-b'),pts[1])]
        for n in range(1,6):
            a,b=(high[n-1],controls[n-1]) if real else pair
            if secrets.randbelow(2):a,b=b,a
            con.execute('INSERT INTO study_trials (id,session_id,round,left_id,right_id,left_snapshot,right_snapshot) VALUES (?,?,?,?,?,?,?)',(str(uuid4()),sid,n,a['id'],b['id'],j(a),j(b)))
        answer=session_view(con,dict(id=sid,study_mode='study' if real else 'demo'))
    secure=os.getenv('COOKIE_SECURE','0')=='1'
    response.set_cookie('apie_session',token,httponly=True,secure=secure,samesite='none' if secure else 'lax',max_age=2592000)
    if secure: response.headers['set-cookie'] += '; Partitioned'
    return answer

@app.post('/api/vote')
def save_vote(vote:Vote,request:Request):
    origin(request)
    if set(vote.reasons)-REASONS:raise HTTPException(400,'Motivo no válido')
    if len(j(vote.view))>4000:raise HTTPException(400,'Información de vista demasiado extensa')
    with connection(write=True) as con:
        s=session(con,request);rows=trials(con,s['id']);t=next((t for t in rows if t['id']==vote.trial_id),None)
        if not t:raise HTTPException(404,'Comparación no encontrada')
        if t['choice']:
            if t['choice']!=vote.choice:raise HTTPException(409,'La comparación ya tiene otra respuesta')
            return session_view(con,s)
        if any(r['round']<t['round'] and not r['choice'] for r in rows):raise HTTPException(409,'Responde primero la comparación anterior')
        con.execute('UPDATE study_trials SET choice=?,reasons_json=?,duration_ms=?,view_json=?,answered_at=? WHERE id=? AND session_id=? AND choice IS NULL',(vote.choice,j(list(dict.fromkeys(vote.reasons))),vote.duration_ms,j(vote.view),now(),t['id'],s['id']))
        return session_view(con,s)

def comparable(a,b):
    ma,mb=a['metrics'],b['metrics']
    return bool(ma and mb and ma.get('verified',True) and mb.get('verified',True) and all(ma[k]==mb[k] for k in ('radius_m','year_start','year_end','version','definition','quality')) and ma['accidents']!=mb['accidents'])

@app.get('/api/results')
def results(request:Request):
    with connection() as con:
        s=session(con,request);rows=trials(con,s['id'])
        if any(t['choice'] is None for t in rows):raise HTTPException(403,'Termina las cinco comparaciones')
        points={};preferences={};n=agreement=0
        for t in rows:
            a,b=json.loads(t['left_snapshot']),json.loads(t['right_snapshot']);points[a['id']]=a;points[b['id']]=b
            if t['choice'] in ('left','right'):
                selected,other=(a,b) if t['choice']=='left' else (b,a)
                preferences[selected['id']]=preferences.get(selected['id'],0)+1
                if comparable(a,b):n+=1;agreement+=selected['metrics']['accidents']<other['metrics']['accidents']
        st=con.execute("SELECT value FROM study_settings WHERE key='story'").fetchone()
        return dict(summary=dict(answered=5,decisive=sum(preferences.values()),comparable=n,agreements=agreement,preferences=preferences),study_mode=s['study_mode'],points=list(points.values()),rounds=[{k:t[k] for k in ('round','left_id','right_id','choice')} for t in rows],story=json.loads(st['value']) if st else dict(features=[],metadata=None))

@app.get('/api/admin/export')
def export(request:Request):
    admin(request)
    with connection() as con:
        sessions=[{k:v for k,v in dict(r).items() if k!='token_hash'} for r in con.execute('SELECT * FROM study_sessions ORDER BY created_at')]
        return dict(schema_version=1,exported_at=now(),sessions=sessions,trials=[dict(r) for r in con.execute('SELECT * FROM study_trials ORDER BY session_id,round')],points=catalog(con))

@app.post('/api/admin/catalog')
def set_catalog(payload:Catalog,request:Request):
    origin(request);admin(request)
    if len({p.id for p in payload.points})!=len(payload.points):raise HTTPException(400,'Identificadores repetidos')
    features=payload.story.get('features',[])
    if len(features)>10000:raise HTTPException(400,'El mapa admite un máximo de 10.000 puntos agregados')
    for f in features:
        try:
            lon,lat=f['geometry']['coordinates'];n=f['properties']['accidents']
            assert f['type']=='Feature' and f['geometry']['type']=='Point' and 40<=lat<=41 and -4.2<=lon<=-3 and isinstance(n,int) and n>=0 and isinstance(f['properties']['label'],str)
        except (KeyError,ValueError,AssertionError,TypeError):raise HTTPException(400,'El mapa no es válido')
    for p in payload.points:
        if p.metrics and p.metrics.year_start>p.metrics.year_end:raise HTTPException(400,'Periodo no válido')
    with connection(write=True) as con:
        con.execute('UPDATE study_points SET active=0')
        for pt in payload.points:
            p=pt.model_dump()
            con.execute('INSERT INTO study_points VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET label=excluded.label,lat=excluded.lat,lon=excluded.lon,pano_id=excluded.pano_id,heading=excluded.heading,pitch=excluded.pitch,cohort=excluded.cohort,active=1,metrics_json=excluded.metrics_json,updated_at=excluded.updated_at',(p['id'],p['label'],p['lat'],p['lon'],p['pano_id'],p['heading'],p['pitch'],p['cohort'],1,j(p['metrics']) if p['metrics'] else None,now()))
        con.execute("INSERT INTO study_settings VALUES ('story',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(j(payload.story),))
    return dict(points=len(payload.points),map_points=len(features),updated_at=now())

@app.post('/api/admin/maps')
def set_maps(payload:MapsKey,request:Request):
    origin(request);admin(request)
    with connection(write=True) as con:con.execute("INSERT INTO study_settings VALUES ('maps_key',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(payload.key.strip(),))
    return dict(saved=True)
