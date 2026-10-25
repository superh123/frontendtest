"""Persistent credit negotiations and atomic, exactly-once loan settlement."""

import json
from uuid import uuid4

from backend import __version__
from backend.credit_policy import assess_credit, business_facts
from backend.forks import snapshot_hash
from backend.ledger import LedgerError


class CreditStore:
    @staticmethod
    def init_credit_tables(connection):
        connection.execute("""CREATE TABLE IF NOT EXISTS credit_runs (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL, business_id TEXT NOT NULL,
            request_id TEXT NOT NULL, request TEXT NOT NULL, snapshot TEXT NOT NULL, report TEXT NOT NULL,
            UNIQUE(source_id, business_id, request_id))""")
        connection.execute("""CREATE TABLE IF NOT EXISTS credit_settlements (
            run_id TEXT PRIMARY KEY, transaction_id TEXT NOT NULL, result TEXT NOT NULL)""")

    def find_credit(self, simulation_id, business_id, request):
        with self.connection() as connection:
            row = connection.execute("SELECT request, report FROM credit_runs WHERE source_id=? AND business_id=? AND request_id=?",
                                     (simulation_id, business_id, request["request_id"])).fetchone()
            if row is None:
                return None
            if json.loads(row[0]) != request:
                raise LedgerError("Credit request ID already used with different contents")
            report = json.loads(row[1])
            if report["status"] == "running":
                raise LedgerError(f"Credit workflow is already running: {report['run_id']}")
            return report

    def claim_credit(self, simulation_id, business_id, request, models):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute("SELECT id FROM credit_runs WHERE source_id=? AND business_id=? AND request_id=?",
                                        (simulation_id, business_id, request["request_id"])).fetchone()
            if exists:
                raise LedgerError(f"Credit workflow already exists; retrieve or retry it: {exists[0]}")
            source = self.load(connection, simulation_id)
            facts = business_facts(source, business_id)
            report = {"run_id": f"credit_{uuid4().hex}", "simulation_id": simulation_id,
                      "business_id": business_id, "bank_id": facts["bank_id"], "engine_version": __version__,
                      "source_tick": source.state["tick"], "snapshot_sha256": snapshot_hash(source.state),
                      "request": request, "status": "running", "facts": facts,
                      "providers": {role: model.provider for role, model in models.items()},
                      "models": {role: model.model for role, model in models.items()},
                      "trace": [], "proposal": None, "business_rationale": None, "business_accepted": None,
                      "decision": None, "settlement": None, "error": None}
            connection.execute("INSERT INTO credit_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (report["run_id"], simulation_id, business_id, request["request_id"],
                                json.dumps(request), json.dumps(source.state), json.dumps(report)))
            return report, source

    def save_credit(self, report):
        with self.connection() as connection:
            connection.execute("UPDATE credit_runs SET report=? WHERE id=?", (json.dumps(report), report["run_id"]))

    def get_credit(self, run_id):
        with self.connection() as connection:
            row = connection.execute("SELECT report FROM credit_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            return json.loads(row[0])

    def list_credit(self, simulation_id, business_id):
        with self.connection() as connection:
            business_facts(self.load(connection, simulation_id), business_id)
            rows = connection.execute("SELECT report FROM credit_runs WHERE source_id=? AND business_id=? ORDER BY rowid",
                                      (simulation_id, business_id)).fetchall()
            return [json.loads(row[0]) for row in rows]

    def credit_settlement_error(self, run_id, error):
        # A simultaneous manual settlement must never be overwritten by an
        # older in-memory approval while auto-settlement records an error.
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT report FROM credit_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            report = json.loads(row[0])
            if report["status"] == "approved":
                report["error"] = error
                connection.execute("UPDATE credit_runs SET report=? WHERE id=?", (json.dumps(report), run_id))
            return report

    def settle_credit(self, run_id, transaction_id):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute("SELECT transaction_id, result FROM credit_settlements WHERE run_id=?",
                                          (run_id,)).fetchone()
            if previous:
                if previous[0] != transaction_id:
                    raise LedgerError("Credit run has already settled with another transaction ID")
                return json.loads(previous[1])
            row = connection.execute("SELECT report FROM credit_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            report = json.loads(row[0])
            if report["status"] != "approved" or not report["decision"]["approved"] or not report["business_accepted"]:
                raise LedgerError("Only an approved credit workflow can settle")
            source = self.load(connection, report["simulation_id"])
            if snapshot_hash(source.state) != report["snapshot_sha256"]:
                raise LedgerError("Source world changed; request a new credit review")
            if transaction_id in source.ledger._transactions:
                raise LedgerError("Settlement transaction ID is already used")
            amount = report["decision"]["amount_cents"]
            if amount > report["request"]["max_amount_cents"] or amount > report["proposal"]["amount_cents"]:
                raise LedgerError("Approved principal exceeds the authorized proposal")
            assessment = assess_credit(source, report["business_id"], amount)
            if not assessment["eligible"]:
                raise LedgerError("Credit no longer passes underwriting constraints")
            receipt = source.loan(transaction_id, report["business_id"], amount)
            source.emit("agent_credit_settled", report["business_id"], report["bank_id"], amount, transaction_id,
                        {"run_id": run_id, "purpose": "payroll", "due_tick": assessment["due_tick"]})
            result = {"run_id": run_id, "simulation_id": report["simulation_id"],
                      "business_id": report["business_id"], "bank_id": report["bank_id"],
                      "transaction_id": transaction_id, "amount_cents": amount,
                      "due_tick": source.state["entities"][report["business_id"]].get("loan_due_tick"),
                      "receipt": receipt, "audit": source.audit()}
            report["settlement"] = result
            report["status"] = "settled"
            connection.execute("UPDATE worlds SET state=? WHERE id=?", (json.dumps(source.state), report["simulation_id"]))
            connection.execute("UPDATE credit_runs SET report=? WHERE id=?", (json.dumps(report), run_id))
            connection.execute("INSERT INTO credit_settlements VALUES (?, ?, ?)", (run_id, transaction_id, json.dumps(result)))
            return result
