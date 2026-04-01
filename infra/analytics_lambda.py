"""
Lambda function for phd-demographics analytics.
Handles two routes:
  POST /collect  — receives pageview/click events from the tracking script
  GET  /analytics — returns aggregated data (password-protected)
"""
import json
import os
import time
import hashlib
import boto3
from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('TABLE_NAME', 'phd-demographics-analytics')
ANALYTICS_PASSWORD = os.environ.get('ANALYTICS_PASSWORD', 'changeme')

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
}


def response(status, body):
    return {
        'statusCode': status,
        'headers': {**CORS_HEADERS, 'Content-Type': 'application/json'},
        'body': json.dumps(body, default=str),
    }


def handler(event, context):
    method = event.get('requestContext', {}).get('http', {}).get('method', '')
    path = event.get('rawPath', '')

    # CORS preflight
    if method == 'OPTIONS':
        return response(200, {})

    if method == 'POST' and '/collect' in path:
        return handle_collect(event)
    elif method == 'GET' and '/analytics' in path:
        return handle_analytics(event)
    else:
        return response(404, {'error': 'not found'})


def handle_collect(event):
    try:
        body = json.loads(event.get('body', '{}'))
    except:
        return response(400, {'error': 'invalid json'})

    now = datetime.utcnow()
    date_str = now.strftime('%Y-%m-%d')
    ts = now.isoformat() + 'Z'

    # Extract geo from API Gateway / CloudFront headers
    headers = event.get('headers', {})
    source_ip = event.get('requestContext', {}).get('http', {}).get('sourceIp', '')
    country = headers.get('cloudfront-viewer-country', headers.get('x-country', ''))
    city = headers.get('cloudfront-viewer-city', '')
    region = headers.get('cloudfront-viewer-country-region-name', '')

    session_id = body.get('sid', '')[:64]
    event_type = body.get('type', 'pageview')[:20]

    item = {
        'date': date_str,
        'ts_session': f"{ts}#{session_id}",
        'timestamp': ts,
        'session_id': session_id,
        'event_type': event_type,
        'page': body.get('page', '')[:200],
        'referrer': body.get('referrer', '')[:500],
        'country': country,
        'city': city,
        'region': region,
        'ip': source_ip,
        'user_agent': body.get('ua', '')[:300],
        'screen': body.get('screen', '')[:20],
        'click_target': body.get('target', '')[:100],
        'uni_key': body.get('uni', '')[:50],
        'ttl': int(time.time()) + 90 * 86400,  # 90-day TTL
    }

    # Remove empty strings
    item = {k: v for k, v in item.items() if v}

    table = dynamodb.Table(TABLE_NAME)
    table.put_item(Item=item)

    return response(200, {'ok': True})


def handle_analytics(event):
    params = event.get('queryStringParameters', {}) or {}
    password = params.get('password', '')

    if password != ANALYTICS_PASSWORD:
        return response(401, {'error': 'unauthorized'})

    days = min(int(params.get('days', 30)), 90)
    table = dynamodb.Table(TABLE_NAME)

    # Query last N days
    all_items = []
    for i in range(days):
        date_str = (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
        resp = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('date').eq(date_str),
        )
        all_items.extend(resp.get('Items', []))

    # Aggregate
    daily_views = defaultdict(int)
    hourly_views = defaultdict(int)
    countries = defaultdict(int)
    cities = defaultdict(int)
    pages = defaultdict(int)
    sessions = defaultdict(lambda: {'views': 0, 'clicks': 0, 'country': '', 'first_ts': '', 'pages': set()})
    uni_views = defaultdict(int)

    for item in all_items:
        et = item.get('event_type', 'pageview')
        sid = item.get('session_id', '')
        ts = item.get('timestamp', '')
        date = item.get('date', '')

        if et == 'pageview':
            daily_views[date] += 1
            if len(ts) >= 13:
                try:
                    hour = int(ts[11:13])
                    hourly_views[hour] += 1
                except:
                    pass
            country = item.get('country', 'Unknown')
            if country:
                countries[country] += 1
            city = item.get('city', '')
            if city:
                cities[f"{city}, {country}"] += 1
            page = item.get('page', '')
            if page:
                pages[page] += 1
            sessions[sid]['views'] += 1
            sessions[sid]['country'] = country
            if not sessions[sid]['first_ts'] or ts < sessions[sid]['first_ts']:
                sessions[sid]['first_ts'] = ts
            sessions[sid]['pages'].add(page)

        elif et == 'click':
            sessions[sid]['clicks'] += 1
            uni = item.get('uni_key', '')
            if uni:
                uni_views[uni] += 1

    # Build response
    total_sessions = len(sessions)
    total_views = sum(daily_views.values())
    total_clicks = sum(s['clicks'] for s in sessions.values())
    avg_clicks = round(total_clicks / total_sessions, 1) if total_sessions else 0

    # Recent sessions (last 50)
    recent = sorted(sessions.items(), key=lambda x: x[1]['first_ts'], reverse=True)[:50]
    recent_list = []
    for sid, s in recent:
        recent_list.append({
            'session_id': sid[:8],
            'timestamp': s['first_ts'],
            'country': s['country'],
            'views': s['views'],
            'clicks': s['clicks'],
            'pages': list(s['pages']),
        })

    return response(200, {
        'period_days': days,
        'total_views': total_views,
        'total_sessions': total_sessions,
        'total_clicks': total_clicks,
        'avg_clicks_per_session': avg_clicks,
        'daily_views': dict(sorted(daily_views.items())),
        'hourly_views': {str(h): c for h, c in sorted(hourly_views.items())},
        'top_countries': dict(sorted(countries.items(), key=lambda x: -x[1])[:20]),
        'top_cities': dict(sorted(cities.items(), key=lambda x: -x[1])[:20]),
        'top_pages': dict(sorted(pages.items(), key=lambda x: -x[1])[:20]),
        'top_universities': dict(sorted(uni_views.items(), key=lambda x: -x[1])[:20]),
        'recent_sessions': recent_list,
    })
