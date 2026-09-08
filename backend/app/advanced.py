"""Reproducible Phase 3 decision support. Every run is an immutable snapshot."""
import calendar
import math
import statistics
from datetime import date, timedelta
from decimal import Decimal, localcontext
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from .db import Record, User, now
from .security import audit, current_user, db_session, require
from .market import StrictInput, accessible, get, points, public, records

router = APIRouter(prefix='/api/v1/advanced', tags=['Advanced intelligence'])
SOURCE_KINDS = {'document', 'price', 'event', 'supplier', 'rfi', 'advanced_analysis', 'external_evidence'}
FACTORS = {'financial': 25, 'delivery': 25, 'quality': 20, 'geopolitical': 15, 'concentration': 15}


def authorize(db, user, row, seen=None):
    seen = set() if seen is None else seen
    if not accessible(user, row): return False
    if row.id in seen: return True
    seen.add(row.id)
    for citation in row.data.get('citations', []):
        if citation.get('kind') == 'mcp':
            if user.role not in ('Buyer', 'Market Intelligence Analyst') or citation.get('region') != user.region: return False
        elif not authorize(db, user, db.get(Record, citation.get('id')), seen): return False
    return all(authorize(db, user, db.get(Record, sid), seen) for sid in row.data.get('source_ids', []))


def sources(db, user, ids):
    result = []
    for sid in dict.fromkeys(ids):
        row = get(db, user, sid)
        if row.kind not in SOURCE_KINDS or not authorize(db, user, row):
            raise HTTPException(404, 'Sumber tidak tersedia untuk pengguna ini.')
        result.append({'id': row.id, 'kind': row.kind, 'title': row.data.get('name', row.data.get('title', row.id)),
                       'updated_at': row.updated_at, 'is_demo': bool(row.data.get('is_demo')),
                       'classification': row.classification})
    return result


def save(db, user, variant, data, source_ids):
    refs = sources(db, user, source_ids)
    classification = 'RESTRICTED' if any(r['classification'] == 'RESTRICTED' for r in refs) else 'CONFIDENTIAL'
    row = Record(kind='advanced_analysis', region=user.region, owner=user.id, classification=classification,
                 data={**data, 'variant': variant, 'source_ids': list(dict.fromkeys(source_ids)), 'sources': refs,
                       'is_demo': bool(data.get('is_demo')) or any(r['is_demo'] for r in refs),
                       'shared_with': [], 'created_at': now(), 'status': 'DRAFT', 'method_version': 'phase3-v1'})
    db.add(row); db.flush(); audit(db, user, 'advanced.' + variant + '.created', row.id); db.commit()
    return public(row)


def analysis(db, user, id, variant=None, lock=False):
    require(user, 'procurement')
    row = get(db, user, id, 'advanced_analysis', lock=lock)
    if not authorize(db, user, row): raise HTTPException(404, 'Sumber analisis tidak lagi dapat diakses.')
    if variant and row.data.get('variant') != variant: raise HTTPException(422, 'Jenis analisis tidak sesuai.')
    return row


