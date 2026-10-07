"""Preparación espacial y análisis reproducible del estudio A pie.

No requiere DuckDB Spatial: mide en EPSG:25830 usando pyproj y cKDTree.
Los accidentes se cuentan en accidentes_todos, sin uniones a personas_todos.
"""
from __future__ import annotations
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

DEFINITION='unique_accident_with_pedestrian_police_record'
QUALITY='high|medium;apto_mapa=true'
TO_UTM=Transformer.from_crs(4326,25830,always_xy=True)
TO_WGS=Transformer.from_crs(25830,4326,always_xy=True)
DEMO_POINTS=[
 dict(id='demo-a',label='Punto A · Madrid',lat=40.4331538,lon=-3.7040872,pano_id='4XV5XZ4Vo7SQAULn992JrQ',heading=195.89313310418282,pitch=3.8884,cohort='unverified',coordinates_reviewed=False),
 dict(id='demo-b',label='Punto B · Madrid',lat=40.4328741,lon=-3.704739,pano_id='VoK_pFOJdaEOzFov2O1FUg',heading=0,pitch=0,cohort='unverified',coordinates_reviewed=False),
]

def load_accidents(db_path,year_start=2019,year_end=2025,exclude_years=()):
    path=Path(db_path)
    if not path.is_file():raise FileNotFoundError(f'No existe la base de datos: {path}. Ejecuta el cuaderno en el ordenador que contiene el archivo.')
    with duckdb.connect(str(path),read_only=True) as con:
        columns=set(con.execute('DESCRIBE accidentes_todos').fetchdf()['column_name'])
        required={'accident_uid','year','con_peaton','apto_mapa','geolocation_quality','x_final','y_final','lat','lon'}
        if required-columns:raise ValueError(f'Faltan columnas: {sorted(required-columns)}')
        # Una fila por accidente, antes de cualquier cálculo espacial.
        df=con.execute('''SELECT accident_uid, year, location_raw, distrito,
          x_final, y_final, lat, lon, geolocation_quality
          FROM accidentes_todos WHERE con_peaton=TRUE AND apto_mapa=TRUE
          AND geolocation_quality IN ('high','medium') AND year BETWEEN ? AND ?
          AND x_final IS NOT NULL AND y_final IS NOT NULL''',[year_start,year_end]).fetchdf()
        coverage=con.execute('''SELECT year,COUNT(DISTINCT accident_uid) total_accidents,
          COUNT(DISTINCT CASE WHEN con_peaton THEN accident_uid END) pedestrian_accidents,
          COUNT(DISTINCT CASE WHEN con_peaton AND apto_mapa AND geolocation_quality IN ('high','medium') THEN accident_uid END) mapped_pedestrian_accidents
          FROM accidentes_todos GROUP BY year ORDER BY year''').fetchdf()
    if df.accident_uid.duplicated().any():raise ValueError('accidentes_todos contiene accident_uid repetidos: revísalos antes del análisis.')
    if exclude_years:df=df[~df.year.isin(exclude_years)].copy()
    finite=np.isfinite(df[['x_final','y_final']].to_numpy(dtype=float)).all(axis=1)
    df=df.loc[finite].reset_index(drop=True)
    if df.empty:raise ValueError('No hay accidentes aptos para el mapa en el periodo seleccionado.')
    coverage['mapped_pct']=100*coverage.mapped_pedestrian_accidents/coverage.pedestrian_accidents.replace(0,np.nan)
    return df,coverage

def dataset_version(df,year_start,year_end,radius_m,exclude_years=()):
    digest=hashlib.sha256()
    digest.update(json.dumps([year_start,year_end,radius_m,sorted(exclude_years),DEFINITION,QUALITY]).encode())
    # Incluye el contenido espacial, no solo el nombre del archivo o la fecha.
    stable=df[['accident_uid','x_final','y_final']].sort_values('accident_uid')
    digest.update(pd.util.hash_pandas_object(stable,index=False).to_numpy().tobytes())
    return digest.hexdigest()[:24]

