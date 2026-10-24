import life


def _fresh(tmp_path):
    import config
    config.NOTES_FILE = tmp_path / "n.json"
    config.EXPENSES_FILE = tmp_path / "e.json"
    life._notes = life._exp = None


def test_notes(tmp_path):
    _fresh(tmp_path)
    assert "Noted" in life.handle("note: call the bank")
    assert "call the bank" in life.handle("show my notes")
    assert life.handle("note that I like tea") is None          # memory owns "note that"
    assert "Deleted" in life.handle("delete note 1")


def test_expenses(tmp_path):
    _fresh(tmp_path)
    assert "food" in life.handle("I spent 250 on lunch")
    life.handle("spent ₹1,200 on uber")
    out = life.handle("show expenses")
    assert "₹1,450" in out and "travel" in out
    assert "Removed" in life.handle("undo expense")


def test_convert_clock_split_dice():
    assert life.handle("convert 5 km to miles").startswith("5 km = 3.107")
    assert "212" in life.handle("100 c to f")
    assert life.handle("5 apples to pears") is None
    assert "Tokyo" in life.handle("what time is it in tokyo")
    assert "₹660 each" in life.handle("split 2400 among 4 with 10% tip")
    assert life.handle("random number between 5 and 5").endswith("5")
    assert len(life.handle("generate a 20 character password").split()[1]) == 20
    assert life.handle("how are you") is None
