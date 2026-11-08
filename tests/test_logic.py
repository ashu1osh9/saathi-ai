import unittest
from datetime import datetime, timezone
from logic import decide_command, digest_message, extract_draft, parse_draft, parse_reminder

class TestCommands(unittest.TestCase):
    def test_read(self):
        self.assertEqual(decide_command('Mera latest message padho'), 'read')
    def test_summary(self):
        self.assertEqual(decide_command('Iska summary batao'), 'summary')
    def test_draft(self):
        self.assertEqual(decide_command('message likho main kal aunga'), 'draft')
        self.assertEqual(extract_draft('message likho main kal aunga'), 'main kal aunga')
    def test_reminder(self):
        self.assertEqual(decide_command('Mujhe kal yaad dilana'), 'reminder')
    def test_sensitive_message(self):
        d = digest_message('Your OTP is 4567. Visit https://example.com for payment.')
        self.assertTrue(d['warnings'])
        self.assertEqual(d['method'], 'extractive')

    def test_hindi_and_hinglish_variants(self):
        for text, intent in [('साथी मेरा संदेश पढ़ो', 'read'), ('मेरे मैसेज सुनाओ', 'read'), ('Saathi, sab messages padho', 'read'), ('इसका सारांश बताओ', 'summary'), ('मुझे कल याद दिलाना', 'reminder'), ('मदद करो', 'help'), ('हाँ।', 'confirm'), ('नहीं', 'cancel'), ('stop speaking', 'stop')]:
            with self.subTest(text=text):
                self.assertEqual(decide_command(text), intent)

    def test_no_substring_or_negated_actions(self):
        for text in ['prototype message', 'already have a message', 'screenshot', 'typewriter', 'do not read my message', 'मत message पढ़ो', 'mera message mat padho', 'reminder nahi set karo', 'yes please send everything']:
            with self.subTest(text=text):
                self.assertEqual(decide_command(text), 'unknown')

    def test_draft_content_not_rerouted(self):
        text = 'Ravi ko message likho, kal reminder aur summary bhej dena'
        self.assertEqual(decide_command(text), 'draft')
        draft = parse_draft(text)
        self.assertEqual(draft['recipient'], 'Ravi')
        self.assertEqual(draft['body'], 'kal reminder aur summary bhej dena')

    def test_observed_prisma_draft_prefix_variant_is_bounded(self):
        transcript = 'रावी को message लाखो, मैं कल आऊँगा।'
        self.assertEqual(decide_command(transcript), 'draft')
        self.assertEqual(parse_draft(transcript)['recipient'], 'रावी')
        self.assertEqual(extract_draft(transcript), 'मैं कल आऊँगा।')
        self.assertEqual(decide_command('लाखो रुपये हैं'), 'unknown')
        self.assertEqual(decide_command('message में लाखो रुपये हैं'), 'unknown')

    def test_preserves_authored_reply(self):
        for text, expected in [('जवाब लिखो मैं कल आऊँगा', 'मैं कल आऊँगा'), ('Draft a reply: Please do not change this!', 'Please do not change this!'), ('Message likho main aa raha hoon', 'main aa raha hoon'), ('Reply likho', '')]:
            with self.subTest(text=text):
                self.assertEqual(extract_draft(text), expected)

    def test_relative_reminder_and_note(self):
        now = datetime(2026, 11, 8, 10, 0, tzinfo=timezone.utc)
        for text in ['5 minute baad paani peena yaad dilana', 'पांच मिनट बाद paani peena याद दिलाना', 'remind me in five minutes paani peena']:
            with self.subTest(text=text):
                reminder = parse_reminder(text, now)
                self.assertEqual(reminder['due_at'], '2026-11-08T15:35:00+05:30')
                self.assertEqual(reminder['note'], 'paani peena')
                self.assertEqual(reminder['clarification'], '')

    def test_explicit_hindi_time(self):
        now = datetime(2026, 11, 8, 10, 0, tzinfo=timezone.utc)
        for text in ['kal shaam 4 baje meeting yaad dilana', 'कल शाम चार बजे meeting याद दिलाना', 'tomorrow 4pm meeting reminder', '2026-11-09 16:00 meeting reminder']:
            with self.subTest(text=text):
                reminder = parse_reminder(text, now)
                self.assertEqual(reminder['due_at'], '2026-11-09T16:00:00+05:30')
                self.assertEqual(reminder['note'], 'meeting')

    def test_ambiguous_invalid_or_past_time_requires_choice(self):
        now = datetime(2026, 11, 8, 10, 0, tzinfo=timezone.utc)
        for text in ['kal 4 baje meeting reminder', 'kal meeting reminder', 'today 9am meeting reminder', 'tomorrow 13pm meeting reminder', '2026-99-99 16:00 meeting reminder', 'reminder set karo']:
            with self.subTest(text=text):
                reminder = parse_reminder(text, now)
                self.assertIsNone(reminder['due_at'])
                self.assertTrue(reminder['clarification'])

    def test_does_not_change_do_in_reminder_note(self):
        now = datetime(2026, 11, 8, 10, 0, tzinfo=timezone.utc)
        self.assertEqual(parse_reminder('remind me in 5 minutes do yoga', now)['note'], 'do yoga')

    def test_client_timezone_used(self):
        now = datetime(2026, 11, 8, 10, 0, tzinfo=timezone.utc)
        result = parse_reminder('tomorrow 4pm meeting reminder', now, utc_offset_minutes=-300)
        self.assertEqual(result['due_at'], '2026-11-09T16:00:00-05:00')

if __name__=='__main__': unittest.main()
