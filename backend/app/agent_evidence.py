"""Bounded, typed evidence collection and reproducible change/risk assessment."""
import hashlib
import json
from datetime import date
from typing import Literal
from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import select
from .db import MarketPoint, Record, uid, now
from .market import StrictInput, accessible
from .advanced import authorize
from .intelligence import mcp_call

DOMAINS = ['Demand', 'Inventory', 'PO', 'RFI', 'Market Data', 'Supplier Data', 'Price', 'Market Events']
METRICS = {'demand_quantity': 'Demand', 'inventory_coverage': 'Inventory', 'po_open_value': 'PO',
           'po_overdue_count': 'PO', 'supplier_lead_time': 'Supplier Data', 'price': 'Price'}
TOOLS = {'get_demand_history': {'demand_quantity'}, 'get_inventory_position': {'inventory_coverage'},
         'get_open_purchase_orders': {'po_open_value', 'po_overdue_count'}, 'get_lead_time_history': {'supplier_lead_time'}}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


class OperationalMetric(StrictInput):
    metric: Literal['demand_quantity', 'inventory_coverage', 'po_open_value', 'po_overdue_count', 'supplier_lead_time']
    unit: str = Field(min_length=1, max_length=50)
    currency: str = Field(default='', max_length=3)
    scope: str = Field(min_length=2, max_length=100)
    horizon_days: int = Field(default=30, ge=1, le=730)


def metric_contract(metric):
    expected = {'inventory_coverage': 'months', 'po_overdue_count': 'orders', 'supplier_lead_time': 'weeks', 'po_open_value': 'currency'}
    if metric.metric in expected and metric.unit != expected[metric.metric]:
        raise HTTPException(422, 'Unit untuk ' + metric.metric + ' harus ' + expected[metric.metric] + '.')
    if metric.metric == 'po_open_value':
        if len(metric.currency) != 3 or not metric.currency.isalpha() or not metric.currency.isupper(): raise HTTPException(422, 'PO value memerlukan kode mata uang ISO huruf besar.')
    elif metric.currency: raise HTTPException(422, 'Metrik nonmoneter tidak memakai currency.')


class GatewayObservation(OperationalMetric):
    key: str = Field(min_length=1, max_length=100)
    value: float = Field(ge=0, le=1e12)
    as_of: date
    source: str = Field(min_length=3, max_length=300)
    confidence: float = Field(default=1, ge=0, le=1)
    previous_value: float | None = Field(default=None, ge=0, le=1e12)
    previous_as_of: date | None = None


class GatewayResult(StrictInput):
    category_id: str
    region: str
    observations: list[GatewayObservation] = Field(max_length=100)


def parse_gateway(result, tool, category, region):
    try:
        payload = result.get('structuredContent')
        if payload is None:
            texts = [c['text'] for c in result.get('content', []) if c.get('type') == 'text']
            if len(texts) != 1: raise ValueError()
            payload = json.loads(texts[0])
        if len(json.dumps(payload)) > 200000: raise ValueError()
        data = GatewayResult.model_validate(payload)
        if data.category_id != category or data.region != region: raise ValueError()
        if len({r.key for r in data.observations}) != len(data.observations): raise ValueError()
        for row in data.observations:
            metric_contract(row)
            if row.metric not in TOOLS[tool] or row.as_of > date.today(): raise ValueError()
            if (row.previous_value is None) != (row.previous_as_of is None): raise ValueError()
            if row.previous_as_of and row.previous_as_of >= row.as_of: raise ValueError()
            if row.metric == 'po_overdue_count' and (not row.value.is_integer() or (row.previous_value is not None and not row.previous_value.is_integer())): raise ValueError()
        return data.observations
    except (ValueError, TypeError, KeyError, AttributeError, HTTPException) as exc:
        raise HTTPException(502, 'MCP evidence harus mengikuti kontrak kategori, region, metrik, unit, dan tanggal agent.') from exc


