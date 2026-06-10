# TODO: Review

This is the output from Claude Fable for review since last release.
The review consumed the whole 5 hours cap! So saving its results here:

Verification complete: 13 of 14 candidates survived (one refuted — the fence-content margin-collapse case turned out to be correct-by-spec since marimo's cleandoc behaves the same way).

The cap forces cutting the three weakest (pre-existing set-ordering display, and two pure-cleanup duplications). Here are the findings.

TLDR: The release range has one serious theme — the stricter negative-number tokenizer (commit 062cdd1) regresses valid CLI invocations and, worse, breaks round-tripping of commands moops itself generates for negative ranges. The new multiselect re-prompt loop (1d449d3) can crash or trap users. The markdown indentation/fence work is internally inconsistent in a few ways. All findings below were verified by agents actually running the code.

```json
  [
    {
      "file": "src/moops/_parse.py",
      "line": 9,
      "summary": "The new strict negative-number regex rejects dash-leading split values the v0.11.4 isdigit() check accepted (e.g. '-5,10', '-1_000', '-5px'),
  regressing previously-valid CLI invocations.",
      "failure_scenario": "Verified end-to-end: at v0.11.4, `script.py --range -5,10` with range_slider(start=-100, stop=100) parsed to [-5, 10]; at HEAD it
  exits 1 with 'Option --range requires a value' + 'Unexpected argument: -5,10'. Also breaks interactive mode, where a valid prompt reply like '-5,10' is
  re-parsed through the same tokenizer and dies."
    },
    {
      "file": "src/moops/_options.py",
      "line": 818,
      "summary": "RangeControl.format_value emits the split form instead of routing through option_value_token's equals form, so the script callout moops itself
  generates for negative ranges no longer round-trips through the narrowed tokenizer.",
      "failure_scenario": "Verified: a range_slider with value [-5.0, 10.0] renders '--range -5.0,10.0' in the callout/_current_args(); apply_cli_args on that
  exact string fails with 'Option --range requires a value (use --range=-5.0,10.0 ...)'. The round-trip property test misses it because its range strategy uses
  st.floats(min_value=0)."
    },
    {
      "file": "src/moops/_options.py",
      "line": 962,
      "summary": "The new multiselect re-prompt loop calls input() with no EOFError handling, so piped/non-interactive stdin ending after an invalid entry
  crashes with an uncaught traceback where the old single read exited cleanly keeping the default.",
      "failure_scenario": "Verified: `printf 'typo\\n' | script.py --interactive` with a multiselect — before 1d449d3 it kept the default and exited 0; at HEAD
  the second input() raises EOFError with a full traceback and exit 1. The driver in _value_resolution.py:97 catches only KeyboardInterrupt."
    },
    {
      "file": "src/moops/_options.py",
      "line": 968,
      "summary": "The multiselect prompt prints a numbered menu ('1) alpha') but the new validation loop rejects numeric replies that
  DropdownControl.prompt_interactive accepts, trapping users who follow the menu in an endless re-prompt.",
      "failure_scenario": "Verified: entering '1,3' at a multiselect prompt loops forever with \"invalid: ['1', '3']\" because line 968 checks `part not in
  self.select_opts`, while DropdownControl (lines 1092-1095) accepts indices. Pre-change, the same input produced one clean parse error instead of an inescapable
  loop."
    },
    {
      "file": "src/moops/_markdown.py",
      "line": 43,
      "summary": "_common_indent_margin includes the first line in the margin computation, but marimo's mo.md dedents via inspect.cleandoc which ignores the
  first line, so heading demotion misses indented headings in the common content-starts-on-the-opening-quote pattern.",
      "failure_scenario": "Verified: demote_markdown_headings('# Title\\n    ## Section\\n    body', 1) returns '## Title\\n    ## Section' — Title demoted,
  Section not — yet cleandoc renders both as headings, so the notebook shows them at the same level instead of nested."
    },
    {
      "file": "src/moops/_markdown.py",
      "line": 32,
      "summary": "strip_outer_fence treats any first line starting with three backticks as a fence opener even when the line is really inline code (CommonMark
  forbids backticks in a backtick-fence info string), then deletes the first and last lines of CLI output; v0.11.4 never lost content.",
      "failure_scenario": "Verified: strip_outer_fence('```x``` inline\\nfoo\\n```') returns 'foo', silently dropping the first line's content in CLI mode. Rare
  input shape, but it is silent content loss introduced in 5e0aa65 and carried into 6614bd7."
    },
    {
      "file": "src/moops/group.py",
      "line": 287,
      "summary": "strip_outer_fence ignores the common-indent margin that demote_markdown_headings learned to handle this release, so an indented triple-quoted
  markdown string whose body is one fenced block keeps its ``` markers in CLI output while the dedented equivalent strips them.",
      "failure_scenario": "Verified: g.md('\\n    ```\\n    hello\\n    ```\\n    ') in CLI mode prints the literal backtick fence lines (the indented closing '
    ```' is never recognized, strip_outer_fence returns None); unindented, the same content prints just 'hello'. Notebook mode renders both correctly, so CLI
  and notebook disagree."
    },
    {
      "file": "src/moops/group.py",
      "line": 290,
      "summary": "CLI markdown rendering stacks per-pattern heuristics (whole-text fence strip, then a count('`')==2 inline-span strip), and confirmed sibling
  cases remain broken — a deeper single markdown-to-terminal normalization in _markdown.py would subsume them.",
      "failure_scenario": "Verified: '```code```' (single-line fence) prints with raw backticks (strip_outer_fence declines on len(lines)<2, span branch declines
  on count 6), and ``cmd`` (double-backtick span, count 4) prints raw. Each new report of this class will add another condition in Group.md."
    },
    {
      "file": "src/moops/interface.py",
      "line": 139,
      "summary": "The equals-form hint suppression compares the raw follower token against bare rendered option names, so a follower in --opt=value form isn't
  recognized as a known option and the error prints a hint that would swallow another option's assignment.",
      "failure_scenario": "Verified: `script.py --tag --name=Bob` prints \"Option --tag requires a value (use --tag=--name=Bob ...)\" because _parse.py:52 stores
  the raw token before the '=' split while the suppression checks `follower not in rendered`. Following the hint sets tag to the literal '--name=Bob' and
  silently drops --name. Limited severity: the command fails loudly either way; only the hint misleads."
    },
    {
      "file": "src/moops/interface.py",
      "line": 137,
      "summary": "The equals-form hint interpolates the follower without shell quoting, so multi-word dash-leading followers (reachable via the editable command
  box) produce a suggestion that re-tokenizes incorrectly when followed.",
      "failure_scenario": "Verified: command text `script.py --tag '-d ev'` yields the hint 'use --tag=-d ev', which re-tokenizes via the same shlex path to
  ['--tag=-d', 'ev'] — a broken command — instead of the working --tag='-d ev'. shlex.quote(follower) in the hint fixes it without changing the common
  single-word case."
    }
  ]
```

Three more findings survived verification but were cut by the 10-item cap, all lower severity: the multiselect prompt displays default values from a set in hash order (pre-existing, _options.py:954); pathlib.PurePath(self.command).name is copy-pasted at interface.py 174/199/445 (commit 8e8dc1c had to edit all three in lockstep — a `_naming.command_name()` helper would fix that); and the caller-frame inspection block from 8ac6c44 is duplicated nearly verbatim between
group.py:233 and presets.py:142.

The two findings I'd act on first are the tokenizer pair (#1/#2): they share a root cause — the schema-free tokenizer guessing option-vs-value lexically — and #2 means moops currently displays commands to users that its own parser rejects. A deeper fix the altitude finder suggested: resolve dash-leading followers at validation time, where value_options is known, so a follower that isn't itself a known option becomes the value. That would subsume the regex, the hint
plumbing, and both regressions.
