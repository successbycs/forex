import copy
import json
from pathlib import Path
import unittest
from demo import evaluate, instant, render_text


class OperatingModelTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(Path(__file__).with_name('examples.json').read_text())
        self.policy = self.data['policy']
        self.examples = {r['name']: r for r in self.data['examples']}

    def result(self, name):
        return evaluate(self.policy, self.examples[name])

    def test_session_boundaries(self):
        for name, expected in [('before_open','CLOSED'),('at_open','OPEN'),('daily_break','BREAK'),('break_end','OPEN'),('at_close','CLOSED'),('holiday','HOLIDAY'),('weekend','CLOSED')]:
            with self.subTest(name=name):
                self.assertEqual(self.result(name)['scheduled_state'], expected)

    def test_unknown_never_invents_transition(self):
        for name in ['unknown_calendar','expired_calendar','coverage_gap','policy_conflict']:
            with self.subTest(name=name):
                r = self.result(name)
                self.assertEqual(r['scheduled_state'], 'UNKNOWN')
                self.assertIsNone(r['next_expected_transition'])
                self.assertEqual(r['session_entry_eligibility'], 'BLOCKED')

    def test_stale_is_not_scheduled_closed(self):
        r = self.result('stale_feed')
        self.assertEqual(r['scheduled_state'], 'OPEN')
        self.assertEqual(r['observed_state'], 'STALE_OR_UNKNOWN')
        self.assertEqual(r['session_entry_eligibility'], 'BLOCKED')

    def test_spread_and_no_execution_authority(self):
        self.assertEqual(self.result('wide_spread')['session_entry_eligibility'], 'BLOCKED')
        r = self.result('at_open')
        self.assertEqual(r['session_entry_eligibility'], 'CANDIDATE_ONLY')
        self.assertEqual(r['execution_permission'], 'NOT_EVALUATED_NO_ORDER_CAPABILITY')

    def test_offsets_and_auckland_dst(self):
        self.assertEqual(instant('2026-10-23T09:00:00+03:00').hour, 6)
        self.assertEqual(instant('2026-10-26T09:00:00+02:00').hour, 7)
        for name in ['before_dst_change', 'after_dst_change']:
            self.assertEqual(self.result(name)['scheduled_state'], 'OPEN')
        transition = self.result('weekend')['next_expected_transition']
        self.assertEqual(transition['auckland'], '2026-09-28T19:00:00+13:00')

    def test_exit_remains_unresolved(self):
        self.assertEqual(self.result('exit_unavailable')['position_handling'], 'EXIT_UNRESOLVED_CONTINUE_PROTECTION')
        self.assertEqual(self.result('near_close_position')['position_handling'], 'CONTINUE_EXISTING_PROTECTION')

    def test_renderers_agree_on_every_field(self):
        for item in self.data['examples']:
            result = evaluate(self.policy, item)
            text = render_text(result, details=True)
            recovered = dict((key, json.loads(value)) for key, value in (line.strip().split(': ', 1) for line in text.split('Audit details:\n')[1].splitlines()))
            self.assertEqual(recovered, json.loads(json.dumps(result)))
            brief = render_text(result)
            for field in ['scheduled_state','observed_state','session_entry_eligibility','position_handling','policy_version','policy_hash']:
                self.assertIn(result[field], brief)

    def test_future_knowledge_overlap_and_bad_quotes(self):
        policy = copy.deepcopy(self.policy)
        policy['known_at'] = '2027-01-01T00:00:00Z'
        self.assertEqual(evaluate(policy,self.examples['at_open'])['scheduled_state'],'UNKNOWN')
        policy = copy.deepcopy(self.policy)
        policy['intervals'].append(policy['intervals'][1])
        self.assertEqual(evaluate(policy,self.examples['at_open'])['scheduled_state'],'UNKNOWN')
        for value in [-1, None, float('nan'), True]:
            item = dict(self.examples['at_open'], quote_age_seconds=value)
            self.assertEqual(evaluate(self.policy,item)['session_entry_eligibility'],'BLOCKED')

    def test_never_predict_open_across_future_conflict(self):
        for start in ['2026-09-22T05:59:59.500000Z','2026-09-22T06:00:00Z']:
            policy = copy.deepcopy(self.policy)
            policy['intervals'].append({'start':start,'end':'2026-09-22T07:00:00Z','state':'CLOSED','reason':'conflict'})
            self.assertIsNone(evaluate(policy,self.examples['before_open'])['next_expected_transition'])
        policy = copy.deepcopy(self.policy)
        policy['intervals'][1]['state'] = 'INVALID'
        self.assertIsNone(evaluate(policy,self.examples['before_open'])['next_expected_transition'])


if __name__ == '__main__':
    unittest.main()