def point_metrics(df,points,radius_m=25,year_start=2019,year_end=2025,exclude_years=()):
    if radius_m<=0:raise ValueError('El radio debe ser positivo')
    if not len(points):raise ValueError('Añade al menos una ubicación')
    xy=df[['x_final','y_final']].to_numpy(dtype=float)
    tree=cKDTree(xy)
    version=dataset_version(df,year_start,year_end,radius_m,exclude_years)
    output=[]
    for point in points:
        p=dict(point)
        if not (-4.2<=float(p['lon'])<=-3 and 40<=float(p['lat'])<=41):raise ValueError(f'Coordenadas fuera del entorno de Madrid: {p["id"]}')
        x,y=TO_UTM.transform(float(p['lon']),float(p['lat']))
        idx=tree.query_ball_point([x,y],radius_m)
        sample=df.iloc[idx]
        metric=dict(accidents=int(sample.accident_uid.nunique()),radius_m=float(radius_m),year_start=int(year_start),year_end=int(year_end),version=version,definition=DEFINITION,quality=QUALITY,verified=str(p.get('coordinates_reviewed',False)).strip().lower()=='true',excluded_years=list(exclude_years))
        p.update(x_utm=x,y_utm=y,metrics=metric)
        output.append(p)
    return output

def hotspot_candidates(df,radius_m=25,n=100,min_distance_m=None):
    """Centros candidatos en coordenadas de accidentes y selección sin solapes.

    No es un ranking oficial de cruces: es una regla espacial explícita.
    Separación >=2R impide que el top 5 muestre cinco centros del mismo entorno.
    """
    min_distance_m=max(2*radius_m,min_distance_m or 0)
    xy=df[['x_final','y_final']].to_numpy(dtype=float)
    candidates=np.unique(xy,axis=0)
    tree=cKDTree(xy)
    counts=tree.query_ball_point(candidates,radius_m,return_length=True)
    order=np.lexsort((candidates[:,1],candidates[:,0],-counts))
    selected=[];records=[]
    for k in order:
        center=candidates[k]
        if selected and np.min(np.linalg.norm(np.asarray(selected)-center,axis=1))<min_distance_m:continue
        selected.append(center)
        lon,lat=TO_WGS.transform(*center)
        nearest=tree.query(center)[1]
        row=df.iloc[nearest]
        records.append(dict(id=f'hotspot-{len(records)+1:03d}',label=str(row.location_raw),distrito=str(row.distrito),lat=lat,lon=lon,x_utm=center[0],y_utm=center[1],accidents=int(counts[k]),radius_m=radius_m,pano_id='',heading=0,pitch=0,cohort='high',coordinates_reviewed=False))
        if len(records)>=n:break
    return pd.DataFrame(records)

def story_geojson(df,hotspots,radius_m,year_start,year_end,exclude_years=()):
    # Mapa de toda la muestra en celdas de 50 m; ranking por buffers independiente.
    metadata=dict(radius_m=radius_m,year_start=year_start,year_end=year_end,excluded_years=list(exclude_years),definition=DEFINITION,quality=QUALITY,version=dataset_version(df,year_start,year_end,radius_m,exclude_years),method='centers_at_accident_coordinates;greedy_separation_at_least_2R',source='Accidentes con intervención de Policía Municipal; accidentes_todos',mapped_accidents=int(len(df)),map_grid_m=50)
    features=[dict(type='Feature',geometry=dict(type='Point',coordinates=[float(r.lon),float(r.lat)]),properties=dict(id=r.id,label=r.label,accidents=int(r.accidents),distrito=r.distrito)) for r in hotspots.itertuples()]
    hotspot_features=features
    grid=df.copy()
    grid['gx']=np.floor(grid.x_final/50).astype(int)
    grid['gy']=np.floor(grid.y_final/50).astype(int)
    cells=grid.groupby(['gx','gy']).agg(accidents=('accident_uid','nunique'),distrito=('distrito','first')).reset_index()
    map_features=[]
    for c in cells.itertuples():
        lon,lat=TO_WGS.transform((c.gx+.5)*50,(c.gy+.5)*50)
        map_features.append(dict(type='Feature',geometry=dict(type='Point',coordinates=[float(lon),float(lat)]),properties=dict(label=f'Celda de 50 m · {c.distrito}',accidents=int(c.accidents))))
    assert sum(f['properties']['accidents'] for f in map_features)==len(df)
    return dict(type='FeatureCollection',metadata=metadata,features=map_features,hotspots=hotspot_features)

def export_catalog(points,story,path):
    ids=set();clean=[]
    for p in points:
        if p['id'] in ids:raise ValueError('IDs de ubicaciones repetidos')
        ids.add(p['id'])
        if not p.get('pano_id'):raise ValueError(f'Falta el panorama de {p["id"]}. Selecciónalo antes de incluirlo en la encuesta.')
        clean.append({k:p[k] for k in ('id','label','lat','lon','pano_id','heading','pitch','cohort','metrics')})
    payload=dict(points=clean,story=story)
    Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return payload