def reference(row):
    return {'id': row.id, 'name': row.data.get('name', row.data.get('title', row.id)), 'kind': row.kind,
            'region': row.region, 'classification': row.classification, 'is_demo': bool(row.data.get('is_demo'))}


def sample_series(db, row, config):
    points = list(db.scalars(select(MarketPoint).where(MarketPoint.series_id == row.id).order_by(MarketPoint.observed_on.desc()).limit(2)))
    if not points: return None
    latest = points[0]; prior = points[1] if len(points) > 1 else None
    if prior and float(prior.confidence) < config['min_confidence']: prior = None
    return {'key': row.id, 'metric': row.data.get('metric', 'price'), 'label': row.data['name'],
            'domain': METRICS.get(row.data.get('metric'), 'Price'), 'scope': row.data.get('scope', row.data.get('geography', '')),
            'horizon_days': row.data.get('horizon_days'), 'value': float(latest.value), 'as_of': latest.observed_on,
            'previous_value': float(prior.value) if prior else None, 'previous_as_of': prior.observed_on if prior else None,
            'unit': row.data['unit'], 'currency': row.data.get('currency', ''), 'confidence': float(latest.confidence),
            'source': reference(row), 'publication': latest.source, 'is_demo': bool(row.data.get('is_demo')),
            'stale': (date.today() - date.fromisoformat(latest.observed_on)).days > config['max_source_age_days']}


def snapshot_sources(snapshot):
    return list({ref['id'] for item in snapshot.get('metrics', []) + snapshot.get('entities', [])
        for ref in [item['source'], *item.get('dependencies', [])] if ref['kind'] != 'mcp'})


def snapshot_access(db, user, snapshot):
    for item in snapshot.get('metrics', []) + snapshot.get('entities', []):
        for ref in [item['source'], *item.get('dependencies', [])]:
            if ref['kind'] == 'mcp':
                if user.role not in ('Buyer', 'Market Intelligence Analyst') or ref['region'] != user.region: return False
            elif not authorize(db, user, db.get(Record, ref['id'])): return False
    return True


