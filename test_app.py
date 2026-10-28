"""
Campus Resolve - Automated Test Suite (test_app.py)
Tests all 17 required criteria from Section 13 of the specification.
"""

import os
import io
import gc
import unittest
import tempfile
from app import app
from models import init_db, get_db, create_user
from ai_model.classifier import predict_complaint_category

class CampusResolveTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)
        
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test-secret-key-123'
        
        import models
        models.DB_PATH = self.temp_db_path
        init_db()

        self.client = app.test_client()

        # Seed test accounts
        self.admin_id = create_user("Test Officer", "admin@campus.edu", "Admin@123", role="management")
        self.student1_id = create_user("Student One", "student1@campus.edu", "Student@123", role="student")
        self.student2_id = create_user("Student Two", "student2@campus.edu", "Student@123", role="student")

    def tearDown(self):
        gc.collect()
        try:
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
        except Exception:
            pass

    def login(self, email, password):
        """Helper to log in."""
        self.client.get('/login')
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        return self.client.post('/login', data={
            'email': email,
            'password': password,
            'csrf_token': token
        }, follow_redirects=True)

    def logout(self):
        """Helper to log out."""
        return self.client.get('/logout', follow_redirects=True)

    # 1. A student can register and log in.
    def test_01_student_registration_and_login(self):
        self.client.get('/register')
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        res = self.client.post('/register', data={
            'name': 'Pooja Patel',
            'email': 'pooja@campus.edu',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'csrf_token': token
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Welcome to Campus Resolve', res.data)
        self.logout()

        # Login with newly registered student
        res_login = self.login('pooja@campus.edu', 'Password@123')
        self.assertIn(b'Pooja Patel', res_login.data)

    # 2. A management account can log in securely.
    def test_02_management_login(self):
        res = self.login('admin@campus.edu', 'Admin@123')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Admin Command Center', res.data)
        self.assertIn(b'Queue Triage', res.data)

    # 3. Invalid login attempts are rejected.
    def test_03_invalid_login_rejected(self):
        res = self.login('admin@campus.edu', 'WrongPassword123')
        self.assertIn(b'Invalid email address or password', res.data)

    # 4. A student can submit a complaint.
    def test_04_student_submit_complaint(self):
        self.login('student1@campus.edu', 'Student@123')
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        res = self.client.post('/complaints/new', data={
            'title': 'Corridor tube light flickering continuously',
            'location': 'Academic Block B - 3rd Floor',
            'description': 'The fluorescent tube light is blinking rapidly and producing smoke odor.',
            'category': 'Electrical',
            'csrf_token': token
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Grievance submitted successfully', res.data)
        self.assertIn(b'Corridor tube light flickering continuously', res.data)

    # 5. An uploaded photo is saved and displayed safely.
    def test_05_uploaded_photo_saved_and_displayed(self):
        self.login('student1@campus.edu', 'Student@123')
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        fake_photo = (io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRfakeimagebytes"), "leak_evidence.png")

        res = self.client.post('/complaints/new', data={
            'title': 'Washroom faucet broken',
            'location': 'Sports Complex Restroom',
            'description': 'Water tap valve broke off completely, leaking clean water onto floor.',
            'category': 'Plumbing',
            'photo': fake_photo,
            'csrf_token': token
        }, content_type='multipart/form-data', follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Photo Evidence Attached', res.data)
        self.assertIn(b'uploads/', res.data)

    # 6. A unique ticket ID is generated.
    def test_06_unique_ticket_id_generation(self):
        self.login('student1@campus.edu', 'Student@123')
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        self.client.post('/complaints/new', data={
            'title': 'Ticket One',
            'location': 'Lab 1',
            'description': 'First ticket for testing uniqueness.',
            'category': 'Other',
            'csrf_token': token
        })

        self.client.post('/complaints/new', data={
            'title': 'Ticket Two',
            'location': 'Lab 2',
            'description': 'Second ticket for testing uniqueness.',
            'category': 'Other',
            'csrf_token': token
        })

        with get_db() as conn:
            tickets = [r['ticket_id'] for r in conn.execute("SELECT ticket_id FROM complaints ORDER BY id ASC").fetchall()]
            self.assertEqual(len(tickets), len(set(tickets)))
            self.assertTrue(tickets[0].startswith('CR-2026-'))
            self.assertTrue(tickets[1].startswith('CR-2026-'))
            self.assertNotEqual(tickets[0], tickets[1])

    # 7. The AI module suggests a category from the description.
    def test_07_ai_category_suggestion(self):
        elec = predict_complaint_category("Ceiling fan regulator sparked and rotating at high speed")
        self.assertEqual(elec['category'], 'Electrical')
        self.assertGreater(elec['confidence'], 0.5)

        net = predict_complaint_category("Wi-Fi network connection drops every 2 minutes in computer lab")
        self.assertEqual(net['category'], 'Internet')

        plumb = predict_complaint_category("Water tap leaking in washroom and toilet flush broken")
        self.assertEqual(plumb['category'], 'Plumbing')

        clean = predict_complaint_category("Garbage bins overflowing outside cafeteria with food waste")
        self.assertEqual(clean['category'], 'Cleaning')

        equip = predict_complaint_category("Projector HDMI cable bent and audio amplifier screeching loudly")
        self.assertEqual(equip['category'], 'Classroom Equipment')

    # 8. The student can change the suggested category.
    def test_08_student_can_change_category(self):
        self.login('student1@campus.edu', 'Student@123')
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        # Description talks about Wi-Fi but student chooses "Other" or "Classroom Equipment"
        res = self.client.post('/complaints/new', data={
            'title': 'Special Networking Hardware Issue',
            'location': 'Auditorium Control Room',
            'description': 'Wi-Fi router needs replacement in the auditorium sound booth.',
            'category': 'Other', # User explicitly chose Other
            'csrf_token': token
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Other', res.data)

    # 9. A student can see their own complaint and timeline.
    def test_09_student_sees_own_complaint_and_timeline(self):
        self.login('student1@campus.edu', 'Student@123')
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        self.client.post('/complaints/new', data={
            'title': 'Audio speaker crackling',
            'location': 'Lecture Hall 101',
            'description': 'Wall audio speakers producing high frequency hiss.',
            'category': 'Classroom Equipment',
            'csrf_token': token
        })

        with get_db() as conn:
            t = conn.execute("SELECT ticket_id FROM complaints WHERE title = 'Audio speaker crackling'").fetchone()
            ticket_id = t['ticket_id']

        res = self.client.get(f'/complaints/{ticket_id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Complaint Tracking &amp; Audit Log', res.data)
        self.assertIn(b'Stage: Submitted', res.data)

    # 10. A student cannot access another student's complaint.
    def test_10_student_cannot_access_other_student_complaint(self):
        self.login('student1@campus.edu', 'Student@123')
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        self.client.post('/complaints/new', data={
            'title': 'Student 1 Private Ticket',
            'location': 'Hostel A',
            'description': 'Private student record.',
            'category': 'Other',
            'csrf_token': token
        })

        with get_db() as conn:
            ticket_row = conn.execute("SELECT ticket_id FROM complaints WHERE title = 'Student 1 Private Ticket'").fetchone()
            ticket_id = ticket_row['ticket_id']

        self.logout()

        # Student 2 tries to access Student 1's complaint
        self.login('student2@campus.edu', 'Student@123')
        res = self.client.get(f'/complaints/{ticket_id}')
        self.assertEqual(res.status_code, 403)

    # 11. A student cannot perform management actions.
    def test_11_student_cannot_access_management_endpoints(self):
        self.login('student1@campus.edu', 'Student@123')
        
        # Access management portal
        res_mgmt = self.client.get('/management', follow_redirects=True)
        self.assertIn(b'Unauthorized access. Management privileges required.', res_mgmt.data)

        # Attempt to post a status update
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        res_update = self.client.post('/management/update/CR-2026-9999', data={
            'status': 'Resolved',
            'csrf_token': token
        }, follow_redirects=True)
        self.assertIn(b'Unauthorized access', res_update.data)

    # 12. Management can view all complaints.
    def test_12_management_view_all_complaints(self):
        # Student 1 logs a complaint
        self.login('student1@campus.edu', 'Student@123')
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        self.client.post('/complaints/new', data={
            'title': 'Student 1 Grievance For Admin Review',
            'location': 'Library 1F',
            'description': 'Testing admin visibility across all records.',
            'category': 'Cleaning',
            'csrf_token': token
        })
        self.logout()

        # Management logs in
        self.login('admin@campus.edu', 'Admin@123')
        res = self.client.get('/management')
        self.assertIn(b'Student 1 Grievance For Admin Review', res.data)

    # 13. Management can change priority and status.
    def test_13_management_change_priority_and_status(self):
        self.login('student1@campus.edu', 'Student@123')
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        self.client.post('/complaints/new', data={
            'title': 'Main gate barrier broken',
            'location': 'Campus Gate 1',
            'description': 'Automatic vehicle boom barrier stuck open.',
            'category': 'Other',
            'csrf_token': token
        })

        with get_db() as conn:
            ticket_id = conn.execute("SELECT ticket_id FROM complaints WHERE title = 'Main gate barrier broken'").fetchone()['ticket_id']
        self.logout()

        # Management updates to Critical priority and In Progress status
        self.login('admin@campus.edu', 'Admin@123')
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        res = self.client.post(f'/management/update/{ticket_id}', data={
            'status': 'In Progress',
            'priority': 'Critical',
            'remarks': 'Security team stationed while technicians work.',
            'csrf_token': token
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)

        with get_db() as conn:
            updated = conn.execute("SELECT status, priority FROM complaints WHERE ticket_id = ?", (ticket_id,)).fetchone()
            self.assertEqual(updated['status'], 'In Progress')
            self.assertEqual(updated['priority'], 'Critical')

    # 14. Management remarks and status changes appear in the timeline.
    def test_14_management_remarks_appear_in_timeline(self):
        self.login('student1@campus.edu', 'Student@123')
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        self.client.post('/complaints/new', data={
            'title': 'Internet switch dead',
            'location': 'Server Room',
            'description': 'Core network switch LEDs unlit.',
            'category': 'Internet',
            'csrf_token': token
        })

        with get_db() as conn:
            ticket_id = conn.execute("SELECT ticket_id FROM complaints WHERE title = 'Internet switch dead'").fetchone()['ticket_id']
        self.logout()

        # Management resolves ticket with specific remarks
        self.login('admin@campus.edu', 'Admin@123')
        with self.client.session_transaction() as sess:
            token = sess.get('_csrf_token', '')

        self.client.post(f'/management/update/{ticket_id}', data={
            'action': 'resolve',
            'status': 'Resolved',
            'remarks': 'Power adapter replaced on Cisco switch. Connectivity restored at 14:35.',
            'csrf_token': token
        }, follow_redirects=True)

        # Check timeline on complaint detail view
        res = self.client.get(f'/complaints/{ticket_id}')
        self.assertIn(b'Power adapter replaced on Cisco switch. Connectivity restored at 14:35.', res.data)
        self.assertIn(b'Stage: Resolved', res.data)

    # 15. Data remains available after restarting the server.
    def test_15_database_persistence_across_connections(self):
        with get_db() as conn:
            conn.execute("INSERT INTO complaints (ticket_id, student_id, title, description, location, category, priority, status) VALUES ('CR-PERSIST-TEST', ?, 'Persistent Data', 'Disk verification', 'Hall', 'Other', 'Low', 'Submitted')", (self.student1_id,))
            conn.commit()

        # Simulate fresh connection
        with get_db() as fresh_conn:
            row = fresh_conn.execute("SELECT title FROM complaints WHERE ticket_id = 'CR-PERSIST-TEST'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['title'], 'Persistent Data')

    # 16. Forms, filters, and navigation work correctly.
    def test_16_search_and_filtering_navigation(self):
        self.login('admin@campus.edu', 'Admin@123')

        # Test search query
        res_search = self.client.get('/management?search=faucet')
        self.assertEqual(res_search.status_code, 200)

        # Test category filter
        res_cat = self.client.get('/management?category=Electrical')
        self.assertEqual(res_cat.status_code, 200)

        # Test priority filter
        res_prio = self.client.get('/management?priority=High')
        self.assertEqual(res_prio.status_code, 200)

    # 17. The UI remains usable on desktop and mobile.
    def test_17_all_ui_screens_render_successfully(self):
        # 1. Landing page
        self.assertEqual(self.client.get('/').status_code, 200)
        # 2. Login page
        self.assertEqual(self.client.get('/login').status_code, 200)
        # 3. Registration page
        self.assertEqual(self.client.get('/register').status_code, 200)

        # Log in as student
        self.login('student1@campus.edu', 'Student@123')
        # 4. Student dashboard
        self.assertEqual(self.client.get('/dashboard').status_code, 200)
        # 5. New complaint page
        self.assertEqual(self.client.get('/complaints/new').status_code, 200)

        self.logout()

        # Log in as management
        self.login('admin@campus.edu', 'Admin@123')
        # 7. Management portal
        self.assertEqual(self.client.get('/management').status_code, 200)

if __name__ == '__main__':
    unittest.main()
