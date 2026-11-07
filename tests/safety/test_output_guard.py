from retail_analyst.core.config import get_settings
from retail_analyst.safety.output_guard import redact

SAFETY = get_settings().safety


def test_email_and_phone_are_removed() -> None:
    result = redact("Contact jane.doe@example.com or call 212-555-0187.", SAFETY, allowed=set())
    assert "jane.doe@example.com" not in result.text
    assert "212-555-0187" not in result.text
    assert "EMAIL_ADDRESS" in result.removed


def test_invented_person_names_are_removed() -> None:
    result = redact("Your top customer is John Smith from Texas.", SAFETY, allowed=set())
    assert "John Smith" not in result.text
    assert "Texas" in result.text


def test_values_from_query_results_are_kept() -> None:
    text = "Calvin Klein and Tommy Hilfiger led revenue in California."
    result = redact(text, SAFETY, allowed={"Calvin Klein", "Tommy Hilfiger"})
    assert result.text == text


def test_single_capitalized_words_are_not_treated_as_people() -> None:
    text = "Revenue excludes items with status Cancelled or Returned."
    assert redact(text, SAFETY, allowed=set()).text == text