def local_evidence(db, user, config):
    snapshot = {'captured_at': now(), 'metrics': [], 'entities': [], 'issues': [], 'coverage': {d: {'count': 0, 'fresh': 0, 'state': 'MISSING'} for d in DOMAINS}, 'failed_keys': []}
    for id in config['signal_ids']:
        row = db.get(Record, id)
        if not row or row.kind != 'agent_signal' or not accessible(user, row) or row.data.get('category_id') != config['category_id']:
            snapshot['issues'].append({'domain': 'Operational sources', 'code': 'SOURCE_UNAVAILABLE', 'message': 'A configured operational source is no longer available.'}); snapshot['failed_keys'].append(id); continue
        value = sample_series(db, row, config)
        if value: snapshot['metrics'].append(value)
        else: snapshot['issues'].append({'domain': METRICS[row.data['metric']], 'code': 'EMPTY_SERIES', 'message': row.data['name'] + ' has no observations.'})
    for kind, domain in [('price', 'Price'), ('rfi', 'RFI'), ('supplier', 'Supplier Data'), ('document', 'Market Data'), ('external_evidence', 'Market Data'), ('event', 'Market Events')]:
        query = select(Record).where(Record.kind == kind, Record.region.in_(['Global', user.region]), Record.data['category_id'].as_string() == config['category_id'])
        if not config['include_demo']: query = query.where(Record.data['is_demo'].as_boolean().is_not(True))
        scanned = list(db.scalars(query.order_by(Record.id).limit(201)))
        if len(scanned) > 200:
            snapshot['issues'].append({'domain': domain, 'code': 'SOURCE_LIMIT', 'message': 'More than 200 sources; narrow the category before evaluation.'})
            continue
        rows = [r for r in scanned if authorize(db, user, r)]
        for row in rows:
            if kind == 'price':
                if row.data.get('metric_type', 'price') not in ('price', 'index'): continue
                value = sample_series(db, row, config)
                if value: snapshot['metrics'].append(value)
                continue
            keys = {'rfi': ['number', 'title', 'status', 'closing_date', 'version', 'supplier_ids', 'questions'],
                    'supplier': ['name', 'country', 'type', 'landscape', 'portal_profile'],
                    'document': ['name', 'status', 'checksum', 'version', 'indexed_at', 'source', 'text'],
                    'external_evidence': ['name', 'connector_id', 'retrieved_at', 'content'],
                    'event': ['title', 'description', 'date', 'impact', 'probability', 'expected_impact', 'assessment', 'source']}[kind]
            body = {k: row.data.get(k) for k in keys}; dependencies = []
            if kind == 'rfi':
                responses = list(db.scalars(select(Record).where(Record.kind == 'response', Record.data['rfi_id'].as_string() == row.id).limit(201)))
                if len(responses) > 200:
                    snapshot['issues'].append({'domain': domain, 'code': 'SOURCE_LIMIT', 'message': 'An RFI exceeds the 200-response evaluation limit.'})
                    continue
                submitted = [r for r in responses if authorize(db, user, r) and r.data.get('submitted')]
                body['submitted_responses'] = len(submitted)
                dependencies = [reference(r) for r in submitted]
            # Hash full content for change detection, expose only operational fields and bounded text.
            digest = fingerprint(body)
            for key in ('text', 'content', 'questions', 'supplier_ids', 'portal_profile'):
                if key in body: body[key] = '[content tracked by checksum]' if body[key] else None
            body['content_checksum'] = digest
            snapshot['entities'].append({'key': row.id, 'domain': domain, 'label': row.data.get('name', row.data.get('title', row.id)),
                'source': reference(row), 'dependencies': dependencies, 'digest': digest, 'fields': body, 'as_of': row.updated_at,
                'stale': False, 'is_demo': bool(row.data.get('is_demo'))})
    return snapshot


async def add_enterprise(snapshot, db, user, config, checkpoint):
    if not config['use_mcp']: return
    for tool, allowed in TOOLS.items():
        await checkpoint('READ_MCP', tool)
        domain = METRICS[next(iter(allowed))]
        try:
            raw = await mcp_call(db, user, tool, {'category': config['category_id']}, uid(), max_response_bytes=2 * 1024 * 1024)
            observations = parse_gateway(raw, tool, config['category_id'], user.region)
            for row in observations:
                snapshot['metrics'].append({**row.model_dump(mode='json'), 'key': 'mcp:' + tool + ':' + row.key,
                    'domain': METRICS[row.metric], 'label': row.scope + ' / ' + row.metric,
                    'source': {'id': 'mcp:' + tool, 'kind': 'mcp', 'name': row.source, 'region': user.region, 'classification': 'CONFIDENTIAL', 'is_demo': False},
                    'publication': row.source, 'is_demo': False,
                    'stale': (date.today() - row.as_of).days > config['max_source_age_days']})
        except HTTPException:
            snapshot['issues'].append({'domain': domain, 'code': 'MCP_UNAVAILABLE', 'message': tool + ': data unavailable or contract rejected.'})
            snapshot['failed_keys'].append('mcp:' + tool + ':')


def qualify_snapshot(snapshot, previous, config):
    old = {r['key']: r for r in previous.get('metrics', [])}
    for item in snapshot['metrics']:
        item['low_confidence'] = item.get('confidence', 1) < config['min_confidence']
        prior = old.get(item['key'])
        item['regressed'] = bool(prior and item['as_of'] < prior['as_of'])
        if item['regressed']:
            snapshot['issues'].append({'domain': item['domain'], 'code': 'REGRESSED_OBSERVATION', 'message': item['label'] + ': source returned an older observation; previous baseline retained.'})
    return snapshot


