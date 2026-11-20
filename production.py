"""Account and cohort access for the hosted SimuTrade application."""
import calendar
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import server

ORIGIN = os.getenv('PUBLIC_ORIGIN', 'https://simutradelabs.thinktanksolutionsai.online')
API_KEY = os.getenv('FIREBASE_API_KEY', '')
COLLECTION = os.getenv('ST_COLLECTION', 'simutrade_records')
OWNER = os.getenv('ADMIN_EMAIL', '').lower()
OPERATOR_AUDIENCE = os.getenv('OPERATOR_AUDIENCE', '')
TERMS_VERSION = 'simutrade-cohort-2026-11-20'
PLANS = {
    'founder': {'name': 'Founding Cohort', 'seats': 5, 'monthly': 19,
                'link': 'https://buy.stripe.com/3cIfZjfk05Wq0f1dww4Ni0d'},
    'premium': {'name': 'Premium', 'seats': 10, 'monthly': 49,
                'link': 'https://buy.stripe.com/7sY3cx5Jq98Ce5RfEE4Ni0e'},
}


class RequestError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def fetch_json(url, payload=None, headers=None):
    req = Request(url, data=json.dumps(payload).encode() if payload is not None else None,
                  headers={'Content-Type': 'application/json', **(headers or {})})
    with urlopen(req, timeout=15) as response:
        return json.load(response)


def firebase(method, payload):
    if not API_KEY:
        raise RequestError('Account service is unavailable.', 503)
    try:
        return fetch_json('https://identitytoolkit.googleapis.com/v1/accounts:' + method +
                          '?key=' + API_KEY, payload)
    except HTTPError as exc:
        error = json.loads(exc.read()).get('error', {}).get('message', '')
        if error.startswith(('INVALID_LOGIN_CREDENTIALS', 'INVALID_PASSWORD', 'EMAIL_NOT_FOUND')):
            raise RequestError('Email or password incorrect.', 401) from None
        if error.startswith('EMAIL_EXISTS'):
            raise RequestError('Use sign in or password recovery for this email.') from None
        if error.startswith(('TOO_MANY_ATTEMPTS', 'QUOTA_EXCEEDED')):
            raise RequestError('Too many requests. Please try again later.', 429) from None
        raise RequestError('Account request could not be completed. Please retry.', 400) from None


def refresh_firebase(token):
    body = urlencode({'grant_type': 'refresh_token', 'refresh_token': token}).encode()
    request = Request('https://securetoken.googleapis.com/v1/token?key=' + API_KEY,
                      data=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def months_after(timestamp, months):
    date = datetime.fromtimestamp(timestamp, timezone.utc)
    year, month = divmod(date.year * 12 + date.month - 1 + months, 12)
    day = min(date.day, calendar.monthrange(year, month + 1)[1])
    return int(date.replace(year=year, month=month + 1, day=day).timestamp())


def batch(records):
    """Apply compare-and-set writes atomically in either supported store."""
    if server.PROJECT:
        token = fetch_json(
            'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token',
            headers={'Metadata-Flavor': 'Google'})['access_token']
        base = f'projects/{server.PROJECT}/databases/(default)/documents'
        writes = []
        for key, data, version in records:
            condition = {'exists': False} if version is None else {'updateTime': version}
            writes.append({'update': {'name': base + '/' + COLLECTION + '/' + key,
                                       'fields': {'payload': {'stringValue': json.dumps(data)}}},
                           'currentDocument': condition})
        try:
            return fetch_json('https://firestore.googleapis.com/v1/' + base + ':commit',
                              {'writes': writes}, {'Authorization': 'Bearer ' + token})
        except HTTPError as exc:
            if exc.code in (409, 412):
                raise server.Conflict('Changed in another session. Refresh and retry.') from None
            raise
    with sqlite3.connect(server.DB) as connection:
        connection.execute('BEGIN IMMEDIATE')
        for key, data, version in records:
            row = connection.execute('SELECT version FROM records WHERE key=?', (key,)).fetchone()
            if (row[0] if row else None) != version:
                raise server.Conflict('Changed in another session. Refresh and retry.')
            connection.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)',
                               (key, json.dumps(data), (version or 0) + 1))


