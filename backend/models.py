from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class WorldConfig(Request):
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    households: int = Field(default=40, ge=1, le=2000)
    businesses: int = Field(default=8, ge=1, le=150)
    banks: int = Field(default=5, ge=1, le=10)
    scenario: Literal["standard", "credit_crunch"] = "standard"


class StepRequest(Request):
    ticks: int = Field(default=1, ge=1, le=100)


class PlayRequest(Request):
    interval_ms: int = Field(default=1000, ge=250, le=10000)


class PlaybackStatus(BaseModel):
    simulation_id: str
    status: Literal["paused", "running"]
    interval_ms: int
    error: str | None = None


class ResetRequest(Request):
    request_id: str = Field(min_length=1, max_length=128)


class ResetResult(BaseModel):
    source_simulation_id: str
    simulation_id: str


class FinancialRequest(Request):
    transaction_id: str = Field(min_length=1, max_length=128)

    @field_validator("transaction_id")
    @classmethod
    def external_transaction_id(cls, value):
        if value.startswith(("genesis:", "tick:", "fork:", "credit:", "procurement:")):
            raise ValueError("Backend transaction prefixes are reserved")
        return value


class PaymentRequest(FinancialRequest):
    payer_id: str = Field(min_length=1, max_length=128)
    receiver_id: str = Field(min_length=1, max_length=128)
    amount_cents: int = Field(gt=0, le=10**12)


class LoanRequest(FinancialRequest):
    borrower_id: str = Field(min_length=1, max_length=128)
    amount_cents: int = Field(gt=0, le=10**12)


class ShockRequest(FinancialRequest):
    bank_id: str = Field(min_length=1, max_length=128)
    asset_category: Literal["risky_assets"] = "risky_assets"
    loss_bps: int = Field(default=4000, ge=1, le=10000)


class InterventionRequest(FinancialRequest):
    kind: Literal["bank_lending", "household_cash"]
    amount_cents: int = Field(gt=0, le=10**12)
    bank_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_target(self):
        if (self.kind == "bank_lending") != (self.bank_id is not None):
            raise ValueError("Only bank lending requires a bank_id")
        return self


class ForkRequest(Request):
    request_id: str = Field(min_length=1, max_length=128)
    bank_id: str = Field(default="bank_1", min_length=1, max_length=128)
    budget_cents: int = Field(default=1_000_000, gt=0, le=10**12)
    ticks: int = Field(default=12, ge=1, le=100)


class ForkLineage(BaseModel):
    fork_id: str
    parent_simulation_id: str
    source_tick: int
    snapshot_sha256: str
    strategy: Literal["no_intervention", "bank_lending", "household_cash"]


class BalanceSheet(BaseModel):
    assets: dict[str, int]
    liabilities: dict[str, int]
    equity: dict[str, int]
    assets_cents: int
    liabilities_cents: int
    equity_cents: int
    balanced: bool


class Entity(BaseModel):
    id: str
    name: str
    kind: Literal["household", "business", "bank", "government", "central_bank"]
    status: str
    bank_id: str | None = None
    employer_id: str | None = None
    employees: list[str] | None = None
    price_cents: int | None = None
    wage_cents: int | None = None
    consumption_budget_cents: int | None = None
    loan_due_tick: int | None = None
    missed_debt_ticks: int = 0
    missed_payroll_ticks: int = 0
    interbank_default: bool = False
    capital_ratio: float | None = None
    liquidity_ratio: float | None = None
    lending_available: bool | None = None
    materials_units: int | None = None
    balance_sheet: BalanceSheet


class Metrics(BaseModel):
    simulation_tick: int
    households: int
    businesses: int
    banks: int
    employed_households: int
    employment_rate: float
    household_cash_cents: int
    business_cash_cents: int
    total_deposits_cents: int
    total_bank_reserves_cents: int
    total_loans_cents: int
    business_defaults: int
    stressed_banks: int
    insolvent_banks: int = 0
    public_intervention_cost_cents: int
    public_support_disbursed_cents: int = 0
    fiscal_transfer_cost_cents: int = 0
    public_loan_outstanding_cents: int = 0
    trade_credit_outstanding_cents: int = 0
    supplier_contract_defaults: int = 0


class World(BaseModel):
    simulation_id: str
    seed: int
    simulation_tick: int
    status: Literal["paused", "running"]
    config: WorldConfig
    metrics: Metrics
    entities: list[Entity]
    latest_event_sequence: int
    lineage: ForkLineage | None = None


