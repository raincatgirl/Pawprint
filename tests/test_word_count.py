"""The content-depth check counts letters, not words.

``_WORD_RE`` is a single-character class, and the depth check applies it with
``findall``, which returns one match per *character*. So a page of ordinary
English prose came out at roughly four times its real length, and the 300-word
"thick enough to be worth citing" threshold was crossed at about 74 real words.
A genuinely thin page scored 20 points for depth, and the report stated a number
the author could check against a word processor and find wrong by a factor of
four. Content depth is one of the five checks, so this moved a score the user
reads as a verdict on their own site.

The class has a real job to do: Chinese and Japanese do not separate words with
spaces, so counting runs of Latin characters misses most of a CJK page entirely.
Counting one character at a time fixes Latin and would have counted every
ideograph as a word. The answer is both, in one pass: a run of word characters
is one word, and an ideograph is one word.
"""

from __future__ import annotations

from pawprint.audit import count_words, run_checks
from pawprint.content import collect


def _depth_check(tmp_path, body):
    (tmp_path / "a.md").write_text("# A\n\n" + body + "\n", encoding="utf-8")
    checks = run_checks(str(tmp_path), collect(str(tmp_path)))
    return next(c for c in checks if c.name == "content depth")


# The unit itself. These are the cases that were wrong, stated as plain
# arithmetic so a failure names the number that is off.


def test_english_prose_counts_words_not_letters():
    assert count_words("The quick brown fox jumps over the lazy dog") == 9


def test_a_real_word_is_not_four_words():
    # "dog" is four characters. Counting characters reported 36 words for a
    # nine-word sentence.
    assert count_words("dog") == 1


def test_whitespace_runs_do_not_create_words():
    assert count_words("one   two\n\nthree\t\tfour ") == 4


def test_punctuation_does_not_create_words():
    assert count_words("Hello, world! Is this right? Yes; it is.") == 8


def test_empty_and_punctuation_only_text_is_zero():
    assert count_words("") == 0
    assert count_words("   \n\n  ") == 0
    assert count_words("--- ... , ; : !?") == 0


def test_hyphenated_and_apostrophised_words_are_one_word():
    assert count_words("It's a well-known self-contained example.") == 5


def test_digits_count_as_part_of_a_word():
    # `load_user_profile` and `max_tokens` are the identifiers the plain text
    # exists to preserve, and they are exactly the things a site is written
    # around. Splitting them on the underscore would report a code sample as a
    # page with a great many words in it.
    assert count_words("Set max_tokens before calling load_user_profile().") == 5


def test_cjk_counts_one_character_per_word():
    # Chinese and Japanese do not put spaces between words, so a run-based count
    # reads most of a CJK page as one enormous word.
    assert count_words("这是一段中文文本") == 8


def test_mixed_scripts_count_each_their_own_way():
    assert count_words("The 年 model") == 3


def test_cjk_punctuation_is_not_a_word():
    # Full-width commas and full stops are not words, and they are the same
    # class of thing the ASCII branch already declines to count.
    assert count_words("你好，世界。") == 4


# The same bug, seen where the user sees it: through the check's own detail
# line, which is a number the author will check for themselves.
#
# `_depth_check` writes a `# A` heading above the body, and the heading is part
# of the page's text, so it contributes one word. The fixtures below are sized
# to leave room for it.


def _sentence(n):
    words = ("The quick brown fox jumps over the lazy dog while the cat watches. " * 400).split()
    return " ".join(words[:n])


def test_reported_word_count_is_the_real_word_count(tmp_path):
    check = _depth_check(tmp_path, _sentence(49))
    assert check.detail == "50 words — too thin to be cited"


def test_a_thin_page_is_reported_as_thin(tmp_path):
    # 74 real words used to be reported as 301 and passed the bar outright.
    check = _depth_check(tmp_path, _sentence(74))
    assert not check.passed
    assert "too thin" in check.detail


def test_the_threshold_is_the_real_word_count(tmp_path):
    # 299 words of body is 300 counted with the heading, which is exactly the
    # bar. Anything shorter must fail, and this is the assertion that would
    # have caught the four-times-too-high count.
    assert _depth_check(tmp_path, _sentence(298)).passed is False
    assert _depth_check(tmp_path, _sentence(299)).passed is True


def test_substantial_page_reports_its_real_size(tmp_path):
    check = _depth_check(tmp_path, _sentence(3199))
    assert check.passed
    assert check.detail == "3200 words — substantial"


def test_a_cjk_page_is_still_counted_rather_than_missed(tmp_path):
    # The reason the character class existed at all. 3000 ideographs is a real
    # three thousand words of content and must not read as one enormous word.
    check = _depth_check(tmp_path, "字" * 2999)
    assert check.passed
    assert check.detail == "3000 words — substantial"