def finalize_coverage(snapshot):
    for domain in DOMAINS:
        items = [r for r in snapshot['metrics'] + snapshot['entities'] if r['domain'] == domain]
        fresh = sum(not r['stale'] and not r.get('low_confidence') and not r.get('regressed') for r in items)
        issues = any(i['domain'] == domain for i in snapshot['issues'])
        snapshot['coverage'][domain] = {'count': len(items), 'fresh': fresh, 'state': 'DEGRADED' if issues or fresh < len(items) else 'AVAILABLE' if items else 'MISSING'}
    return snapshot


def percentage(value, previous):
    if previous == 0: return None
    return (value - previous) / abs(previous) * 100


def comparable(a, b):
    return all(a.get(k) == b.get(k) for k in ('metric', 'unit', 'currency', 'scope', 'horizon_days'))


def compare_snapshots(previous, current, policy):
    changes = []
    if not previous: return changes
    for kind in ('metrics', 'entities'):
        before = {r['key']: r for r in previous.get(kind, [])}
        for item in current[kind]:
            old = before.get(item['key'])
            if item.get('regressed'): continue
            base = {'domain': item['domain'], 'source': item['source'], 'label': item['label'], 'key': item['key'], 'as_of': item['as_of']}
            if not old:
                changes.append({**base, 'type': 'NEW_SOURCE', 'before': None, 'after': item.get('value', item.get('fields')), 'material': not item.get('stale') and not item.get('low_confidence'), 'severity': 'INFO'}); continue
            if kind == 'entities':
                if old['digest'] != item['digest']:
                    changes.append({**base, 'type': 'RECORD_CHANGED', 'before': old['fields'], 'after': item['fields'], 'material': True,
                                    'severity': 'MEDIUM' if item['domain'] in ('Market Events', 'RFI', 'Supplier Data') else 'INFO'})
                continue
            if not comparable(old, item):
                changes.append({**base, 'type': 'BASIS_CHANGED', 'before': {k: old.get(k) for k in ('unit', 'currency', 'scope', 'horizon_days')},
                    'after': {k: item.get(k) for k in ('unit', 'currency', 'scope', 'horizon_days')}, 'material': True, 'severity': 'MEDIUM'}); continue
            if old['value'] == item['value']: continue
            pct = percentage(item['value'], old['value'])
            threshold = {'demand_quantity': policy['demand_change_pct'], 'supplier_lead_time': policy['lead_time_change_pct'],
                         'price': policy['price_change_pct'], 'po_open_value': policy['po_change_pct']}.get(item['metric'], 0)
            material = not item['stale'] and not item.get('low_confidence') and (pct is None or abs(pct) >= threshold)
            changes.append({**base, 'type': 'VALUE_CHANGED', 'before': old['value'], 'after': item['value'], 'before_as_of': old['as_of'],
                'pct': pct, 'unit': item['unit'], 'currency': item['currency'], 'material': material, 'severity': 'MEDIUM' if material else 'INFO',
                'corrected': item['as_of'] == old['as_of'], 'stale': item['stale']})
    # Absence alone never means a supplier disappeared or stock became zero.
    return changes


def merged_baseline(previous, snapshot):
    result = {**snapshot}
    for kind in ('metrics', 'entities'):
        by_key = {r['key']: r for r in previous.get(kind, [])} if previous else {}
        for item in snapshot[kind]:
            if item.get('regressed') or item.get('low_confidence'): continue
            old = by_key.get(item['key'])
            if kind == 'metrics' and item.get('previous_value') is None and old and comparable(old, item):
                item = {**item}
                if item['as_of'] > old['as_of']:
                    item['previous_value'] = old['value']; item['previous_as_of'] = old['as_of']
                elif item['as_of'] == old['as_of']:
                    item['previous_value'] = old.get('previous_value'); item['previous_as_of'] = old.get('previous_as_of')
            by_key[item['key']] = item
        result[kind] = list(by_key.values())
    return result


