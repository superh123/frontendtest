"""Snapshot-bound supplier negotiations and atomic contract publication."""

import json
from uuid import uuid4

from backend import __version__
from backend.forks import snapshot_hash
from backend.ledger import LedgerError
from backend.supply_policy import supplier_facts, validate_terms


class SupplyStore:
    @staticmethod
    def init_supply_tables(connection):
        connection.execute("""CREATE TABLE IF NOT EXISTS procurement_runs (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL, buyer_id TEXT NOT NULL, request_id TEXT NOT NULL,
            request TEXT NOT NULL, snapshot TEXT NOT NULL, report TEXT NOT NULL,
            UNIQUE(source_id, buyer_id, request_id))""")
        connection.execute("""CREATE TABLE IF NOT EXISTS procurement_settlements (
            run_id TEXT PRIMARY KEY, transaction_id TEXT NOT NULL, result TEXT NOT NULL)""")

    def find_procurement(self, simulation_id, buyer_id, request):
        with self.connection() as connection:
            row = connection.execute("SELECT request, report FROM procurement_runs WHERE source_id=? AND buyer_id=? AND request_id=?",
                                     (simulation_id, buyer_id, request["request_id"])).fetchone()
            if row is None:
                return None
            if json.loads(row[0]) != request:
                raise LedgerError("Procurement request ID already used with different contents")
            report = json.loads(row[1])
            if report["status"] == "running":
                raise LedgerError(f"Procurement is already running: {report['run_id']}")
            return report

    def claim_procurement(self, simulation_id, buyer_id, request, supplier_ids, models):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT id FROM procurement_runs WHERE source_id=? AND buyer_id=? AND request_id=?",
                                     (simulation_id, buyer_id, request["request_id"])).fetchone()
            if row:
                raise LedgerError(f"Procurement already exists; retrieve or retry it: {row[0]}")
            source = self.load(connection, simulation_id)
            for supplier_id in supplier_ids:
                supplier_facts(source, buyer_id, supplier_id, request["quantity"])
            if source.customer(buyer_id)["status"] != "active":
                raise LedgerError("Buyer is closed")
            report = {"run_id": f"supply_{uuid4().hex}", "simulation_id": simulation_id, "buyer_id": buyer_id,
                "supplier_ids": supplier_ids, "engine_version": __version__, "source_tick": source.state["tick"],
                "snapshot_sha256": snapshot_hash(source.state), "request": request, "status": "running",
                "providers": {actor: model.provider for actor, model in models.items()},
                "models": {actor: model.model for actor, model in models.items()},
                "offers": [], "trace": [], "negotiation": None, "selected_offer": None, "buyer_rationale": None,
                "contract_id": None, "settlement": None, "error": None}
            connection.execute("INSERT INTO procurement_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                (report["run_id"], simulation_id, buyer_id, request["request_id"], json.dumps(request), json.dumps(source.state), json.dumps(report)))
            return report, source

    def save_procurement(self, report):
        with self.connection() as connection:
            connection.execute("UPDATE procurement_runs SET report=? WHERE id=?", (json.dumps(report), report["run_id"]))

    def get_procurement(self, run_id):
        with self.connection() as connection:
            row = connection.execute("SELECT report FROM procurement_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            return json.loads(row[0])

    def list_procurement(self, simulation_id, buyer_id):
        with self.connection() as connection:
            self.load(connection, simulation_id).customer(buyer_id)
            rows = connection.execute("SELECT report FROM procurement_runs WHERE source_id=? AND buyer_id=? ORDER BY rowid",
                                      (simulation_id, buyer_id)).fetchall()
            return [json.loads(row[0]) for row in rows]

    def procurement_error(self, run_id, error):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT report FROM procurement_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            report = json.loads(row[0])
            if report["status"] == "ready":
                report["error"] = error
                connection.execute("UPDATE procurement_runs SET report=? WHERE id=?", (json.dumps(report), run_id))
            return report

    def settle_procurement(self, run_id, transaction_id):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute("SELECT transaction_id, result FROM procurement_settlements WHERE run_id=?", (run_id,)).fetchone()
            if previous:
                if previous[0] != transaction_id:
                    raise LedgerError("Procurement already settled with another transaction ID")
                return json.loads(previous[1])
            row = connection.execute("SELECT report FROM procurement_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            report = json.loads(row[0])
            if report["status"] != "ready" or report["selected_offer"] is None:
                raise LedgerError("Only a buyer-selected offer can settle")
            source = self.load(connection, report["simulation_id"])
            if snapshot_hash(source.state) != report["snapshot_sha256"]:
                raise LedgerError("Source world changed; request new supplier offers")
            if transaction_id in source.ledger._transactions:
                raise LedgerError("Settlement transaction ID is already used")
            offer = report["selected_offer"]
            if offer not in report["offers"] or offer["total_cents"] > report["request"]["max_total_cents"]:
                raise LedgerError("Selected offer exceeds authorized terms")
            facts = supplier_facts(source, report["buyer_id"], offer["supplier_id"], offer["quantity"])
            validate_terms(facts, offer)
            contract_id = f"contract_{run_id}"
            created = source.create_contract(transaction_id, contract_id, report["buyer_id"], offer["supplier_id"],
                offer["quantity"], offer["unit_price_cents"], offer["down_payment_bps"], offer["due_in_ticks"])
            result = {"run_id": run_id, "simulation_id": report["simulation_id"], **created, "audit": source.audit()}
            report.update(status="contracted", contract_id=contract_id, settlement=result)
            connection.execute("UPDATE worlds SET state=? WHERE id=?", (json.dumps(source.state), report["simulation_id"]))
            connection.execute("UPDATE procurement_runs SET report=? WHERE id=?", (json.dumps(report), run_id))
            connection.execute("INSERT INTO procurement_settlements VALUES (?, ?, ?)", (run_id, transaction_id, json.dumps(result)))
            return result
