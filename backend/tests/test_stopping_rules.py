"""Tests for stopping rules: DB configuration, Settings fallback, and rule evaluation."""

from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.domain.enums import FailureCategory
from app.models.case import RecoveryCase
from app.models.stopping_rule import StoppingRuleConfig
from app.services import stopping_rules
from app.services.stopping_rules import DEFAULT_STOPPING_RULES


def test_stopping_rules_fallback_to_settings_when_db_empty(db_session):
    # Ensure no DB row exists for this category
    db_session.query(StoppingRuleConfig).filter_by(
        failure_category=FailureCategory.INSUFFICIENT_FUNDS
    ).delete()
    db_session.commit()

    settings = get_settings()
    rule = stopping_rules.get_stopping_rule(db_session, FailureCategory.INSUFFICIENT_FUNDS)

    assert rule.max_retries == settings.default_max_retry_attempts
    assert rule.max_days_open == settings.default_max_days_open
    assert rule.opt_out_respected is True
    assert rule.retry_intervals_hours == [2, 24, 72][: settings.default_max_retry_attempts]


def test_stopping_rules_db_overrides_settings(db_session):
    # Insert custom row that differs from Settings defaults (default is 3 retries, 7 days)
    db_session.query(StoppingRuleConfig).filter_by(
        failure_category=FailureCategory.CARD_ISSUE
    ).delete()
    custom_rule = StoppingRuleConfig(
        failure_category=FailureCategory.CARD_ISSUE,
        max_retries=9,
        max_days_open=45,
        retry_intervals_hours=[1, 4, 12],
        opt_out_respected=False,
    )
    db_session.add(custom_rule)
    db_session.commit()

    rule = stopping_rules.get_stopping_rule(db_session, FailureCategory.CARD_ISSUE)
    assert rule.max_retries == 9
    assert rule.max_days_open == 45
    assert rule.retry_intervals_hours == [1, 4, 12]
    assert rule.opt_out_respected is False


def test_migration_seed_defaults_cover_all_failure_categories():
    seeded_categories = {r["failure_category"] for r in DEFAULT_STOPPING_RULES}
    all_enum_categories = {c.value for c in FailureCategory}
    assert seeded_categories == all_enum_categories


def test_seeded_rules_applied_and_evaluated(db_session):
    # Seed all default rules into session
    db_session.query(StoppingRuleConfig).delete()
    for item in DEFAULT_STOPPING_RULES:
        db_session.add(
            StoppingRuleConfig(
                failure_category=FailureCategory(item["failure_category"]),
                max_retries=item["max_retries"],
                retry_intervals_hours=item["retry_intervals_hours"],
                max_days_open=item["max_days_open"],
                opt_out_respected=item["opt_out_respected"],
            )
        )
    db_session.commit()

    tech_rule = stopping_rules.get_stopping_rule(db_session, FailureCategory.RETRIABLE_TECHNICAL)
    assert tech_rule.max_retries == 4
    assert tech_rule.max_days_open == 5
    assert tech_rule.retry_intervals_hours == [2, 6, 24, 72]

    # Test evaluate with case below limit
    case_active = RecoveryCase(
        subscription_id="sub_test_stopping_1",
        amount=50000,
        retry_count=2,
        created_at=datetime.now(timezone.utc),
    )
    triggered, reason = stopping_rules.evaluate(case_active, tech_rule)
    assert triggered is False
    assert reason is None

    # Test evaluate with case reaching max_retries
    case_max_retries = RecoveryCase(
        subscription_id="sub_test_stopping_2",
        amount=50000,
        retry_count=4,
        created_at=datetime.now(timezone.utc),
    )
    triggered, reason = stopping_rules.evaluate(case_max_retries, tech_rule)
    assert triggered is True
    assert "Max retries reached" in reason

    # Test evaluate with case exceeding max_days_open
    case_stale = RecoveryCase(
        subscription_id="sub_test_stopping_3",
        amount=50000,
        retry_count=1,
        created_at=datetime.now(timezone.utc) - timedelta(days=6),
    )
    triggered, reason = stopping_rules.evaluate(case_stale, tech_rule)
    assert triggered is True
    assert "exceeding max_days_open" in reason

    # Test evaluate with opt_out
    case_opt_out = RecoveryCase(
        subscription_id="sub_test_stopping_4",
        amount=50000,
        retry_count=0,
        opted_out=True,
        created_at=datetime.now(timezone.utc),
    )
    triggered, reason = stopping_rules.evaluate(case_opt_out, tech_rule)
    assert triggered is True
    assert "opted out" in reason