def write_analysis_tables(db_path,points,story):
    """Añade solo tablas pc_*; las tablas originales de accidentes no se alteran.

    Cerrar conexiones de lectura y el visor local antes de abrir en escritura.
    La operación es transaccional; repetir reemplaza únicamente las métricas
    de los IDs del catálogo actual y añade versiones históricas del mapa.
    """
    with duckdb.connect(str(db_path)) as con:
        con.execute('BEGIN TRANSACTION')
        try:
            con.execute('''CREATE TABLE IF NOT EXISTS pc_points (
              point_id VARCHAR PRIMARY KEY,label VARCHAR,lat DOUBLE,lon DOUBLE,
              x_utm DOUBLE,y_utm DOUBLE,pano_id VARCHAR,heading DOUBLE,pitch DOUBLE,
              cohort VARCHAR,coordinates_reviewed BOOLEAN,updated_at TIMESTAMP)''')
            con.execute('''CREATE TABLE IF NOT EXISTS pc_point_metrics (
              point_id VARCHAR,metric_version VARCHAR,year_start INTEGER,year_end INTEGER,
              radius_m DOUBLE,accidents INTEGER,definition VARCHAR,quality VARCHAR,
              verified BOOLEAN,excluded_years_json VARCHAR,computed_at TIMESTAMP,
              PRIMARY KEY(point_id,metric_version))''')
            con.execute('''CREATE TABLE IF NOT EXISTS pc_story (
              metric_version VARCHAR PRIMARY KEY,geojson VARCHAR,computed_at TIMESTAMP)''')
            for p in points:
                m=p['metrics']
                con.execute('''INSERT INTO pc_points VALUES (?,?,?,?,?,?,?,?,?,?,?,current_timestamp)
                  ON CONFLICT(point_id) DO UPDATE SET label=excluded.label,lat=excluded.lat,
                  lon=excluded.lon,x_utm=excluded.x_utm,y_utm=excluded.y_utm,pano_id=excluded.pano_id,
                  heading=excluded.heading,pitch=excluded.pitch,cohort=excluded.cohort,
                  coordinates_reviewed=excluded.coordinates_reviewed,updated_at=now()''',
                  [p['id'],p['label'],p['lat'],p['lon'],p['x_utm'],p['y_utm'],p['pano_id'],p['heading'],p['pitch'],p['cohort'],m['verified']])
                con.execute('''INSERT INTO pc_point_metrics VALUES (?,?,?,?,?,?,?,?,?,?,current_timestamp)
                  ON CONFLICT(point_id,metric_version) DO UPDATE SET accidents=excluded.accidents,
                  verified=excluded.verified,computed_at=now()''',
                  [p['id'],m['version'],m['year_start'],m['year_end'],m['radius_m'],m['accidents'],m['definition'],m['quality'],m['verified'],json.dumps(m.get('excluded_years',[]))])
            con.execute('''INSERT INTO pc_story VALUES (?,?,current_timestamp)
              ON CONFLICT(metric_version) DO UPDATE SET geojson=excluded.geojson,computed_at=now()''',
              [story['metadata']['version'],json.dumps(story,ensure_ascii=False,allow_nan=False)])
            con.execute('COMMIT')
        except Exception:
            con.execute('ROLLBACK');raise

def read_responses(path):
    payload=json.loads(Path(path).read_text(encoding='utf-8'))
    if payload.get('schema_version')!=1:raise ValueError('Versión de exportación no compatible')
    sessions=pd.DataFrame(payload.get('sessions',[]));trials=pd.DataFrame(payload.get('trials',[]))
    if sessions.empty or trials.empty:return sessions,pd.DataFrame()
    if sessions.id.duplicated().any() or trials.id.duplicated().any():raise ValueError('IDs duplicados en la exportación')
    rows=[]
    for t in trials.to_dict('records'):
        if not t.get('choice'):continue
        a=json.loads(t['left_snapshot']);b=json.loads(t['right_snapshot'])
        ma,mb=a.get('metrics'),b.get('metrics')
        comparable=bool(ma and mb and ma.get('verified',True) and mb.get('verified',True) and all(ma.get(k)==mb.get(k) for k in ('version','year_start','year_end','radius_m','definition','quality')) and ma['accidents']!=mb['accidents'])
        decisive=t['choice'] in ('left','right');selected=a if t['choice']=='left' else b if t['choice']=='right' else None
        other=b if t['choice']=='left' else a if t['choice']=='right' else None
        pair='|'.join(sorted([a['id'],b['id']]))
        rows.append(dict(**t,pair_key=pair,left_accidents=ma['accidents'] if ma else np.nan,right_accidents=mb['accidents'] if mb else np.nan,metric_version=ma['version'] if ma and mb and ma['version']==mb['version'] else None,selected_point=selected['id'] if selected else None,other_point=other['id'] if other else None,decisive=decisive,comparable=comparable,agreement=(selected['metrics']['accidents']<other['metrics']['accidents']) if comparable and decisive else np.nan,duration_seconds=(t['duration_ms'] or 0)/1000,reasons=json.loads(t.get('reasons_json') or '[]')))
    votes=pd.DataFrame(rows)
    if votes.empty:return sessions,votes
    votes=votes.merge(sessions.rename(columns={'id':'session_id'}),on='session_id',how='left',validate='many_to_one')
    votes['repeated_pair']=votes.duplicated(['session_id','pair_key'],keep=False)
    votes['very_fast_flag']=votes.duration_seconds<1.5
    complete=votes.groupby('session_id').size().eq(5)
    votes['complete_session']=votes.session_id.map(complete)
    return sessions,votes