class Event(BaseModel):
    sequence: int
    simulation_id: str
    simulation_tick: int
    event_type: str
    agent_id: str | None
    counterparty_id: str | None
    amount_cents: int | None
    transaction_id: str | None
    details: dict[str, Any]


class EventPage(BaseModel):
    events: list[Event]
    next_after: int
    has_more: bool


class JournalLine(BaseModel):
    account_id: str
    signed_cents: int


class Transaction(BaseModel):
    transaction_id: str
    lines: list[JournalLine]
    metadata: dict[str, Any]


class TransactionPage(BaseModel):
    transactions: list[Transaction]
    next_offset: int
    has_more: bool


class Audit(BaseModel):
    balanced: bool
    journal_matches_balances: bool
    bank_counterparties_match: bool
    interbank_counterparties_match: bool = True
    public_counterparties_match: bool = True
    supplier_counterparties_match: bool = True
    transaction_count: int
    account_count: int


class Exposure(BaseModel):
    kind: Literal["interbank", "customer_loan", "public_loan", "trade_credit"]
    borrower_id: str
    lender_id: str
    amount_cents: int
    due_tick: int | None


class Network(BaseModel):
    simulation_id: str
    simulation_tick: int
    exposures: list[Exposure]


class ForkBranch(BaseModel):
    strategy: Literal["no_intervention", "bank_lending", "household_cash"]
    simulation_id: str
    metrics: Metrics
    timeline: list[Metrics]
    audit: Audit
    delta_vs_no_intervention: dict[str, int | float]


class ForkSummary(BaseModel):
    fork_id: str
    source_simulation_id: str
    source_tick: int
    source_event_sequence: int
    end_tick: int
    snapshot_sha256: str
    recommended_strategy: str


class ForkComparison(ForkSummary):
    engine_version: str
    seed: int
    request: ForkRequest
    initial_metrics: Metrics
    branches: list[ForkBranch]
    tied_strategies: list[str]
    recommendation_basis: str
    cost_definition: str


class AgentRunRequest(Request):
    request_id: str = Field(min_length=1, max_length=128)
    mode: Literal["live", "demo"] = "live"
    budget_cap_cents: int = Field(default=1_000_000, ge=1, le=10**12)
    ticks: int = Field(default=12, ge=1, le=100)
    max_experiments: int = Field(default=2, ge=1, le=3)


class InspectArguments(Request):
    pass


class CompareArguments(Request):
    bank_id: str = Field(min_length=1, max_length=128)
    budget_cents: int = Field(ge=1, le=10**12)


class RecommendArguments(Request):
    fork_id: str = Field(min_length=1, max_length=128)
    strategy: Literal["no_intervention", "bank_lending", "household_cash"]
    rationale: str = Field(min_length=1, max_length=2000)


class AgentTrace(BaseModel):
    sequence: int
    tool: str
    arguments: dict[str, Any]
    status: Literal["accepted", "rejected"]
    result: dict[str, Any]


class AgentRecommendation(BaseModel):
    fork_id: str
    strategy: Literal["no_intervention", "bank_lending", "household_cash"]
    bank_id: str | None
    amount_cents: int
    rationale: str
    metrics: Metrics
    delta_vs_no_intervention: dict[str, int | float]


class AgentReport(BaseModel):
    run_id: str
    simulation_id: str
    engine_version: str
    source_tick: int
    snapshot_sha256: str
    request: AgentRunRequest
    status: Literal["running", "completed", "failed"]
    provider: str
    model: str
    trace: list[AgentTrace]
    comparison_ids: list[str]
    recommendation: AgentRecommendation | None = None
    error: str | None = None


class ApplyAgentRequest(FinancialRequest):
    pass


class AgentApplication(BaseModel):
    run_id: str
    simulation_id: str
    strategy: str
    transaction_id: str
    receipt: Transaction
    audit: Audit


class CreditRunRequest(Request):
    request_id: str = Field(min_length=1, max_length=128)
    mode: Literal["live", "demo"] = "live"
    max_amount_cents: int = Field(default=500_000, ge=1, le=500_000)
    auto_settle: bool = False


class CreditProposal(Request):
    amount_cents: int = Field(gt=0, le=500_000)
    rationale: str = Field(min_length=1, max_length=2000)