def throttle(purpose, identity, limit=12, duration=600):
    now = time.time()
    digest = hashlib.sha256((purpose + ':' + str(identity)).encode()).hexdigest()
    key = 'rate:' + digest
    for attempt in range(4):
        row, version = server.STORE.get(key)
        row = row if row and row.get('expires', 0) > now else {'count': 0, 'expires': now + duration}
        if row['count'] >= limit:
            raise RequestError('Too many requests. Please try again later.', 429)
        row['count'] += 1
        try:
            server.STORE.put(key, row, version)
            return
        except server.Conflict:
            if attempt == 3:
                raise RequestError('Please retry in a moment.', 429) from None


def public_team(team, uid):
    active = team.get('status') == 'active' and team.get('paidUntil', 0) > time.time()
    plan = PLANS.get(team.get('plan'), {})
    pending = [x for x in team.get('invites', []) if x['expires'] > time.time()]
    return {
        'id': team['id'], 'name': team['name'], 'owner': team['owner'] == uid,
        'status': 'active' if active else 'pending', 'plan': team.get('plan'),
        'planName': plan.get('name', 'Choose a plan'), 'seatLimit': plan.get('seats', 1),
        'paidUntil': team.get('paidUntil'), 'termEndsAt': team.get('termEndsAt'),
        'members': [{'uid': x['uid'], 'name': x['name'], 'role': x['role']} for x in team['members']],
        'pendingInvites': [{'email': x['email'], 'expires': x['expires']} for x in pending]
                          if team['owner'] == uid else [],
        'notes': team.get('notes', []) if active else [],
    }


