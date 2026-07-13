"""Tests for CSV batch processing."""

import csv

from src.batch import BatchItem, load_batch, save_batch_results


def test_load_batch(tmp_path):
    csv_file = tmp_path / "tasks.csv"
    csv_file.write_text("file,task\nsrc/a.py,Refactor this\nsrc/b.py,Add types\n")
    items = load_batch(csv_file)
    assert len(items) == 2
    assert items[0].data["file"] == "src/a.py"
    assert items[0].data["task"] == "Refactor this"
    assert items[1].data["file"] == "src/b.py"


def test_batch_item_get_instructions():
    item = BatchItem(row_index=0, data={"file": "src/auth.py", "task": "Fix SQL injection"})
    instructions = item.get_instructions()
    assert "Fix SQL injection" in instructions
    assert "src/auth.py" in instructions


def test_save_batch_results(tmp_path):
    items = [
        BatchItem(row_index=0, data={"file": "a.py", "task": "task1"}),
        BatchItem(row_index=1, data={"file": "b.py", "task": "task2"}),
    ]
    output_path = tmp_path / "results.csv"
    save_batch_results(items, ["output1", "output2"], output_path)

    with open(output_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["output"] == "output1"
    assert rows[1]["status"] == "completed"
