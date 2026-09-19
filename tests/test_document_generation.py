from pathlib import Path

from docx import Document

from backend.schemas.state import Executor, PersonalWishesState
from backend.services.document_generator import generate_document


def _paragraph_texts(document: Document) -> list[str]:
    return [paragraph.text for paragraph in document.paragraphs]


def _generate_and_open(state: PersonalWishesState, tmp_path: Path, session_id: str = "1") -> tuple[Path, Document]:
    output_path = generate_document(state, session_id=session_id, output_dir=tmp_path)
    assert output_path.exists()
    return output_path, Document(output_path)


def test_populated_state_generates_valid_docx(tmp_path: Path):
    state = PersonalWishesState(
        full_name="Rahul Sharma",
        home_address="12 MG Road, Bengaluru",
        covers_worldwide_assets=True,
        has_children=True,
        children=["Asha Sharma", "Vikram Sharma"],
        executor=Executor(name="Priya Sharma", relationship="Spouse"),
        specific_gifts=["Vintage watch to Vikram"],
        additional_wishes="Keep the family home.",
    )

    output_path, document = _generate_and_open(state, tmp_path, session_id="populated")
    texts = _paragraph_texts(document)

    assert output_path.suffix == ".docx"
    assert "PERSONAL WISHES DOCUMENT" in texts
    assert "FICTIONAL DOCUMENT — NOT LEGAL ADVICE" in texts
    assert "Full Name: Rahul Sharma" in texts
    assert "Home Address: 12 MG Road, Bengaluru" in texts
    assert "Worldwide Assets: Yes" in texts
    assert "Children: Yes" in texts
    assert "Children's Names: Asha Sharma, Vikram Sharma" in texts
    assert "Executor Name: Priya Sharma" in texts
    assert "Relationship: Spouse" in texts
    assert "Vintage watch to Vikram" in texts
    assert "Keep the family home." in texts


def test_worldwide_assets_yes_no_not_confirmed(tmp_path: Path):
    yes_texts = _paragraph_texts(
        _generate_and_open(PersonalWishesState(covers_worldwide_assets=True), tmp_path / "yes", "yes")[1]
    )
    no_texts = _paragraph_texts(
        _generate_and_open(PersonalWishesState(covers_worldwide_assets=False), tmp_path / "no", "no")[1]
    )
    null_texts = _paragraph_texts(_generate_and_open(PersonalWishesState(), tmp_path / "null", "null")[1])

    assert "Worldwide Assets: Yes" in yes_texts
    assert "Worldwide Assets: No" in no_texts
    assert "Worldwide Assets: Not confirmed" in null_texts


def test_children_false_omits_names(tmp_path: Path):
    _, document = _generate_and_open(PersonalWishesState(has_children=False), tmp_path)
    texts = _paragraph_texts(document)

    assert "Children: No" in texts
    assert not any(text.startswith("Children's Names:") for text in texts)


def test_children_true_with_names(tmp_path: Path):
    state = PersonalWishesState(has_children=True, children=["Asha", "Vikram"])
    _, document = _generate_and_open(state, tmp_path)
    texts = _paragraph_texts(document)

    assert "Children: Yes" in texts
    assert "Children's Names: Asha, Vikram" in texts


def test_children_true_without_names(tmp_path: Path):
    state = PersonalWishesState(has_children=True, children=[])
    _, document = _generate_and_open(state, tmp_path)
    texts = _paragraph_texts(document)

    assert "Children: Yes" in texts
    assert "Children's Names: Not provided" in texts


def test_executor_name_and_relationship(tmp_path: Path):
    state = PersonalWishesState(executor=Executor(name="Amit", relationship="Brother"))
    _, document = _generate_and_open(state, tmp_path)
    texts = _paragraph_texts(document)

    assert "Executor Name: Amit" in texts
    assert "Relationship: Brother" in texts


def test_missing_executor_field_shows_not_confirmed(tmp_path: Path):
    state = PersonalWishesState(executor=Executor(name="Amit", relationship=None))
    _, document = _generate_and_open(state, tmp_path)
    texts = _paragraph_texts(document)

    assert "Executor Name: Amit" in texts
    assert "Relationship: Not confirmed" in texts


def test_specific_gifts_listed_or_none_specified(tmp_path: Path):
    with_gifts = PersonalWishesState(specific_gifts=["Ring to Asha", "Books to Vikram"])
    empty = PersonalWishesState(specific_gifts=[])

    gift_texts = _paragraph_texts(_generate_and_open(with_gifts, tmp_path / "gifts", "gifts")[1])
    empty_texts = _paragraph_texts(_generate_and_open(empty, tmp_path / "empty", "empty")[1])

    assert "Ring to Asha" in gift_texts
    assert "Books to Vikram" in gift_texts
    assert "None specified" in empty_texts


def test_additional_wishes_present_or_not_confirmed(tmp_path: Path):
    present = PersonalWishesState(additional_wishes="Donate to charity.")
    missing = PersonalWishesState(additional_wishes=None)

    present_texts = _paragraph_texts(_generate_and_open(present, tmp_path / "present", "present")[1])
    missing_texts = _paragraph_texts(_generate_and_open(missing, tmp_path / "missing", "missing")[1])

    assert "Donate to charity." in present_texts
    assert "Not confirmed" in missing_texts


def test_completely_empty_state_generates_draft(tmp_path: Path):
    output_path, document = _generate_and_open(PersonalWishesState(), tmp_path, session_id="empty")
    texts = _paragraph_texts(document)

    assert output_path.exists()
    assert "PERSONAL WISHES DOCUMENT" in texts
    assert "FICTIONAL DOCUMENT — NOT LEGAL ADVICE" in texts
    assert "Full Name: Not confirmed" in texts
    assert "Home Address: Not confirmed" in texts
    assert "Worldwide Assets: Not confirmed" in texts
    assert "Children: Not confirmed" in texts
    assert not any(text.startswith("Children's Names:") for text in texts)
    assert "Executor Name: Not confirmed" in texts
    assert "Relationship: Not confirmed" in texts
    assert "None specified" in texts