def assessment(snapshot, baseline, policy):
    signals = []; known = set(); required = {'demand_quantity', 'inventory_coverage', 'supplier_lead_time'}
    prior = {r['key']: r for r in baseline.get('metrics', [])}
    for item in snapshot['metrics']:
        if item['stale'] or item.get('low_confidence') or item.get('regressed') or item.get('is_demo'): continue
        metric = item['metric']; context = prior.get(item['key'], item)
        previous = context.get('previous_value')
        pct = percentage(item['value'], previous) if previous is not None else None
        if metric == 'inventory_coverage':
            level = 'HIGH' if item['value'] < policy['inventory_critical_months'] else 'MEDIUM' if item['value'] < policy['inventory_watch_months'] else 'LOW'
            known.add(metric); reason = f"Inventory coverage {item['value']:g} months (critical < {policy['inventory_critical_months']:g})."
        elif metric == 'po_overdue_count':
            level = 'MEDIUM' if item['value'] > 0 else 'LOW'; reason = f"{item['value']:g} overdue purchase orders."
        elif metric in ('demand_quantity', 'supplier_lead_time', 'price', 'po_open_value'):
            if previous is None or pct is None: continue
            limit = {'demand_quantity': policy['demand_change_pct'], 'supplier_lead_time': policy['lead_time_change_pct'], 'price': policy['price_change_pct'], 'po_open_value': policy['po_change_pct']}[metric]
            level = 'MEDIUM' if pct >= limit else 'LOW'; known.add(metric)
            reason = f"{item['label']} {pct:+.2f}% versus {context['previous_as_of']} (threshold +{limit:g}%)."
        else: continue
        signals.append({'key': item['key'], 'metric': metric, 'level': level, 'reason': reason, 'source': item['source'], 'value': item['value'], 'change_pct': pct, 'as_of': item['as_of']})
    elevated = [s for s in signals if s['level'] in ('MEDIUM', 'HIGH')]
    level = 'HIGH' if any(s['level'] == 'HIGH' for s in elevated) or len({s['metric'] for s in elevated}) >= 3 else 'MEDIUM' if elevated else 'LOW' if required <= known else 'UNKNOWN'
    return {'level': level, 'complete': required <= known, 'missing_risk_metrics': sorted(required - known), 'signals': signals,
            'covered_domains': sum(v['state'] == 'AVAILABLE' for v in snapshot['coverage'].values()), 'total_domains': len(DOMAINS),
            'basis': 'Evidence rules v1. Risk is the observed level; missing metrics are not treated as low risk. No award or purchase action is performed.'}


def summarize(changes, before_risk, risk, initial=False):
    if initial: return 'Initial baseline recorded. Future runs will compare against this evidence; no change is inferred yet.'
    material = [c for c in changes if c['material']]
    lines = [f"Observed procurement risk: {before_risk or 'UNKNOWN'} → {risk['level']}."]
    for change in material[:12]:
        if change['type'] == 'VALUE_CHANGED':
            pct = f" ({change['pct']:+.2f}%)" if change['pct'] is not None else ' (percentage unavailable: zero baseline)'
            lines.append(f"{change['label']}: {change['before']:g} → {change['after']:g} {change['currency']} {change['unit']}{pct}." + (' Historical correction.' if change['corrected'] else ''))
        elif change['type'] == 'NEW_SOURCE': lines.append(change['label'] + ': new evidence available.')
        elif change['type'] == 'COVERAGE_CHANGED': lines.append(change['label'] + ': ' + change['before'] + ' → ' + change['after'] + '.')
        else: lines.append(change['label'] + ': ' + change['type'].replace('_', ' ').lower() + '.')
    if not material: lines.append('No material source changes detected.')
    if len(material) > 12: lines.append(f'{len(material) - 12} additional changes are listed in the evidence report.')
    if not risk['complete']: lines.append('Risk evidence incomplete: ' + ', '.join(risk['missing_risk_metrics']) + '.')
    return '\n'.join(lines)
