"""backend v4 artifact contract columns

Revision ID: 002
Revises: 001
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return any(c["name"] == column for c in sa.inspect(bind).get_columns(table))


def _add(table: str, column: sa.Column) -> None:
    if table in _tables() and not _has_column(table, column.name):
        op.add_column(table, column)


def _idx(name: str, table: str, columns: list[str]) -> None:
    bind = op.get_bind()
    existing = {idx["name"] for idx in sa.inspect(bind).get_indexes(table)} if table in _tables() else set()
    if table in _tables() and name not in existing:
        op.create_index(name, table, columns)


def upgrade() -> None:
    for col in (
        sa.Column("has_rubika", sa.Boolean(), nullable=True),
        sa.Column("has_ewano", sa.Boolean(), nullable=True),
        sa.Column("has_hamrahman", sa.Boolean(), nullable=True),
        sa.Column("has_volte", sa.Boolean(), nullable=True),
        sa.Column("ecosystem_product_count", sa.Integer(), nullable=True),
        sa.Column("ecosystem_engagement_level", sa.String(length=32), nullable=True),
        sa.Column("ecosystem_segment", sa.String(length=64), nullable=True),
        sa.Column("ecosystem_risk_gap", sa.Boolean(), nullable=True),
        sa.Column("ecosystem_retention_strategy", sa.String(length=128), nullable=True),
    ):
        _add("subscribers", col)
    _idx("ix_subscribers_ecosystem_segment", "subscribers", ["ecosystem_segment"])
    _idx("ix_subscribers_ecosystem_retention_strategy", "subscribers", ["ecosystem_retention_strategy"])

    for col in (
        sa.Column("champion_family", sa.String(length=64), nullable=True),
        sa.Column("calibration_method", sa.String(length=32), nullable=True),
        sa.Column("model_schema_version", sa.String(length=64), nullable=True),
        sa.Column("feature_contract_version", sa.String(length=64), nullable=True),
    ):
        _add("churn_predictions", col)

    for col in (
        sa.Column("rule_top_driver", sa.String(length=256), nullable=True),
        sa.Column("shap_top_driver", sa.String(length=256), nullable=True),
        sa.Column("final_top_driver", sa.String(length=256), nullable=True),
        sa.Column("final_top_driver_source", sa.String(length=32), nullable=True),
        sa.Column("rule_priority", sa.String(length=8), nullable=True),
        sa.Column("secondary_channel", sa.String(length=32), nullable=True),
        sa.Column("digital_only_flag", sa.Boolean(), nullable=True),
        sa.Column("escalation_required", sa.Boolean(), nullable=True),
        sa.Column("action_assigned", sa.Boolean(), nullable=True),
        sa.Column("is_fallback_rule", sa.Boolean(), nullable=True),
        sa.Column("offer_budget_numeric_tier", sa.Integer(), nullable=True),
        sa.Column("offer_budget_cap_type", sa.String(length=64), nullable=True),
        sa.Column("campaign_urgency_days", sa.Float(), nullable=True),
        sa.Column("crm_queue", sa.String(length=64), nullable=True),
        sa.Column("campaign_channel_group", sa.String(length=64), nullable=True),
        sa.Column("retention_cost_estimate", sa.String(length=64), nullable=True),
        sa.Column("contact_channel", sa.String(length=128), nullable=True),
        sa.Column("offer_budget", sa.String(length=256), nullable=True),
        sa.Column("has_rubika", sa.Boolean(), nullable=True),
        sa.Column("has_ewano", sa.Boolean(), nullable=True),
        sa.Column("has_hamrahman", sa.Boolean(), nullable=True),
        sa.Column("has_volte", sa.Boolean(), nullable=True),
        sa.Column("ecosystem_product_count", sa.Integer(), nullable=True),
        sa.Column("ecosystem_engagement_level", sa.String(length=32), nullable=True),
        sa.Column("ecosystem_segment", sa.String(length=64), nullable=True),
        sa.Column("ecosystem_risk_gap", sa.Boolean(), nullable=True),
        sa.Column("ecosystem_retention_strategy", sa.String(length=128), nullable=True),
        sa.Column("shap_risk_up_drivers", sa.Text(), nullable=True),
        sa.Column("shap_risk_down_drivers", sa.Text(), nullable=True),
        sa.Column("recommendation_schema_version", sa.String(length=64), nullable=True),
        sa.Column("model_schema_version", sa.String(length=64), nullable=True),
        sa.Column("feature_contract_version", sa.String(length=64), nullable=True),
    ):
        _add("recommendations", col)
    _idx("ix_recommendations_crm_queue", "recommendations", ["crm_queue"])
    _idx("ix_recommendations_ecosystem_segment", "recommendations", ["ecosystem_segment"])
    _idx("ix_recommendations_campaign_channel_group", "recommendations", ["campaign_channel_group"])
    _idx("ix_recommendations_digital_only_flag", "recommendations", ["digital_only_flag"])
    _idx("ix_recommendations_escalation_required", "recommendations", ["escalation_required"])

    for col in (
        sa.Column("top_business_label", sa.String(length=256), nullable=True),
        sa.Column("shap_top_driver", sa.String(length=256), nullable=True),
        sa.Column("shap_risk_up_drivers", sa.Text(), nullable=True),
        sa.Column("shap_risk_down_drivers", sa.Text(), nullable=True),
        sa.Column("shap_schema_version", sa.String(length=64), nullable=True),
        sa.Column("feature_contract_version", sa.String(length=64), nullable=True),
    ):
        _add("shap_explanations", col)

    for col in (
        sa.Column("schema_version", sa.String(length=64), nullable=True),
        sa.Column("bundle_schema_version", sa.String(length=64), nullable=True),
        sa.Column("feature_contract_version", sa.String(length=64), nullable=True),
        sa.Column("recommendation_schema_version", sa.String(length=64), nullable=True),
        sa.Column("shap_schema_version", sa.String(length=64), nullable=True),
        sa.Column("compatibility_status", sa.String(length=32), nullable=True),
    ):
        _add("model_versions", col)


def downgrade() -> None:
    # Non-destructive by design. Leave v4 metadata in place.
    pass
