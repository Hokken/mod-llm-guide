"""Opt-in queue integration tests in an isolated, disposable MySQL database.

Requires GUIDE_TEST_CONFIG and GUIDE_TEST_QUEUE_DB=1. Creates and removes only
a uniquely named llm_guide_test_* schema; never processes real player requests.
"""

import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm_guide_bridge import LLMBridge, parse_conf_file


@unittest.skipUnless(os.environ.get('GUIDE_TEST_CONFIG') and
                     os.environ.get('GUIDE_TEST_QUEUE_DB') == '1',
                     'Opt-in disposable database check')
class QueueDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = parse_conf_file(os.environ['GUIDE_TEST_CONFIG'])
        if os.environ.get('GUIDE_TEST_DB_HOST'):
            cls.config['LLMGuide.Database.Host'] = os.environ['GUIDE_TEST_DB_HOST']
        admin = LLMBridge(cls.config).get_db_connection()
        cls.database = 'llm_guide_test_' + uuid.uuid4().hex
        cursor = admin.cursor()
        try:
            cursor.execute(f'CREATE DATABASE `{cls.database}`')
        finally:
            cursor.close()
            admin.close()
        cls.addClassCleanup(cls.drop_test_database)
        cls.config['LLMGuide.Database.Name'] = cls.database
        LLMBridge(cls.config)._ensure_table_exists()

    @classmethod
    def drop_test_database(cls):
        # Exact schema created by this test invocation; never a configured DB.
        assert cls.database.startswith('llm_guide_test_')
        assert len(cls.database) == len('llm_guide_test_') + 32
        conn = LLMBridge(cls.config).get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f'DROP DATABASE `{cls.database}`')
        finally:
            cursor.close()
            conn.close()

    def setUp(self):
        self.bridge = LLMBridge(self.config)
        self.conn = self.bridge.get_db_connection()
        self.cursor = self.conn.cursor()
        self.addCleanup(self.conn.close)
        self.addCleanup(self.cursor.close)
        self.cursor.execute('DELETE FROM llm_guide_queue')

    def insert_request(self, guid=1):
        self.cursor.execute('''
            INSERT INTO llm_guide_queue
                (character_guid, character_name, question, character_context)
            VALUES (%s, 'Test', 'hello', %s)
        ''', (guid, 'Full context ' * 100))
        return self.cursor.lastrowid

    def status(self, request_id):
        self.cursor.execute('SELECT status FROM llm_guide_queue WHERE id = %s',
                            (request_id,))
        return self.cursor.fetchone()[0]

    def test_migration_is_idempotent_and_preserves_context(self):
        request_id = self.insert_request()
        self.bridge._ensure_table_exists()
        self.cursor.execute('''
            SELECT LENGTH(character_context) FROM llm_guide_queue WHERE id = %s
        ''', (request_id,))
        self.assertGreater(self.cursor.fetchone()[0], 500)

    def test_only_one_worker_claims_and_cancellation_wins(self):
        request_id = self.insert_request()
        other = LLMBridge(self.config)
        self.assertTrue(self.bridge.mark_processing(self.cursor, request_id))
        self.assertFalse(other.mark_processing(self.cursor, request_id))
        self.cursor.execute("UPDATE llm_guide_queue SET status = 'cancelled' "
                            "WHERE id = %s", (request_id,))
        self.assertFalse(self.bridge.save_response(self.cursor, request_id, 'late'))
        self.assertEqual(self.status(request_id), 'cancelled')

    def test_expired_lease_recovery_rejects_old_worker(self):
        request_id = self.insert_request()
        self.bridge.mark_processing(self.cursor, request_id)
        self.cursor.execute('''
            UPDATE llm_guide_queue SET lease_until = NOW() - INTERVAL 1 SECOND
            WHERE id = %s
        ''', (request_id,))
        other = LLMBridge(self.config)
        self.assertEqual(other.fetch_pending_requests(self.cursor)[0][0], request_id)
        self.assertTrue(other.mark_processing(self.cursor, request_id))
        self.assertFalse(self.bridge.save_response(self.cursor, request_id, 'old'))
        self.assertTrue(other.save_response(self.cursor, request_id, 'new'))
        self.assertEqual(self.status(request_id), 'complete')

    def test_retry_budget_and_per_character_order(self):
        first = self.insert_request(1)
        self.insert_request(1)
        third = self.insert_request(2)
        self.assertEqual([row[0] for row in
                          self.bridge.fetch_pending_requests(self.cursor)],
                         [first, third])
        self.bridge.mark_processing(self.cursor, first)
        self.cursor.execute('''
            UPDATE llm_guide_queue
            SET lease_until = NOW() - INTERVAL 1 SECOND, attempts = %s
            WHERE id = %s
        ''', (self.bridge.max_attempts, first))
        self.bridge.fetch_pending_requests(self.cursor)
        self.assertEqual(self.status(first), 'error')


if __name__ == '__main__':
    unittest.main()
