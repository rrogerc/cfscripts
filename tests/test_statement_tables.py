import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from cfscripts.core.scraper import get_sample_input_lines, html_to_text
from cfscripts.core.statements import extract_statement


PAGE = Path(__file__).with_name('fixtures').joinpath('codeforces_2109_c1.html').read_text()
SOURCE = 'https://codeforces.me/problemset/problem/2109/C1?locale=en'


class OriginalStatementTests(unittest.TestCase):
    def test_real_command_and_explanation_tables_keep_cells_spans_and_math(self):
        soup = BeautifulSoup(extract_statement(PAGE, 2109, 'C1', SOURCE), 'html.parser')
        tables = soup.select('table')
        self.assertEqual([len(t.select('tr')) for t in tables], [8, 11])
        self.assertEqual(len(tables[0].select('[rowspan="2"]')), 9)
        self.assertEqual([c.get_text() for c in tables[0].select('tr')[0].select('td')],
                         ['Command', 'Constraint', 'Result', 'Case', 'Update', "Jury's response"])
        self.assertIn(r'$$$-10^{18} \le y \le 10^{18}$$$', tables[0].get_text())
        self.assertIn('Solution', tables[1].get_text())
        self.assertIn('Interaction', soup.get_text())
        original = BeautifulSoup(PAGE, 'html.parser')
        self.assertEqual([pre.get_text() for pre in soup.select('pre')],
                         [pre.get_text() for pre in original.select('.problem-statement pre')])

    def test_unsafe_html_is_removed_without_removing_table_content(self):
        unsafe = PAGE.replace('<table class="tex-tabular">',
                              '<script>alert(1)</script><table onclick="alert(1)" class="tex-tabular">', 1)
        unsafe = unsafe.replace('</td>', '<a href="javascript:alert(1)">Unsafe link</a>'
                                '<img src="/images/diagram.png" onerror="alert(1)"></td>', 1)
        soup = BeautifulSoup(extract_statement(unsafe, 2109, 'C1', SOURCE), 'html.parser')
        self.assertEqual(len(soup.select('table')), 2)
        self.assertIsNone(soup.find('script'))
        self.assertFalse(soup.select('[onclick], [onerror], a[href^="javascript:"]'))
        self.assertEqual(soup.img['src'], 'https://codeforces.me/images/diagram.png')

    def test_wrong_problem_language_or_incomplete_page_is_rejected(self):
        pages = [PAGE.replace('2109C1 - Codeforces', '2108C1 - Codeforces'),
                 PAGE.replace('>Input<', '>Входные данные<'),
                 PAGE.replace('class="sample-test"', 'class="missing"'),
                 '<html><title>Please verify your browser</title></html>']
        for page in pages:
            with self.subTest(page=page[:60]), self.assertRaises(ValueError):
                extract_statement(page, 2109, 'C1', SOURCE)

    def test_per_line_sample_divs_survive_sanitization(self):
        soup = BeautifulSoup(PAGE, 'html.parser')
        pre = soup.select_one('.sample-test .input pre')
        pre.clear()
        for value in ['2', '100', '', '0']:
            line = soup.new_tag('div')
            line.string = value
            pre.append(line)
        html = extract_statement(str(soup), 2109, 'C1', SOURCE)
        self.assertEqual(get_sample_input_lines(html), ['2', '100', '', '0'])

    def test_model_prompt_expands_merged_cells_with_explicit_boundaries(self):
        html = extract_statement(PAGE, 2109, 'C1', SOURCE)
        prompt = html_to_text(html)
        self.assertIn("Command | Constraint | Result | Case | Update | Jury's response", prompt)
        self.assertIn('Solution | Jury | Explanation', prompt)
        add_rows = [line for line in prompt.splitlines() if line.startswith('"add') and ' | ' in line]
        self.assertEqual(len(add_rows), 2)
        self.assertTrue(all(r'$$$-10^{18} \le y \le 10^{18}$$$' in line for line in add_rows))


if __name__ == '__main__':
    unittest.main()
