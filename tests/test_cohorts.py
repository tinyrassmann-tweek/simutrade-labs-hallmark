"""Regression coverage for paid seat limits, invitations, and isolated learners."""
import concurrent.futures
import http.cookiejar
import json
import os
import pathlib
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]


class CohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        cls.base = 'http://127.0.0.1:' + str(port)
        env = {**os.environ, 'PORT': str(port), 'DB_PATH': cls.tmp.name + '/records.db',
               'SIMUTRADE_LOCAL_OPERATOR_TOKEN': 'local-test-operator'}
        for key in ('GOOGLE_CLOUD_PROJECT', 'K_SERVICE', 'FIREBASE_API_KEY'):
            env.pop(key, None)
        cls.proc = subprocess.Popen(['python3', 'production.py'], cwd=ROOT, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            try:
                urllib.request.urlopen(cls.base + '/api/health', timeout=1)
                break
            except Exception:
                time.sleep(.1)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait()
        cls.tmp.cleanup()

    def request(self, path, data=None, client=None, operator=False):
        headers = {'Content-Type': 'application/json'}
        if operator:
            headers['Authorization'] = 'Bearer local-test-operator'
        request = urllib.request.Request(self.base + path, headers=headers,
                                         data=None if data is None else json.dumps(data).encode())
        try:
            with (client.open if client else urllib.request.urlopen)(request, timeout=10) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def account(self, email=None):
        email = email or 'qa-' + str(time.time_ns()) + '@example.test'
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        status, result = self.request('/api/register', {
            'email': email, 'name': 'QA Learner', 'password': 'fictional-local-password-123'
        }, client)
        self.assertEqual(status, 200, result)
        return client, email

    def cohort(self):
        client, email = self.account()
        status, response = self.request('/api/team/create', {'name': 'QA study group'}, client)
        self.assertEqual(status, 200, response)
        return client, email, response['team']['id']

    def activation(self, team, email, plan='founder', reference=None):
        import sys
        sys.path.insert(0, str(ROOT))
        from production import months_after
        started = int(time.time()) - 10
        return {'team': team, 'plan': plan, 'customerEmail': email, 'startedAt': started,
                'paidUntil': started + 28 * 86400,
                'paymentReference': reference or 'cs_fixture_' + str(time.time_ns()),
                'subscription': 'sub_fixture_123456789', 'paymentVerified': True,
                'subscriptionVerified': True, 'fictionalAcceptance': True,
                'scheduledCancellationAt': months_after(started, 6), 'cancellationVerified': True}

    def activate(self, team, email, plan='founder'):
        data = self.activation(team, email, plan)
        status, result = self.request('/api/operator/activate', data, operator=True)
        self.assertEqual(status, 200, result)
        return data, result

    def test_hosted_namespace_and_session_cookie(self):
        self.assertEqual(self.request('/api/simutrade/health')[1]['storage'], 'sqlite')
        client, _ = self.account()
        self.assertTrue(self.request('/api/simutrade/me', client=client)[1]['user'])

    def test_refund_suspends_paid_collaboration(self):
        client, email, team = self.cohort()
        data, _ = self.activate(team, email)
        payload = {'team': team, 'subscription': data['subscription'],
                   'reason': 'refunded', 'billingVerified': True}
        self.assertEqual(self.request('/api/operator/suspend', payload, client)[0], 403)
        self.assertEqual(self.request('/api/operator/suspend', payload, operator=True)[0], 200)
        self.assertEqual(self.request('/api/team/invite', {'email': 'new@example.test'}, client)[0], 403)

    def test_five_seats_include_owner_and_reservations(self):
        client, email, team = self.cohort()
        self.activate(team, email)
        for number in range(4):
            status, result = self.request('/api/team/invite', {'email': f'learner-{number}@example.test'}, client)
            self.assertEqual(status, 200, result)
        self.assertEqual(self.request('/api/team/invite', {'email': 'sixth@example.test'}, client)[0], 400)
        status, result = self.request('/api/team/revoke', {'email': 'learner-0@example.test'}, client)
        self.assertEqual(status, 200, result)
        self.assertEqual(self.request('/api/team/invite', {'email': 'replacement@example.test'}, client)[0], 200)

    def test_invitation_identity_and_private_workspace(self):
        owner, email, team = self.cohort()
        self.activate(team, email)
        learner, learner_email = self.account()
        outsider, _ = self.account()
        _, invitation = self.request('/api/team/invite', {'email': learner_email}, owner)
        code = invitation['invite'].split('invite=')[1].split('.')
        join = {'team': code[0], 'token': code[1]}
        self.assertEqual(self.request('/api/team/join', join, outsider)[0], 403)
        self.assertEqual(self.request('/api/team/join', join, learner)[0], 200)
        self.assertEqual(self.request('/api/team/invite', {'email': 'other@example.test'}, learner)[0], 403)
        owner_state = self.request('/api/me', client=owner)[1]
        self.request('/api/state', {'state': {'journal': [{'title': 'Private QA note'}]},
                                   'version': owner_state['version']}, owner)
        self.assertEqual(self.request('/api/me', client=learner)[1]['state']['journal'], [])
        self.request('/api/team/note', {'text': 'Shared QA study exercise'}, learner)
        self.assertEqual(self.request('/api/team', client=owner)[1]['team']['notes'][0]['text'], 'Shared QA study exercise')
        self.assertIsNone(self.request('/api/team', client=outsider)[1]['team'])

    def test_operator_required_and_duplicate_receipt_safe(self):
        client, email, team = self.cohort()
        data = self.activation(team, email)
        self.assertEqual(self.request('/api/operator/activate', data, client)[0], 403)
        self.assertEqual(self.request('/api/operator/activate', {**data, 'cancellationVerified': False}, operator=True)[0], 400)
        self.assertEqual(self.request('/api/operator/activate', data, operator=True)[0], 200)
        self.assertTrue(self.request('/api/operator/activate', data, operator=True)[1]['duplicate'])
        other, other_email, other_team = self.cohort()
        self.assertEqual(self.request('/api/operator/activate', {**data, 'team': other_team, 'customerEmail': other_email}, operator=True)[0], 409)

    def test_concurrent_invites_cannot_overbook(self):
        client, email, team = self.cohort()
        self.activate(team, email)
        for number in range(3):
            self.request('/api/team/invite', {'email': f'base-{number}@example.test'}, client)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            outcomes = list(pool.map(lambda number: self.request('/api/team/invite', {
                'email': f'parallel-{number}@example.test'}, client)[0], range(6)))
        self.assertEqual(outcomes.count(200), 1, outcomes)
        group = self.request('/api/team', client=client)[1]['team']
        self.assertEqual(len(group['members']) + len(group['pendingInvites']), 5)

    def test_premium_has_ten_total_seats(self):
        client, email, team = self.cohort()
        self.activate(team, email, 'premium')
        for number in range(9):
            self.assertEqual(self.request('/api/team/invite', {'email': f'premium-{number}@example.test'}, client)[0], 200)
        self.assertEqual(self.request('/api/team/invite', {'email': 'eleventh@example.test'}, client)[0], 400)

    def test_checkout_requires_owner_and_terms(self):
        client, email, team = self.cohort()
        self.assertEqual(self.request('/api/team/checkout', {'plan': 'founder'}, client)[0], 400)
        status, result = self.request('/api/team/checkout', {
            'plan': 'founder', 'termsAccepted': True, 'termsVersion': 'simutrade-cohort-2026-11-20'}, client)
        self.assertEqual(status, 200, result)
        self.assertIn('client_reference_id=st_' + team, result['url'])
        self.assertIn('https://buy.stripe.com/3cIfZjfk05Wq0f1dww4Ni0d?', result['url'])


if __name__ == '__main__':
    unittest.main()
