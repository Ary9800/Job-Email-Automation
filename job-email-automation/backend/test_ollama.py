"""
Test Ollama extraction on LinkedIn screenshots.

Usage:
  1. Install Ollama: https://ollama.com
  2. ollama pull llama3.2-vision
  3. Put screenshots in test-screenshots/ folder
  4. python test_ollama.py

Or test a single image:
  python test_ollama.py path/to/screenshot.png
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.extractor import extract_job_from_screenshot, _extract_email_regex
from app.services.llm import ollama
from app.services.email_generator import generate_both_emails

TEST_DIR = Path(__file__).parent.parent / "test-screenshots"

# Expected results for the 3 sample LinkedIn screenshots (for validation)
EXPECTED = {
    "piyusha": {
        "recruiter_email": "piyusha.r@apideltech.com",
        "recruiter_name": "Piyusha",
        "role": "Java",
        "company": "Apidel",
    },
    "simran": {
        "recruiter_email": "simran.kumari@programming.com",
        "recruiter_name": "Simran",
        "role": "Java Developer",
    },
    "bhavika": {
        "recruiter_email": "bhavika.bhagchandani@spec-india.com",
        "recruiter_name": "Bhavika",
        "role": "Java Developer",
        "company": "SPEC INDIA",
    },
}


def check_ollama():
    print("=" * 60)
    print("OLLAMA STATUS")
    print("=" * 60)
    if not ollama.is_available():
        print("FAIL: Ollama is not running.")
        print("  Fix: Install from https://ollama.com and run 'ollama serve'")
        return False

    models = ollama.list_models()
    print(f"OK: Ollama running at {ollama.base_url}")
    print(f"Models installed: {', '.join(models) or 'none'}")

    vision_ok = ollama.has_model(ollama.vision_model)
    text_ok = ollama.has_model(ollama.text_model)
    print(f"Vision model ({ollama.vision_model}): {'OK' if vision_ok else 'MISSING - run: ollama pull ' + ollama.vision_model}")
    print(f"Text model ({ollama.text_model}): {'OK' if text_ok else 'MISSING - run: ollama pull ' + ollama.text_model}")
    return vision_ok


def test_image(path: Path):
    print("\n" + "=" * 60)
    print(f"TESTING: {path.name}")
    print("=" * 60)

    result = extract_job_from_screenshot(path)

    print(f"  Email:      {result.recruiter_email or 'NOT FOUND'}")
    print(f"  Recruiter:  {result.recruiter_name or '—'}")
    print(f"  Role:       {result.role or '—'}")
    print(f"  Company:    {result.company or '—'}")
    print(f"  Location:   {result.location or '—'}")
    print(f"  Skills:     {', '.join(result.skills_required or []) or '—'}")
    print(f"  Confidence: {result.confidence}")
    if result.content_summary:
        print(f"  AI Summary: {result.content_summary}")

    if not result.recruiter_email:
        print("\n  WARNING: No email extracted!")
        print("  Tip: Crop screenshot to show ONLY the post with the email address.")
        return False

    # Generate sample email
    ai_email, static_email = generate_both_emails(
        result,
        SenderProfile(name="Aryan Jaiswal", email="aryan@example.com"),
        EmailTemplate(),
        CandidateProfile(
            years_experience="3+ years",
            experience_summary=(
                "I have 3+ years of hands-on experience in Java Full Stack Application Development, "
                "working with technologies such as Java, Spring Boot, REST APIs, SQL, and frontend frameworks."
            ),
        ),
    )
    print("\n  AI GENERATED EMAIL:")
    print("  " + "-" * 50)
    for line in ai_email.body.split("\n"):
        print(f"  {line}")
    print("  " + "-" * 50)
    print(f"  To: {ai_email.to_email}")
    print(f"  Subject: {ai_email.subject}")
    print("\n  STATIC TEMPLATE (fallback):")
    print("  " + "-" * 50)
    for line in static_email.body.split("\n"):
        print(f"  {line}")
    print("  " + "-" * 50)
    return True


def main():
    if not check_ollama():
        sys.exit(1)

    images = []
    if len(sys.argv) > 1:
        images = [Path(sys.argv[1])]
    elif TEST_DIR.exists():
        images = list(TEST_DIR.glob("*.png")) + list(TEST_DIR.glob("*.jpg")) + list(TEST_DIR.glob("*.jpeg"))
    else:
        TEST_DIR.mkdir(parents=True, exist_ok=True)
        print(f"\nNo test images found. Add LinkedIn screenshots to: {TEST_DIR}")
        print("Then run: python test_ollama.py")
        sys.exit(0)

    if not images:
        print(f"\nNo images in {TEST_DIR}. Add your LinkedIn screenshots there.")
        sys.exit(0)

    passed = sum(1 for img in images if test_image(img))
    print("\n" + "=" * 60)
    print(f"RESULT: {passed}/{len(images)} screenshots extracted email successfully")
    print("=" * 60)


if __name__ == "__main__":
    main()