def analytic_sample(votes,include_demo=False,complete_only=True):
    if votes.empty:return votes.copy()
    keep=pd.Series(True,index=votes.index)
    if not include_demo:keep &= votes.study_mode.eq('study')
    if complete_only:keep &= votes.complete_session
    return votes.loc[keep].copy()

def preference_table(votes,group_by=()):
    if votes.empty:return pd.DataFrame()
    rows=[]
    for t in votes.to_dict('records'):
        for side in ('left','right'):
            p=json.loads(t[side+'_snapshot']);m=p.get('metrics') or {}
            rows.append(dict(point_id=p['id'],label=p['label'],session_id=t['session_id'],metric_version=m.get('version','unverified'),accidents=m.get('accidents',np.nan),chosen=int(t['choice']==side),decisive=int(t['decisive']),tie=int(t['choice']=='tie'),skip=int(t['choice']=='skip'),**{g:t[g] for g in group_by}))
    df=pd.DataFrame(rows)
    keys=['point_id','label','metric_version',*group_by]
    out=df.groupby(keys,dropna=False).agg(appearances=('chosen','size'),choices=('chosen','sum'),decisive=('decisive','sum'),participants=('session_id','nunique'),ties=('tie','sum'),skips=('skip','sum'),accidents=('accidents','first')).reset_index()
    out['preference_pct']=100*out.choices/out.decisive.replace(0,np.nan)
    return out

def cluster_interval(votes,field='agreement',n_bootstrap=2000,seed=42):
    """Intervalo bootstrap por participación, no por voto individual."""
    if votes.empty:return dict(n_participants=0,n_votes=0,estimate=None,ci95=None)
    df=votes.loc[votes[field].notna(),['session_id',field]].copy();df[field]=df[field].astype(float)
    by=df.groupby('session_id')[field].agg(['sum','count'])
    if by.empty:return dict(n_participants=0,n_votes=0,estimate=None,ci95=None)
    estimate=float(by['sum'].sum()/by['count'].sum())
    if len(by)<2:return dict(n_participants=len(by),n_votes=int(by['count'].sum()),estimate=estimate,ci95=None)
    arr=by[['sum','count']].to_numpy();rng=np.random.default_rng(seed)
    # Lotes evitan asignar una matriz 2000 x todos los participantes.
    boot=[]
    for _ in range(n_bootstrap):
        sample=arr[rng.integers(0,len(arr),size=len(arr))]
        boot.append(sample[:,0].sum()/sample[:,1].sum())
    return dict(n_participants=len(by),n_votes=int(by['count'].sum()),estimate=estimate,ci95=np.quantile(boot,[.025,.975]).tolist())