class ContinueBusiness(Request):
    rationale: str = Field(min_length=1, max_length=2000)


class AssessCreditArguments(Request):
    amount_cents: int = Field(gt=0, le=500_000)


class BankDecision(Request):
    approved: bool
    amount_cents: int = Field(ge=0, le=500_000)
    rationale: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def principal_matches_decision(self):
        if self.approved != (self.amount_cents > 0):
            raise ValueError("Approval requires positive principal; decline requires zero principal")
        return self


class CreditTrace(AgentTrace):
    actor_id: str
    role: Literal["business", "bank"]


class CreditDecision(BaseModel):
    approved: bool
    amount_cents: int
    rationale: str
    assessment: dict[str, Any] | None


class CreditReport(BaseModel):
    run_id: str
    simulation_id: str
    business_id: str
    bank_id: str
    engine_version: str
    source_tick: int
    snapshot_sha256: str
    request: CreditRunRequest
    status: Literal["running", "approved", "declined", "not_requested", "settled", "failed"]
    providers: dict[str, str]
    models: dict[str, str]
    facts: dict[str, Any]
    trace: list[CreditTrace]
    proposal: CreditProposal | None = None
    business_rationale: str | None = None
    business_accepted: bool | None = None
    decision: CreditDecision | None = None
    settlement: dict[str, Any] | None = None
    error: str | None = None


class CreditSettlement(BaseModel):
    run_id: str
    simulation_id: str
    business_id: str
    bank_id: str
    transaction_id: str
    amount_cents: int
    due_tick: int | None
    receipt: Transaction
    audit: Audit


class ProcurementRequest(Request):
    request_id: str = Field(min_length=1, max_length=128)
    mode: Literal["live", "demo"] = "live"
    supplier_ids: list[str] | None = Field(default=None, min_length=2, max_length=2)
    quantity: int = Field(default=20, ge=1, le=1000)
    max_total_cents: int = Field(default=100_000, ge=1, le=10**9)
    auto_settle: bool = False

    @field_validator("supplier_ids")
    @classmethod
    def different_suppliers(cls, value):
        if value is not None and (len(set(value)) != 2 or any(not item or len(item) > 128 for item in value)):
            raise ValueError("Choose two distinct supplier IDs")
        return value


class QuoteTerms(Request):
    unit_price_cents: int = Field(ge=1, le=100_000)
    down_payment_bps: int = Field(ge=1000, le=10000)
    due_in_ticks: int = Field(ge=1, le=30)
    rationale: str = Field(min_length=1, max_length=2000)


class CounterOffer(QuoteTerms):
    supplier_id: str = Field(min_length=1, max_length=128)


class SelectOffer(Request):
    offer_id: str = Field(min_length=1, max_length=256)
    rationale: str = Field(min_length=1, max_length=2000)


class SupplierOffer(QuoteTerms):
    offer_id: str
    supplier_id: str
    quantity: int
    total_cents: int
    down_payment_cents: int


class SupplyTrace(AgentTrace):
    actor_id: str
    role: Literal["buyer", "supplier"]


class ProcurementReport(BaseModel):
    run_id: str
    simulation_id: str
    buyer_id: str
    supplier_ids: list[str]
    engine_version: str
    source_tick: int
    snapshot_sha256: str
    request: ProcurementRequest
    status: Literal["running", "ready", "declined", "contracted", "failed"]
    providers: dict[str, str]
    models: dict[str, str]
    offers: list[SupplierOffer]
    trace: list[SupplyTrace]
    negotiation: dict[str, Any] | None = None
    selected_offer: SupplierOffer | None = None
    buyer_rationale: str | None = None
    contract_id: str | None = None
    settlement: dict[str, Any] | None = None
    error: str | None = None


class SupplierContract(BaseModel):
    contract_id: str
    buyer_id: str
    supplier_id: str
    quantity: int
    unit_price_cents: int
    total_cents: int
    down_payment_cents: int
    paid_cents: int
    outstanding_cents: int
    written_off_cents: int
    created_tick: int
    due_tick: int
    missed_payment_ticks: int
    status: Literal["open", "overdue", "paid", "defaulted"]
    creation_transaction_id: str


class ProcurementSettlement(BaseModel):
    run_id: str
    simulation_id: str
    contract: SupplierContract
    receipt: Transaction
    audit: Audit
