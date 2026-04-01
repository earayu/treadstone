from treadstone.models.waitlist import ApplicationStatus, WaitlistApplication


def test_waitlist_application_fields_exist():
    app = WaitlistApplication()
    for field in (
        "id",
        "email",
        "name",
        "target_tier",
        "company",
        "github_or_portfolio_url",
        "use_case",
        "user_id",
        "status",
        "processed_at",
    ):
        assert hasattr(app, field)


def test_application_status_values():
    assert ApplicationStatus.PENDING == "pending"
    assert ApplicationStatus.APPROVED == "approved"
    assert ApplicationStatus.REJECTED == "rejected"


def test_waitlist_application_default_status():
    app = WaitlistApplication(status=ApplicationStatus.PENDING)
    assert app.status == ApplicationStatus.PENDING