def bradley_terry(votes):
    """Ranking exploratorio regularizado por componentes de comparación.

    No comparar scores entre componentes desconectados. No produce p-valores.
    La constante mide la preferencia por la escena izquierda.
    """
    from sklearn.linear_model import LogisticRegression
    if votes.empty:return pd.DataFrame(),dict(status='no_data')
    decisive=votes[votes.decisive].copy()
    if len(decisive)<20:return pd.DataFrame(),dict(status='insufficient_votes',minimum=20)
    adjacency=defaultdict(set)
    for t in decisive.itertuples():adjacency[t.left_id].add(t.right_id);adjacency[t.right_id].add(t.left_id)
    remaining=set(adjacency);components=[]
    while remaining:
        root=min(remaining);todo=[root];component=set()
        while todo:
            point=todo.pop()
            if point in component:continue
            component.add(point);todo.extend(adjacency[point]-component)
        components.append(sorted(component));remaining-=component
    output=[];diagnostics=[]
    for num,nodes in enumerate(components,1):
        d=decisive[decisive.left_id.isin(nodes)&decisive.right_id.isin(nodes)]
        y=d.choice.eq('left').astype(int).to_numpy()
        if len(np.unique(y))<2:diagnostics.append(dict(component=num,status='only_one_response_side'));continue
        lookup={p:i for i,p in enumerate(nodes)};X=np.zeros((len(d),len(nodes)))
        for row,t in enumerate(d.itertuples()):X[row,lookup[t.left_id]]=1;X[row,lookup[t.right_id]]=-1
        model=LogisticRegression(C=1.0,fit_intercept=True,max_iter=3000,solver='lbfgs').fit(X,y)
        scores=model.coef_[0];scores=scores-scores.mean()
        output.extend(dict(point_id=p,component=num,score=float(score),votes=int(len(d))) for p,score in zip(nodes,scores))
        diagnostics.append(dict(component=num,points=len(nodes),votes=len(d),left_bias_log_odds=float(model.intercept_[0])))
    table=pd.DataFrame(output)
    if not table.empty:table=table.sort_values(['component','score'],ascending=[True,False])
    return table,dict(status='exploratory',components=len(components),diagnostics=diagnostics)

def association_model(votes):
    """Asociación descriptiva, con error estándar agrupado por participación.
    Resultado: elige izquierda. Predictor: log(1+accidentes derecha)-log(1+accidentes izquierda).
    No mide causalidad ni riesgo: no dispone de exposición peatonal o tráfico.
    """
    import statsmodels.api as sm
    d=votes[votes.decisive & votes.comparable].copy() if not votes.empty else pd.DataFrame()
    if len(d)<100 or d.session_id.nunique()<20:return None,'Se requieren al menos 100 elecciones comparables y 20 participaciones para este modelo exploratorio.'
    x=np.log1p(d.right_accidents)-np.log1p(d.left_accidents)
    if x.nunique()<2 or d.choice.nunique()<2:return None,'No hay variación suficiente para ajustar el modelo.'
    X=sm.add_constant(pd.DataFrame({'delta_log_accidents':x}))
    fit=sm.GLM(d.choice.eq('left').astype(int),X,family=sm.families.Binomial()).fit(cov_type='cluster',cov_kwds={'groups':d.session_id})
    return fit,'Asociación descriptiva; revisar separación, balance y sesgos de muestreo.'

def import_responses_duckdb(db_path,payload):
    """Replica una exportación para análisis. Nunca guarda cookies o hashes de acceso."""
    with duckdb.connect(str(db_path)) as con:
        con.execute('BEGIN TRANSACTION')
        try:
            con.execute('CREATE TABLE IF NOT EXISTS pc_sessions (session_id VARCHAR PRIMARY KEY,age_range VARCHAR,gender VARCHAR,urban VARCHAR,city VARCHAR,study_mode VARCHAR,created_at VARCHAR,catalog_hash VARCHAR)')
            con.execute('''CREATE TABLE IF NOT EXISTS pc_trials (trial_id VARCHAR PRIMARY KEY,session_id VARCHAR,round INTEGER,left_id VARCHAR,right_id VARCHAR,left_snapshot VARCHAR,right_snapshot VARCHAR,choice VARCHAR,reasons_json VARCHAR,duration_ms BIGINT,view_json VARCHAR,answered_at VARCHAR)''')
            for s in payload.get('sessions',[]):
                con.execute('''INSERT INTO pc_sessions VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(session_id) DO NOTHING''',[s['id'],s['age_range'],s['gender'],s['urban'],s.get('city'),s['study_mode'],s['created_at'],s['catalog_hash']])
            for t in payload.get('trials',[]):
                con.execute('''INSERT INTO pc_trials VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(trial_id) DO UPDATE SET choice=excluded.choice,reasons_json=excluded.reasons_json,duration_ms=excluded.duration_ms,view_json=excluded.view_json,answered_at=excluded.answered_at''',[t[k] for k in ('id','session_id','round','left_id','right_id','left_snapshot','right_snapshot','choice','reasons_json','duration_ms','view_json','answered_at')])
            con.execute('COMMIT')
        except Exception:con.execute('ROLLBACK');raise
