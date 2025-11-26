import unittest
import sys
import os

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from docx_analyzer.writer import parse_review_for_comments

class TestBugReproduction(unittest.TestCase):
    def test_bolded_format(self):
        # This is the format shown in the LLM prompt example
        review_text = '- **[段落 5] "損害賠償"** 上限が不明確'
        
        result = parse_review_for_comments(review_text)
        
        print(f"Result for bolded input: {result}")
        
        self.assertIn(5, result)
        quoted_text, comment_text = result[5][0]
        self.assertEqual(quoted_text, "損害賠償")
        # Verify comment text preserves the bolding and quote
        self.assertIn('"損害賠償"', comment_text)

if __name__ == '__main__':
    unittest.main()
