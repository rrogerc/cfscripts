import os
import unittest
from unittest.mock import patch

from cfscripts.web import solutions


class Response:
    def __init__(self, status_code):
        self.status_code = status_code
        self.text = "provider detail"

    def json(self):
        return {"choices": [{"message": {"content": "answer"}}]}


class ModelFallbackTests(unittest.TestCase):
    def setUp(self):
        self.chain = [solutions.GEMINI_MODEL, *solutions.GEMINI_FALLBACK_MODELS]

    def chat(self, statuses, **env):
        """Run _chat against a canned HTTP status per model (503 unless given)."""
        self.tried = []

        def post(url, token, model, prompt):
            self.tried.append(model)
            return Response(statuses.get(model, 503))

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", **env}, clear=True), \
             patch.object(solutions, "_post", side_effect=post):
            return solutions._chat("prompt")

    def test_capacity_refusals_fall_through_every_model_in_order(self):
        oldest = self.chain[-1]
        self.assertEqual(self.chat({oldest: 200}), ("answer", oldest))
        self.assertEqual(self.tried, self.chain)

    def test_first_model_with_capacity_answers_and_later_ones_are_not_called(self):
        primary, previous = self.chain[:2]
        self.assertEqual(self.chat({primary: 429, previous: 200}), ("answer", previous))
        self.assertEqual(self.tried, [primary, previous])

    def test_every_model_out_of_capacity_reports_the_refusal(self):
        with self.assertRaisesRegex(solutions.SolutionUnavailable, "503"):
            self.chat({})
        self.assertEqual(self.tried, self.chain)

    def test_errors_another_model_cannot_fix_skip_the_fallbacks(self):
        with self.assertRaisesRegex(solutions.SolutionUnavailable, "402"):
            self.chat({self.chain[0]: 402})
        self.assertEqual(self.tried, self.chain[:1])

    def test_override_naming_a_fallback_is_not_tried_twice(self):
        override = self.chain[1]
        with self.assertRaises(solutions.SolutionUnavailable):
            self.chat({}, LLM_MODEL=override)
        self.assertEqual(self.tried, [override, *self.chain[2:]])


if __name__ == "__main__":
    unittest.main()
