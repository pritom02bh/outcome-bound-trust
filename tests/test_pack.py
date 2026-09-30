"""Paper pack (eval/pack.py): cell typing, TLC summary parsing, and LaTeX rows read back for verification."""
from eval import pack


def test_plain_numbers_become_numbers_and_the_rest_stays_as_printed():
    assert pack._num("1,314,397,838") == 1314397838 and pack._num("5.43") == 5.43 and pack._num("0") == 0
    assert pack._num("43.1 [37.0, 50.5]") == "43.1 [37.0, 50.5]" and pack._num("n/a") == "n/a"
    assert pack._num("21/30") == "21/30"


def test_tlc_rows_keep_the_violation_text_and_mark_na_rows():
    text = ("# bounds: x\nmutant verdict violation distinct_states depth runtime_s\n"
            "none         PASS               none                                     55007884     30       168\n"
            "I1           CAUGHT(I1)         Action property I1 is violated            1397603     23         5\n"
            "I2           N/A                not applicable at A' (unreachable)\n")
    assert pack._tlc_rows(text) == [["none", "PASS", "none", "55007884", "30", "168"],
                                    ["I1", "CAUGHT(I1)", "Action property I1 is violated", "1397603", "23", "5"],
                                    ["I2", "N/A", "not applicable at A' (unreachable)", "-", "-", "-"]]


def test_tex_rows_read_back_unescaped():
    tex = "\\toprule\na & b \\\\\n\\midrule\nobt+planner & 43.1 [37.0, 50.5] & 5.43 \\\\\nS\\_main \\& co & 1 & 2 \\\\\n\\bottomrule\n"
    assert pack._tex_rows(tex) == [["obt+planner", "43.1 [37.0, 50.5]", "5.43"], ["S_main & co", "1", "2"]]