@router.get('/analyses')
def listing(user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement')
    return [public(r) for r in records(db, user, 'advanced_analysis') if r.data.get('variant') and authorize(db, user, r)]


@router.get('/analyses/{id}')
def detail(id: str, user=Depends(current_user), db=Depends(db_session)):
    return public(analysis(db, user, id))


class Sharing(StrictInput):
    user_ids: list[str] = Field(max_length=30)


@router.put('/analyses/{id}/sharing')
def sharing(id: str, body: Sharing, user=Depends(current_user), db=Depends(db_session)):
    row = analysis(db, user, id, lock=True)
    if row.owner != user.id: raise HTTPException(403, 'Hanya pemilik dapat membagikan analisis.')
    for sid in body.user_ids:
        recipient = db.get(User, sid)
        if not recipient or not recipient.active or recipient.region != user.region or recipient.role not in ('Buyer', 'Market Intelligence Analyst'):
            raise HTTPException(422, 'Penerima harus Buyer atau Analyst aktif di region yang sama.')
        if row.classification == 'RESTRICTED' and sid != user.id: raise HTTPException(403, 'Analisis RESTRICTED hanya untuk pemilik.')
        sources(db, recipient, row.data.get('source_ids', []))
    row.data = {**row.data, 'shared_with': list(dict.fromkeys(body.user_ids))}; row.updated_at = now()
    audit(db, user, 'advanced.sharing', id, {'recipients': body.user_ids}); db.commit(); return public(row)


class Component(StrictInput):
    name: str = Field(min_length=2, max_length=100)
    bucket: Literal['raw_material', 'labor', 'energy', 'logistics', 'other']
    quantity: Decimal = Field(gt=0, le=1e9, max_digits=24, decimal_places=8)
    rate: Decimal = Field(ge=0, le=1e12, max_digits=24, decimal_places=8)
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    fx_rate: Decimal = Field(gt=0, le=1e9, max_digits=24, decimal_places=8)
    basis: str = Field(min_length=5, max_length=1000)
    as_of: date
    source_id: str = ''


class CostInput(StrictInput):
    name: str = Field(min_length=3, max_length=150)
    category_id: str
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    output_unit: str = Field(min_length=1, max_length=50)
    components: list[Component] = Field(min_length=1, max_length=50)
    margin_pct: Decimal = Field(ge=0, lt=100, max_digits=8, decimal_places=4)
    margin_method: Literal['markup', 'gross_margin'] = 'markup'
    assumptions: str = Field(min_length=10, max_length=5000)
    parent_id: str = ''


def calculate_cost(model, shocks=None, fx_change=0, margin=None):
    with localcontext() as ctx:
        ctx.prec = 64
        return _calculate_cost(model, shocks, fx_change, margin)

def _calculate_cost(model, shocks=None, fx_change=0, margin=None):
    shocks = shocks or {}; components = []; subtotal = Decimal(0); currency = model['currency']
    for c in model['components']:
        amount = Decimal(str(c['quantity'])) * Decimal(str(c['rate'])) * Decimal(str(c['fx_rate']))
        amount *= 1 + Decimal(str(shocks.get(c['bucket'], 0))) / 100
        if c['currency'] != currency: amount *= 1 + Decimal(str(fx_change)) / 100
        subtotal += amount
        components.append({**c, 'cost': float(amount.quantize(Decimal('.000001')))})
    pct = Decimal(str(model['margin_pct'] if margin is None else margin)) / 100
    total = subtotal * (1 + pct) if model['margin_method'] == 'markup' else subtotal / (1 - pct)
    return {'components': components, 'subtotal': float(subtotal.quantize(Decimal('.000001'))),
            'supplier_margin': float((total - subtotal).quantize(Decimal('.000001'))),
            'total': float(total.quantize(Decimal('.000001')))}


@router.post('/cost-models')
def create_cost(body: CostInput, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); get(db, user, body.category_id, 'category')
    for c in body.components:
        if c.as_of > date.today(): raise HTTPException(422, 'Tanggal sumber biaya tidak boleh di masa depan.')
        if c.currency == body.currency and c.fx_rate != 1: raise HTTPException(422, 'FX mata uang yang sama harus 1.')
    parent = analysis(db, user, body.parent_id, 'cost_model') if body.parent_id else None
    if parent and parent.owner != user.id: raise HTTPException(403, 'Revisi model hanya oleh pemilik.')
    data = body.model_dump(mode='json')
    return save(db, user, 'cost_model', {**data, 'version': parent.data.get('version', 1) + 1 if parent else 1,
        'result': calculate_cost(data)}, [c.source_id for c in body.components if c.source_id] + ([parent.id] if parent else []))


class ScenarioInput(StrictInput):
    name: str = Field(min_length=3, max_length=150)
    model_id: str
    shocks: dict[Literal['raw_material', 'labor', 'energy', 'logistics', 'other'], float] = Field(default_factory=dict)
    fx_change_pct: float = Field(default=0, ge=-99, le=1000)
    margin_pct: float | None = Field(default=None, ge=0, lt=100)
    volume: float = Field(default=1, gt=0, le=1e12)
    assumptions: str = Field(min_length=10, max_length=5000)


@router.post('/scenarios')
def create_scenario(body: ScenarioInput, user=Depends(current_user), db=Depends(db_session)):
    model = analysis(db, user, body.model_id, 'cost_model')
    if any(not math.isfinite(v) or v < -100 or v > 1000 for v in body.shocks.values()): raise HTTPException(422, 'Shock harus -100 sampai 1000%.')
    result = calculate_cost(model.data, body.shocks, body.fx_change_pct, body.margin_pct)
    base = model.data['result']['total']; delta = result['total'] - base
    sensitivity = []
    for bucket in ('raw_material', 'labor', 'energy', 'logistics', 'other'):
        sensitivity.append({'factor': bucket, 'minus_10': calculate_cost(model.data, {bucket: -10})['total'],
                            'plus_10': calculate_cost(model.data, {bucket: 10})['total']})
    return save(db, user, 'scenario', {**body.model_dump(), 'category_id': model.data['category_id'],
        'currency': model.data['currency'], 'output_unit': model.data['output_unit'], 'result': result,
        'baseline': base, 'delta': delta, 'delta_pct': delta / base * 100 if base else None,
        'total_budget': result['total'] * body.volume, 'baseline_budget': base * body.volume, 'sensitivity': sensitivity}, [model.id])


def next_period(day, frequency, steps=1):
    if frequency in ('daily', 'weekly'): return day + timedelta(days=steps * (1 if frequency == 'daily' else 7))
    months = steps * (1 if frequency == 'monthly' else 3); index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def forecast_values(values, method, horizon, season):
    if method == 'naive': return [values[-1]] * horizon
    if method == 'drift': return [values[-1] + h * (values[-1] - values[0]) / (len(values) - 1) for h in range(1, horizon + 1)]
    return [values[-season + h % season] for h in range(horizon)]


def forecast_run(observations, frequency, horizon):
    if frequency not in ('daily', 'weekly', 'monthly', 'quarterly'): raise HTTPException(422, 'Forecast memerlukan frekuensi reguler.')
    if len(observations) < 18: raise HTTPException(422, 'Minimal 18 observasi reguler diperlukan untuk backtesting.')
    days = [date.fromisoformat(p['date']) for p in observations]
    for i in range(1, len(days)):
        # Monthly/quarterly series may be stamped at any day within their period.
        expected = next_period(days[i - 1], frequency)
        valid = days[i] == expected if frequency in ('daily', 'weekly') else (days[i].year, days[i].month) == (expected.year, expected.month)
        if not valid: raise HTTPException(422, 'Ada periode hilang atau duplikat. Lengkapi data sebelum forecasting.')
    values = [float(p['value']) for p in observations]; season = {'monthly': 12, 'quarterly': 4, 'daily': 7, 'weekly': 52}[frequency]
    methods = ['naive', 'drift'] + (['seasonal_naive'] if len(values) >= season * 2 + 6 else [])
    start = max(12, season * 2 if 'seasonal_naive' in methods else 12, len(values) - 24)
    scored = []
    for method in methods:
        errors = []; one_step = []
        for origin in range(start, len(values)):
            h = min(horizon, len(values) - origin)
            predictions = forecast_values(values[:origin], method, h, season)
            errors.extend(values[origin + j] - pred for j, pred in enumerate(predictions))
            one_step.append(values[origin] - predictions[0])
        scored.append({'model': method, 'mae': statistics.mean(abs(e) for e in errors),
            'rmse': math.sqrt(statistics.mean(e * e for e in errors)), 'origins': len(one_step), 'evaluations': len(errors)})
    selected = min(scored, key=lambda x: x['mae'])['model']; n = len(values)
    lag = season if selected == 'seasonal_naive' else 1
    drift = (values[-1] - values[0]) / (n - 1) if selected == 'drift' else 0
    residuals = [values[i] - values[i - lag] - drift for i in range(lag, n)]
    sigma = math.sqrt(sum(e * e for e in residuals) / (len(residuals) - (1 if selected == 'drift' else 0)))
    result = []
    for h, value in enumerate(forecast_values(values, selected, horizon, season), 1):
        scale = math.sqrt((h - 1) // season + 1) if selected == 'seasonal_naive' else math.sqrt(h * (1 + h / (n - 1))) if selected == 'drift' else math.sqrt(h)
        spread = sigma * scale
        result.append({'date': next_period(days[-1], frequency, h).isoformat(), 'value': value,
                       'lower_80': value - 1.2815515655 * spread, 'upper_80': value + 1.2815515655 * spread,
                       'lower_95': value - 1.9599639845 * spread, 'upper_95': value + 1.9599639845 * spread})
    return {'model': selected, 'backtest': scored, 'forecast': result, 'training_start': days[0].isoformat(),
            'training_end': days[-1].isoformat(), 'observations': n, 'history': observations,
            'methodology': 'Expanding-window rolling-origin validation; lowest multi-horizon MAE among eligible baselines. Normal 80/95% prediction intervals assume uncorrelated residuals; model-selection uncertainty is not included.',
            'limitations': ['Statistical baseline; no causal or macroeconomic predictors.', 'Validation selected the model; it is not an independent final holdout.', 'Intervals are approximate and may include negative values; no positivity clipping.']}


class ForecastInput(StrictInput):
    series_id: str
    horizon: int = Field(default=6, ge=1, le=24)
    as_of: date = Field(default_factory=date.today)


@router.post('/forecasts')
def create_forecast(body: ForecastInput, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); series = get(db, user, body.series_id, 'price')
    if body.as_of > date.today(): raise HTTPException(422, 'Cutoff tidak boleh di masa depan.')
    observations = points(db, series, end=body.as_of.isoformat())
    result = forecast_run(observations, series.data.get('frequency', 'irregular'), body.horizon)
    gap = (body.as_of - date.fromisoformat(result['training_end'])).days
    expected_days = {'daily': 1, 'weekly': 7, 'monthly': 31, 'quarterly': 92}[series.data['frequency']]
    result['stale'] = gap > expected_days * 2; result['stale_days'] = gap
    result['mean_source_confidence'] = statistics.mean(p.get('confidence', 1) for p in observations)
    return save(db, user, 'forecast', {**body.model_dump(mode='json'), 'name': series.data['name'] + ' — forecast',
        'category_id': series.data['category_id'], 'currency': series.data['currency'], 'unit': series.data['unit'],
        'frequency': series.data['frequency'], 'is_demo': bool(series.data.get('is_demo')), 'result': result}, [series.id])


class RiskFactor(StrictInput):
    factor: Literal['financial', 'delivery', 'quality', 'geopolitical', 'concentration']
    score: float | None = Field(default=None, ge=0, le=100)
    rationale: str = Field(min_length=10, max_length=2000)
    source_ids: list[str] = Field(default_factory=list, max_length=10)
    as_of: date


class RiskInput(StrictInput):
    supplier_id: str
    factors: list[RiskFactor] = Field(min_length=5, max_length=5)
    valid_days: int = Field(default=90, ge=1, le=365)


@router.post('/supplier-risks')
def create_risk(body: RiskInput, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); supplier = get(db, user, body.supplier_id, 'supplier')
    if {f.factor for f in body.factors} != set(FACTORS): raise HTTPException(422, 'Lima faktor risiko harus unik dan lengkap.')
    known = []; gaps = []
    for factor in body.factors:
        if factor.as_of > date.today(): raise HTTPException(422, 'Tanggal bukti tidak boleh di masa depan.')
        if factor.score is None or not factor.source_ids or (date.today() - factor.as_of).days > body.valid_days:
            gaps.append(factor.factor)
        else: known.append(factor)
    coverage = sum(FACTORS[f.factor] for f in known)
    score = sum(f.score * FACTORS[f.factor] for f in known) / coverage if coverage else None
    rating = 'INCOMPLETE' if coverage < 100 else ('HIGH' if score >= 70 else 'MEDIUM' if score >= 40 else 'LOW')
    return save(db, user, 'supplier_risk', {**body.model_dump(mode='json'), 'name': supplier.data['name'] + ' — risk assessment',
        'category_id': supplier.data.get('category_id'), 'weights': FACTORS, 'result': {'score': score, 'coverage_pct': coverage,
        'rating': rating, 'gaps': gaps,
        'expires_on': (min(f.as_of for f in body.factors) + timedelta(days=body.valid_days)).isoformat(),
        'methodology': 'Analyst-assessed risk 0–100, higher is riskier. Missing, unsourced or stale factors do not count as low risk; the partial score is provisional.'}},
        [supplier.id] + [sid for f in body.factors for sid in f.source_ids])


class Review(StrictInput):
    decision: Literal['APPROVED', 'REJECTED']
    rationale: str = Field(min_length=10, max_length=3000)


@router.post('/analyses/{id}/review')
def review(id: str, body: Review, user=Depends(current_user), db=Depends(db_session)):
    row = analysis(db, user, id, lock=True)
    if row.data['variant'] == 'supplier_risk': require(user, 'market:write')
    else: require(user, 'rfi:approve')
    row.data = {**row.data, 'status': body.decision, 'review': {'by': user.id, 'at': now(), **body.model_dump()},
                'reviews': [*row.data.get('reviews', []), {'by': user.id, 'at': now(), **body.model_dump()}]}
    row.updated_at = now(); audit(db, user, 'advanced.review', id, body.model_dump()); db.commit(); return public(row)


class RecommendationInput(StrictInput):
    name: str = Field(min_length=3, max_length=150)
    category_id: str
    forecast_id: str = ''
    scenario_id: str = ''
    risk_ids: list[str] = Field(default_factory=list, max_length=20)
    context: str = Field(min_length=10, max_length=5000)


@router.post('/recommendations')
def recommendation(body: RecommendationInput, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); get(db, user, body.category_id, 'category')
    ids = [i for i in [body.forecast_id, body.scenario_id, *body.risk_ids] if i]
    if not ids: raise HTTPException(422, 'Pilih minimal satu analisis sebagai bukti.')
    actions = []; gaps = []; evidence = []
    for sid in ids:
        row = analysis(db, user, sid); data = row.data; variant = data['variant']; result = data['result']
        expected = 'forecast' if sid == body.forecast_id else 'scenario' if sid == body.scenario_id else 'supplier_risk'
        if variant != expected or data.get('category_id') != body.category_id: raise HTTPException(422, 'Analisis harus sesuai jenis dan kategori rekomendasi.')
        evidence.append({'id': sid, 'title': data['name'], 'variant': variant, 'result': result, 'status': data['status']})
        if data.get('is_demo'):
            gaps.append(data['name'] + ': illustrative evidence cannot support a live procurement recommendation.'); continue
        if variant == 'forecast':
            current_age = (date.today() - date.fromisoformat(result['training_end'])).days
            max_age = {'daily': 2, 'weekly': 14, 'monthly': 62, 'quarterly': 184}[data['frequency']]
            if result['stale'] or current_age > max_age:
                gaps.append('Forecast memakai data lama atau demo; perbarui benchmark sebelum keputusan.'); continue
            latest = result['history'][-1]['value']; end = result['forecast'][-1]
            if end['lower_80'] > latest: action = 'Evaluate phased purchasing and request fixed-price options.'
            elif end['upper_80'] < latest: action = 'Compare shorter commitments and refreshed quotations against demand needs.'
            else: action = 'Maintain staged procurement; uncertainty does not support a directional timing decision.'
            actions.append({'action': action, 'reason': '80% forecast range compared with latest observed price.', 'source_ids': [sid]})
        elif variant == 'scenario':
            actions.append({'action': 'Review contingency budget and negotiate exposed cost components.' if result and data['delta'] > 0 else 'Validate cost assumptions with suppliers before revising the budget.',
                'reason': f"Scenario changes unit cost by {data['delta']:.4f} {data['currency']}; this is an assumption-driven scenario.", 'source_ids': [sid]})
        else:
            if data['status'] != 'APPROVED' or result['coverage_pct'] < 100 or result['expires_on'] < date.today().isoformat():
                gaps.append(data['name'] + ': complete current evidence and analyst approval first.'); continue
            actions.append({'action': 'Qualify alternative sources and request a mitigation plan.' if result['rating'] == 'HIGH' else 'Monitor supplier risk and revalidate evidence before commitment.',
                'reason': f"Reviewed supplier risk {result['rating']} ({result['score']:.1f}/100).", 'source_ids': [sid]})
    return save(db, user, 'recommendation', {**body.model_dump(), 'result': {'actions': actions, 'gaps': gaps, 'evidence': evidence,
        'engine': 'Deterministic evidence rules v1', 'decision_scope': 'Procurement decision support; requires Buyer review. No supplier award or purchase order is generated.'}}, ids)
