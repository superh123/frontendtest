"""Atomic SQLite checkpoints, including ledger, event history, and tick state."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from backend.engine import Economy
from backend.forks import build_comparison, snapshot_hash
from backend import __version__
from backend.ledger import LedgerError
from backend.credit_store import CreditStore
from backend.supply_store import SupplyStore
from backend.playback import PlaybackStore


class Store(CreditStore, SupplyStore, PlaybackStore):
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS worlds (id TEXT PRIMARY KEY, state TEXT NOT NULL)")
            connection.execute("""CREATE TABLE IF NOT EXISTS forks (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL, request_id TEXT NOT NULL,
                request TEXT NOT NULL, snapshot TEXT NOT NULL, result TEXT NOT NULL,
                UNIQUE(source_id, request_id))""")
            connection.execute("""CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL, request_id TEXT NOT NULL,
                request TEXT NOT NULL, snapshot TEXT NOT NULL, report TEXT NOT NULL,
                UNIQUE(source_id, request_id))""")
            connection.execute("""CREATE TABLE IF NOT EXISTS agent_applications (
                run_id TEXT PRIMARY KEY, transaction_id TEXT NOT NULL, result TEXT NOT NULL)""")
            self.init_credit_tables(connection)
            self.init_supply_tables(connection)
            self.init_playback_tables(connection)

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, world):
        with self.connection() as connection:
            connection.execute("INSERT INTO worlds VALUES (?, ?)",
                               (world.state["simulation_id"], json.dumps(world.state)))

    @staticmethod
    def load(connection, simulation_id):
        row = connection.execute("SELECT state FROM worlds WHERE id = ?", (simulation_id,)).fetchone()
        if row is None:
            raise KeyError(simulation_id)
        return Economy(json.loads(row[0]))

    def get(self, simulation_id):
        with self.connection() as connection:
            return self.load(connection, simulation_id)

    def mutate(self, simulation_id, operation):
        # Lock before reading, so concurrent requests cannot lose an update.
        # Any exception rolls back the complete operation.
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            world = self.load(connection, simulation_id)
            result = operation(world)
            world.audit()
            connection.execute("UPDATE worlds SET state = ? WHERE id = ?",
                               (json.dumps(world.state), simulation_id))
            return result

    @staticmethod
    def existing_fork(connection, simulation_id, request):
        row = connection.execute("SELECT request, result FROM forks WHERE source_id = ? AND request_id = ?",
                                 (simulation_id, request["request_id"])).fetchone()
        if row is not None:
            if json.loads(row[0]) != request:
                raise LedgerError("Fork request ID already used with different contents")
            return json.loads(row[1])

    def fork(self, simulation_id, request, source=None):
        # Copy one committed snapshot under a short read transaction. The source
        # may continue afterward; all three branches still use this exact copy.
        with self.connection() as connection:
            connection.execute("BEGIN")
            previous = self.existing_fork(connection, simulation_id, request)
            if previous is not None:
                return previous
            source = self.load(connection, simulation_id) if source is None else Economy(source.state)
            if source.state["simulation_id"] != simulation_id:
                raise LedgerError("Fork snapshot does not belong to the source world")
        fork_id = f"fork_{uuid4().hex}"
        result, branches = build_comparison(source, fork_id, request)
        # Publish all worlds and the immutable report together, or none of them.
        # Recheck retries after computation so concurrent duplicate requests
        # cannot leave orphan worlds or publish conflicting experiments.
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = self.existing_fork(connection, simulation_id, request)
            if previous is not None:
                return previous
            for branch in branches:
                connection.execute("INSERT INTO worlds VALUES (?, ?)",
                                   (branch.state["simulation_id"], json.dumps(branch.state)))
            connection.execute("INSERT INTO forks VALUES (?, ?, ?, ?, ?, ?)",
                               (fork_id, simulation_id, request["request_id"], json.dumps(request),
                                json.dumps(source.state), json.dumps(result)))
        return result

    def get_fork(self, fork_id):
        with self.connection() as connection:
            row = connection.execute("SELECT result FROM forks WHERE id = ?", (fork_id,)).fetchone()
            if row is None:
                raise KeyError(fork_id)
            return json.loads(row[0])

    def list_forks(self, simulation_id):
        with self.connection() as connection:
            self.load(connection, simulation_id)
            rows = connection.execute("SELECT result FROM forks WHERE source_id = ? ORDER BY rowid",
                                      (simulation_id,)).fetchall()
            keys = ("fork_id", "source_simulation_id", "source_tick", "source_event_sequence", "end_tick",
                    "snapshot_sha256", "recommended_strategy")
            return [{key: result[key] for key in keys} for result in (json.loads(row[0]) for row in rows)]

    def find_agent(self, simulation_id, request):
        with self.connection() as connection:
            row = connection.execute("SELECT request, report FROM agent_runs WHERE source_id = ? AND request_id = ?",
                                     (simulation_id, request["request_id"])).fetchone()
            if row is None:
                return None
            if json.loads(row[0]) != request:
                raise LedgerError("Agent request ID already used with different contents")
            report = json.loads(row[1])
            if report["status"] == "running":
                raise LedgerError(f"Agent run is already running: {report['run_id']}")
            return report

    def claim_agent(self, simulation_id, request, model):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT id FROM agent_runs WHERE source_id = ? AND request_id = ?",
                                     (simulation_id, request["request_id"])).fetchone()
            if row:
                raise LedgerError(f"Agent run already exists; retrieve or retry it: {row[0]}")
            source = self.load(connection, simulation_id)
            report = {"run_id": f"agent_{uuid4().hex}", "simulation_id": simulation_id,
                      "engine_version": __version__, "source_tick": source.state["tick"],
                      "snapshot_sha256": snapshot_hash(source.state), "request": request,
                      "status": "running", "provider": model.provider, "model": model.model,
                      "trace": [], "comparison_ids": [], "recommendation": None, "error": None}
            connection.execute("INSERT INTO agent_runs VALUES (?, ?, ?, ?, ?, ?)",
                               (report["run_id"], simulation_id, request["request_id"], json.dumps(request),
                                json.dumps(source.state), json.dumps(report)))
            return report, source

    def save_agent(self, report):
        with self.connection() as connection:
            connection.execute("UPDATE agent_runs SET report = ? WHERE id = ?",
                               (json.dumps(report), report["run_id"]))

    def get_agent(self, run_id):
        with self.connection() as connection:
            row = connection.execute("SELECT report FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            return json.loads(row[0])

    def list_agents(self, simulation_id):
        with self.connection() as connection:
            self.load(connection, simulation_id)
            rows = connection.execute("SELECT report FROM agent_runs WHERE source_id = ? ORDER BY rowid",
                                      (simulation_id,)).fetchall()
            return [json.loads(row[0]) for row in rows]

    def apply_agent(self, run_id, transaction_id):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT transaction_id, result FROM agent_applications WHERE run_id = ?",
                                     (run_id,)).fetchone()
            if row:
                if row[0] != transaction_id:
                    raise LedgerError("This recommendation has already been applied with another transaction ID")
                return json.loads(row[1])
            row = connection.execute("SELECT report FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            report = json.loads(row[0])
            if report["status"] != "completed" or report["recommendation"] is None:
                raise LedgerError("Only completed recommendations can be applied")
            world = self.load(connection, report["simulation_id"])
            if snapshot_hash(world.state) != report["snapshot_sha256"]:
                raise LedgerError("Source world changed since observation; run a new analysis before applying")
            if transaction_id in world.ledger._transactions:
                raise LedgerError("Application transaction ID is already used; choose a new ID")
            recommendation = report["recommendation"]
            strategy = recommendation["strategy"]
            if strategy == "no_intervention":
                receipt = world.ledger.post(transaction_id, [("central_bank:equity", 0)],
                                            {"type": "agent_no_intervention", "run_id": run_id,
                                             "tick": world.state["tick"]})
            else:
                receipt = world.intervene(transaction_id, strategy, recommendation["amount_cents"],
                                           recommendation["bank_id"])
            world.emit("agent_recommendation_applied", "central_bank", transaction_id=transaction_id,
                       details={"run_id": run_id, "strategy": strategy})
            result = {"run_id": run_id, "simulation_id": report["simulation_id"], "strategy": strategy,
                      "transaction_id": transaction_id, "receipt": receipt, "audit": world.audit()}
            connection.execute("UPDATE worlds SET state = ? WHERE id = ?",
                               (json.dumps(world.state), report["simulation_id"]))
            connection.execute("INSERT INTO agent_applications VALUES (?, ?, ?)",
                               (run_id, transaction_id, json.dumps(result)))
            return result
