// Shared by the local preview server and isolated browser tests.
// These synthetic contest IDs keep sample results separate from real cached results.
export const demoProblem = { contestId: 900001, index: 'C', rating: 1500, name: 'A Walk Through the Array' };

export const demoHtml = `
<div class="problem-statement">
  <div class="header">
    <div class="title">C. A Walk Through the Array</div>
    <div class="time-limit"><div class="property-title">time limit per test</div>2 seconds</div>
    <div class="memory-limit"><div class="property-title">memory limit per test</div>256 megabytes</div>
  </div>
  <div><p>You are given an array of integers. On each move, choose two neighboring
  elements and replace them with their sum. Find the smallest number of moves
  needed to make every remaining element equal.</p>
  <p>This sample problem lets you check reading, scrolling, tables, and sample input
  in the phone preview. Try rotating the phone or changing the text width in Settings.</p></div>
  <div class="input-specification"><div class="section-title">Input</div>
    <p>The first line contains the number of test cases.</p>
    <p>Each test case contains the array length, followed by the array elements.</p>
  </div>
  <div class="output-specification"><div class="section-title">Output</div>
    <p>For each test case, print the minimum number of moves.</p>
  </div>
  <div class="sample-tests"><div class="section-title">Example</div>
    <div class="sample-test">
      <div class="input"><div class="title">Input</div><pre><div class="test-example-line test-example-line-0">2</div><div class="test-example-line test-example-line-1">5</div><div class="test-example-line test-example-line-1">1 2 3 2 1</div><div class="test-example-line test-example-line-2">4</div><div class="test-example-line test-example-line-2">2 2 2 2</div></pre></div>
      <div class="output"><div class="title">Output</div><pre>2\n0</pre></div>
    </div>
  </div>
  <div class="note"><div class="section-title">Note</div>
    <p>In the first test case, merge the first pair and the last pair.</p>
    <table><caption>Example moves</caption><tbody>
      <tr><th>Step</th><th>Array before the move</th><th>Array after the move</th><th>Equal elements?</th></tr>
      <tr><td>1</td><td>1, 2, 3, 2, 1</td><td>3, 3, 2, 1</td><td>No</td></tr>
      <tr><td>2</td><td>3, 3, 2, 1</td><td>3, 3, 3</td><td>Yes</td></tr>
    </tbody></table>
    <p>End of sample statement.</p>
  </div>
</div>`;

type ActiveMatch = {
  id: number; contest_id: number; problem_index: string; problem_name: string;
  start_ts: number; deadline_ts: number;
};

export function createDemoApi() {
  const now = () => Math.floor(Date.now() / 1000);
  let active: ActiveMatch | null = null;
  let elo = 1537;
  const history = [{
    id: 900001, contest_id: 900001, problem_index: 'C', problem_name: demoProblem.name,
    problem_rating: 1500, result: 'win', elo_before: 1521, elo_after: 1537,
    start_ts: 1788825600, solved_ts: 1788826200,
  }];
  const state = () => ({
    elo, seeded: false, wins: 1, losses: history.length - 1,
    server_now: now(), active, history,
  });

  return (pathname: string, method = 'GET'): { status: number; body: unknown } => {
    let body: unknown;
    switch (`${method} ${pathname}`) {
      case 'GET /api/pick':
        body = { problem: demoProblem, html: demoHtml };
        break;
      case 'GET /api/linemap':
        body = { linemap: null };
        break;
      case 'GET /api/participations':
        body = { official_rating: 1537, participations: [{
          contest_id: 900001, contest_name: 'Sample Round (Div. 2)',
          participation_type: 'contestant', start_time: 1788825600,
        }] };
        break;
      case 'GET /api/perf':
        body = {
          contest_id: 900001, contest_name: 'Sample Round (Div. 2)', points: 2250,
          penalty: 0, rating: 1521, rank: 1234, delta: 16, performance: 1650,
          participation_type: 'contestant', result_status: 'normal', user_was_rated: true,
        };
        break;
      case 'GET /api/ranked/state':
        body = state();
        break;
      case 'POST /api/ranked/queue':
        active ??= {
          id: 900001 + history.length, contest_id: 900001, problem_index: 'C',
          problem_name: demoProblem.name, start_ts: now(), deadline_ts: now() + 25 * 60,
        };
        body = { ...state(), html: demoHtml };
        break;
      case 'GET /api/ranked/problem':
        body = { match_id: active?.id, html: demoHtml };
        break;
      case 'POST /api/ranked/surrender':
        if (active) {
          history.unshift({ ...active, problem_rating: 1500, result: 'surrender',
            elo_before: elo, elo_after: elo - 16, solved_ts: now() });
          elo -= 16;
          active = null;
        }
        body = state();
        break;
      case 'GET /api/ranked/review':
      case 'POST /api/ranked/solution':
        body = { html: demoHtml, solution: {
          status: 'done', model: 'sample',
          content_md: '## Approach\nTry each possible number of equal segments. If the total sum is divisible by that number, scan the array and form segments with that sum.\n\n## Complexity\nA simple implementation takes O(n²) time and O(1) extra space.',
        } };
        break;
      default:
        return { status: 404, body: { detail: `No sample response for ${method} ${pathname}` } };
    }
    return { status: 200, body };
  };
}