class ProductionHandler(server.Handler):
    def cookie(self, token='', expires=604800):
        return '__session=' + token + '; HttpOnly; SameSite=Lax; Path=/; Max-Age=' + str(expires) + (
            '; Secure' if server.CLOUD or self.headers.get('X-Forwarded-Proto') == 'https' else '')

    def session_key(self):
        cookies = SimpleCookie()
        cookies.load(self.headers.get('Cookie', ''))
        value = cookies.get('__session')
        return 'session:' + hashlib.sha256(value.value.encode()).hexdigest() if value else None

    def session(self):
        row = super().session()
        if not row or not row.get('firebaseRefresh') or row.get('checkedAt', 0) > time.time() - 300:
            return row
        key = self.session_key()
        stored, version = server.STORE.get(key)
        try:
            refresh = refresh_firebase(row['firebaseRefresh'])
            account = firebase('lookup', {'idToken': refresh['id_token']})['users'][0]
            if account['localId'] != row['uid'] or account.get('disabled'):
                raise RequestError('Please sign in again.', 401)
            row.update(verified=account.get('emailVerified', False), checkedAt=time.time(),
                       firebaseRefresh=refresh['refresh_token'])
            server.STORE.put(key, row, version)
            return row
        except server.Conflict:
            return super().session()
        except HTTPError as exc:
            if exc.code in (400, 401, 403):
                row['expires'] = 0
                server.STORE.put(key, row, version)
                return None
            raise

    def require_user(self, verified=False):
        user = self.session()
        if not user:
            raise RequestError('Sign in to use your team workspace.', 401)
        if verified and API_KEY and not user.get('verified'):
            raise RequestError('Verify your email before using team access.', 403)
        return user

    def require_operator(self):
        token = self.headers.get('Authorization', '').removeprefix('Bearer ').strip()
        local = os.getenv('SIMUTRADE_LOCAL_OPERATOR_TOKEN', '')
        if not server.CLOUD and local and token and hmac.compare_digest(token, local):
            return
        if not token or not OWNER or not OPERATOR_AUDIENCE:
            raise RequestError('Authorized operator sign-in required.', 403)
        try:
            info = fetch_json('https://oauth2.googleapis.com/tokeninfo?' + urlencode({'id_token': token}))
        except HTTPError:
            raise RequestError('Authorized operator sign-in required.', 403) from None
        if (info.get('email', '').lower() != OWNER or info.get('aud') != OPERATOR_AUDIENCE or
                info.get('email_verified') not in ('true', True) or
                info.get('iss') not in ('accounts.google.com', 'https://accounts.google.com') or
                int(info.get('exp', 0)) <= time.time()):
            raise RequestError('Authorized operator sign-in required.', 403)

    def request_data(self):
        origin = self.headers.get('Origin')
        allowed = (ORIGIN, 'http://' + self.headers.get('Host', ''), 'https://' + self.headers.get('Host', ''))
        if origin and origin not in allowed:
            raise RequestError('Cross-origin request rejected.', 403)
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise RequestError('Cross-site request rejected.', 403)
        if not self.headers.get('Content-Type', '').startswith('application/json'):
            raise RequestError('JSON required.', 415)
        data = self.body()
        if not isinstance(data, dict):
            raise RequestError('Object required.')
        return data

    def current_team(self, user):
        member, _ = server.STORE.get('member:' + user['uid'])
        if not member or not member.get('team'):
            return None, None
        team, version = server.STORE.get('cohort:' + member['team'])
        if not team or not any(x['uid'] == user['uid'] for x in team['members']):
            return None, None
        return team, version

    def do_GET(self):
        if self.path.startswith('/api/simutrade/'):
            self.path = '/api' + self.path[len('/api/simutrade'):]
        path = urlparse(self.path).path
        try:
            if path == '/api/team':
                user = self.require_user()
                team, _ = self.current_team(user)
                return self.out(200, {'team': public_team(team, user['uid']) if team else None,
                                      'emailVerified': user.get('verified', not bool(API_KEY)),
                                      'termsVersion': TERMS_VERSION})
            if path == '/api/operator/team':
                self.require_operator()
                from urllib.parse import parse_qs
                team_id = parse_qs(urlparse(self.path).query).get('id', [''])[0]
                if not re.fullmatch('[a-f0-9]{32}', team_id):
                    raise RequestError('Valid team ID required.')
                team, _ = server.STORE.get('cohort:' + team_id)
                return self.out(200, {'team': team})
            return super().do_GET()
        except RequestError as exc:
            self.out(exc.status, {'error': str(exc)})
        except Exception:
            self.out(503, {'error': 'Service unavailable. Please retry.'})

    def authenticate(self, path, data):
        email = str(data.get('email', '')).strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254:
            raise RequestError('Please enter a valid email address.')
        throttle('auth', email)
        if path == '/api/auth/recovery':
            try:
                firebase('sendOobCode', {'requestType': 'PASSWORD_RESET', 'email': email})
            except RequestError as exc:
                if exc.status == 429:
                    raise
            return self.out(200, {'ok': True, 'message': 'If this address has an account, check its inbox for recovery instructions.'})
        password = str(data.get('password', ''))
        if not 12 <= len(password) <= 128:
            raise RequestError('Use a password of 12–128 characters.')
        new = path == '/api/register'
        if new and (data.get('termsVersion') != TERMS_VERSION or data.get('termsAccepted') is not True):
            raise RequestError('Read and accept the account terms to continue.')
        result = firebase('signUp' if new else 'signInWithPassword', {
            'email': email, 'password': password, 'returnSecureToken': True})
        account = firebase('lookup', {'idToken': result['idToken']})['users'][0]
        uid = account['localId']
        profile_key = 'profile:' + uid
        profile, profile_version = server.STORE.get(profile_key)
        name = str(data.get('name', '')).strip()[:80] if new else ''
        profile = profile or {'name': name or 'Learner', 'email': email,
                              'termsVersion': TERMS_VERSION, 'createdAt': time.time()}
        state, state_version = server.STORE.get('state:' + uid)
        writes = []
        if profile_version is None:
            writes.append((profile_key, profile, None))
        if state_version is None:
            writes.append(('state:' + uid, server.fresh(), None))
        if writes:
            try:
                batch(writes)
            except server.Conflict:
                profile, _ = server.STORE.get(profile_key)
                state, _ = server.STORE.get('state:' + uid)
                if not profile or not state:
                    raise
        token = secrets.token_urlsafe(32)
        server.STORE.put('session:' + hashlib.sha256(token.encode()).hexdigest(), {
            'uid': uid, 'email': email, 'name': profile['name'], 'expires': time.time() + 604800,
            'verified': account.get('emailVerified', False), 'checkedAt': time.time(),
            'firebaseRefresh': result['refreshToken']})
        sent = False
        if new:
            try:
                firebase('sendOobCode', {'requestType': 'VERIFY_EMAIL', 'idToken': result['idToken']})
                sent = True
            except RequestError:
                pass
        self.out(200, {'ok': True, 'verificationSent': sent}, self.cookie(token))

    def verify_email(self):
        user = self.require_user()
        throttle('verify', user['uid'], 5, 3600)
        refresh = refresh_firebase(user['firebaseRefresh'])
        account = firebase('lookup', {'idToken': refresh['id_token']})['users'][0]
        key = self.session_key()
        record, version = server.STORE.get(key)
        record.update(verified=account.get('emailVerified', False), checkedAt=time.time(),
                      firebaseRefresh=refresh['refresh_token'])
        server.STORE.put(key, record, version)
        if account.get('emailVerified'):
            return self.out(200, {'ok': True, 'verified': True})
        firebase('sendOobCode', {'requestType': 'VERIFY_EMAIL', 'idToken': refresh['id_token']})
        return self.out(200, {'ok': True, 'verified': False, 'message': 'Verification requested. Check your inbox, then check again.'})

    def team_action(self, path, data):
        user = self.require_user(verified=True)
        team, version = self.current_team(user)
        if path == '/api/team/create':
            if team:
                return self.out(200, {'team': public_team(team, user['uid'])})
            team_id = secrets.token_hex(16)
            membership_key = 'member:' + user['uid']
            previous, membership_version = server.STORE.get(membership_key)
            if previous and previous.get('team'):
                raise server.Conflict('Refresh your existing team.')
            team = {'id': team_id, 'name': str(data.get('name', '')).strip()[:80] or 'My study group',
                    'owner': user['uid'], 'ownerEmail': user['email'],
                    'members': [{'uid': user['uid'], 'name': user['name'], 'role': 'owner'}],
                    'invites': [], 'notes': [], 'status': 'pending', 'createdAt': time.time()}
            batch([('cohort:' + team_id, team, None),
                   (membership_key, {'team': team_id}, membership_version)])
            return self.out(200, {'team': public_team(team, user['uid'])})
        if path == '/api/team/join':
            if team:
                raise RequestError('Leave your current team before joining another.')
            team_id = str(data.get('team', ''))
            token = str(data.get('token', ''))
            if not re.fullmatch('[a-f0-9]{32}', team_id) or not 20 <= len(token) <= 100:
                raise RequestError('Invitation is invalid.')
            target, target_version = server.STORE.get('cohort:' + team_id)
            if not target or public_team(target, user['uid'])['status'] != 'active':
                raise RequestError('This team is not active.')
            digest = hashlib.sha256(token.encode()).hexdigest()
            invite = next((i for i in target['invites'] if hmac.compare_digest(i['hash'], digest)), None)
            if not invite or invite['expires'] <= time.time() or invite['email'] != user['email']:
                raise RequestError('Use the verified email named in the invitation.', 403)
            if len(target['members']) >= PLANS[target['plan']]['seats']:
                raise RequestError('This team has reached its seat limit.')
            target['members'].append({'uid': user['uid'], 'name': user['name'], 'role': 'learner'})
            target['invites'] = [i for i in target['invites'] if i['hash'] != digest]
            membership, membership_version = server.STORE.get('member:' + user['uid'])
            if membership and membership.get('team'):
                raise server.Conflict('Refresh your team membership.')
            batch([('cohort:' + team_id, target, target_version),
                   ('member:' + user['uid'], {'team': team_id}, membership_version)])
            return self.out(200, {'team': public_team(target, user['uid'])})
        if not team:
            raise RequestError('Create or join a team first.')
        if path == '/api/team/checkout':
            if team['owner'] != user['uid']:
                raise RequestError('The team owner manages billing.', 403)
            plan = str(data.get('plan', ''))
            if plan not in PLANS or data.get('termsVersion') != TERMS_VERSION or data.get('termsAccepted') is not True:
                raise RequestError('Choose a plan and accept its terms.')
            if team.get('status') == 'active':
                raise RequestError('Request an upgrade through support so your existing subscription is updated.')
            team.update(requestedPlan=plan, termsVersion=TERMS_VERSION, termsAcceptedAt=time.time())
            server.STORE.put('cohort:' + team['id'], team, version)
            query = urlencode({'client_reference_id': 'st_' + team['id'], 'prefilled_email': user['email']})
            return self.out(200, {'url': PLANS[plan]['link'] + '?' + query})
        if public_team(team, user['uid'])['status'] != 'active':
            raise RequestError('Paid team activation is pending. Free practice stays available.', 403)
        if path == '/api/team/invite':
            if team['owner'] != user['uid']:
                raise RequestError('Only the team owner can invite learners.', 403)
            email = str(data.get('email', '')).strip().lower()
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254 or email == user['email']:
                raise RequestError('Enter the learner’s email address.')
            team['invites'] = [i for i in team['invites'] if i['expires'] > time.time()]
            if any(i['email'] == email for i in team['invites']):
                raise RequestError('An invitation is already reserved for this email.')
            if len(team['members']) + len(team['invites']) >= PLANS[team['plan']]['seats']:
                raise RequestError('All included seats are occupied or reserved.')
            token = secrets.token_urlsafe(32)
            team['invites'].append({'email': email, 'hash': hashlib.sha256(token.encode()).hexdigest(),
                                    'expires': time.time() + 7 * 86400})
            server.STORE.put('cohort:' + team['id'], team, version)
            return self.out(200, {'invite': ORIGIN + '/app#team?invite=' + team['id'] + '.' + token,
                                  'team': public_team(team, user['uid'])})
        if path == '/api/team/note':
            text = str(data.get('text', '')).strip()
            if not 1 <= len(text) <= 1500:
                raise RequestError('Write a study note of up to 1,500 characters.')
            team['notes'] = ([{'id': secrets.token_hex(8), 'name': user['name'], 'uid': user['uid'],
                               'text': text, 'created': time.time()}] + team.get('notes', []))[:100]
        elif path == '/api/team/remove':
            if team['owner'] != user['uid']:
                raise RequestError('Only the owner can remove a team member.', 403)
            uid = str(data.get('uid', ''))
            if uid == user['uid'] or not any(m['uid'] == uid for m in team['members']):
                raise RequestError('Choose a learner to remove.')
            team['members'] = [m for m in team['members'] if m['uid'] != uid]
            membership, member_version = server.STORE.get('member:' + uid)
            if not membership or membership.get('team') != team['id']:
                raise server.Conflict('Refresh the team roster.')
            batch([('cohort:' + team['id'], team, version),
                   ('member:' + uid, {'team': None}, member_version)])
            return self.out(200, {'team': public_team(team, user['uid'])})
        elif path == '/api/team/revoke':
            if team['owner'] != user['uid']:
                raise RequestError('Only the owner can release a reserved seat.', 403)
            email = str(data.get('email', '')).strip().lower()
            team['invites'] = [invite for invite in team['invites'] if invite['email'] != email]
        else:
            raise RequestError('Team action not found.', 404)
        server.STORE.put('cohort:' + team['id'], team, version)
        return self.out(200, {'team': public_team(team, user['uid'])})

    def activate(self, data):
        self.require_operator()
        team_id = str(data.get('team', ''))
        if not re.fullmatch('[a-f0-9]{32}', team_id):
            raise RequestError('Valid team ID required.')
        team, version = server.STORE.get('cohort:' + team_id)
        if not team:
            raise RequestError('Team not found.', 404)
        plan = str(data.get('plan', ''))
        if plan not in PLANS or data.get('customerEmail', '').lower() != team['ownerEmail']:
            raise RequestError('Plan and verified purchaser identity must match the team.')
        fixture = data.get('fictionalAcceptance') is True
        if fixture and not team['ownerEmail'].endswith(('@example.test', '@example.com')):
            raise RequestError('Acceptance fixtures require a designated fictional account.')
        reference = str(data.get('paymentReference', data.get('checkoutSession', '')))
        if not re.fullmatch(r'(cs|in)_[A-Za-z0-9_]{12,255}', reference):
            raise RequestError('Verified checkout session or renewal invoice required.')
        subscription = str(data.get('subscription', ''))
        if not re.fullmatch(r'sub_[A-Za-z0-9_]{8,255}', subscription):
            raise RequestError('Verified subscription required.')
        if team.get('subscription') and reference.startswith('in_') and subscription != team['subscription']:
            raise RequestError('Renewal subscription must match the active team.')
        if not fixture and team.get('termsVersion') != TERMS_VERSION:
            raise RequestError('Customer acceptance of the order terms is required.')
        if data.get('paymentVerified') is not True or data.get('subscriptionVerified') is not True:
            raise RequestError('Confirm settled payment and active matching subscription first.')
        until = float(data.get('paidUntil', 0))
        started = float(data.get('startedAt', 0))
        if not 0 < started <= time.time() + 60 or not time.time() < until <= time.time() + 35 * 86400:
            raise RequestError('Verified billing period required.')
        term_end = months_after(started, 6) if plan == 'founder' else None
        if term_end and (data.get('scheduledCancellationAt') != term_end or
                         data.get('cancellationVerified') is not True or until > term_end):
            raise RequestError('Verify the six-month Stripe cancellation schedule before activation.')
        existing, receipt_version = server.STORE.get('receipt:' + reference)
        if existing:
            if existing['team'] != team_id:
                raise RequestError('This receipt is already assigned.', 409)
            return self.out(200, {'ok': True, 'duplicate': True, 'team': public_team(team, team['owner'])})
        if len(team['members']) > PLANS[plan]['seats']:
            raise RequestError('Reduce occupied seats before changing this plan.')
        team.update(plan=plan, status='active', paidUntil=until, startedAt=started,
                    termEndsAt=term_end, subscription=subscription,
                    activationMethod='operator_verified_stripe', fictionalAcceptance=fixture,
                    updatedAt=time.time())
        batch([('cohort:' + team_id, team, version),
               ('receipt:' + reference, {'team': team_id, 'recordedAt': time.time(),
                                         'fictionalAcceptance': fixture}, receipt_version)])
        return self.out(200, {'ok': True, 'team': public_team(team, team['owner'])})

    def suspend(self, data):
        self.require_operator()
        team_id = str(data.get('team', ''))
        if not re.fullmatch('[a-f0-9]{32}', team_id):
            raise RequestError('Valid team ID required.')
        team, version = server.STORE.get('cohort:' + team_id)
        if not team:
            raise RequestError('Team not found.', 404)
        reason = str(data.get('reason', ''))
        if reason not in ('refunded', 'chargeback', 'subscription_ended') or data.get('billingVerified') is not True:
            raise RequestError('Verified billing status and reason required.')
        if data.get('subscription') != team.get('subscription'):
            raise RequestError('Subscription must match this team.')
        team.update(status='suspended', paidUntil=min(team.get('paidUntil', 0), time.time()),
                    suspensionReason=reason, updatedAt=time.time())
        server.STORE.put('cohort:' + team_id, team, version)
        return self.out(200, {'ok': True, 'team': public_team(team, team['owner'])})

    def do_POST(self):
        if self.path.startswith('/api/simutrade/'):
            self.path = '/api' + self.path[len('/api/simutrade'):]
        path = urlparse(self.path).path
        handled = path.startswith(('/api/team/', '/api/auth/', '/api/operator/')) or (
            bool(API_KEY) and path in ('/api/register', '/api/login'))
        if not handled:
            return super().do_POST()
        try:
            data = self.request_data()
            if path in ('/api/register', '/api/login', '/api/auth/recovery'):
                return self.authenticate(path, data)
            if path == '/api/auth/verify':
                return self.verify_email()
            if path == '/api/operator/activate':
                return self.activate(data)
            if path == '/api/operator/suspend':
                return self.suspend(data)
            if path.startswith('/api/team/'):
                return self.team_action(path, data)
            raise RequestError('Route not found.', 404)
        except RequestError as exc:
            self.out(exc.status, {'error': str(exc)})
        except server.Conflict as exc:
            self.out(409, {'error': str(exc)})
        except (ValueError, TypeError, KeyError):
            self.out(400, {'error': 'Please check the request fields.'})
        except Exception:
            self.out(503, {'error': 'Service temporarily unavailable. No success was confirmed. Please retry.'})


if __name__ == '__main__':
    port = int(os.getenv('PORT', '8080'))
    ThreadingHTTPServer((os.getenv('ST_BIND_HOST', '0.0.0.0'), port), ProductionHandler).serve_forever()
