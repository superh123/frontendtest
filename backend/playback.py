"""Persistent controls and atomic scheduling shared by every API worker."""

import json
import logging
import time
from uuid import uuid4

from backend.engine import Economy
from backend.ledger import LedgerError


class PlaybackStore:
    def init_playback_tables(self, connection):
        connection.execute("""CREATE TABLE IF NOT EXISTS playback (
            world_id TEXT PRIMARY KEY, status TEXT NOT NULL, interval_ms INTEGER NOT NULL,
            next_due REAL NOT NULL, error TEXT)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS resets (
            source_id TEXT NOT NULL, request_id TEXT NOT NULL, target_id TEXT NOT NULL,
            PRIMARY KEY(source_id, request_id))""")

    @staticmethod
    def playback_row(connection, simulation_id):
        row = connection.execute(
            "SELECT status, interval_ms, error FROM playback WHERE world_id = ?", (simulation_id,)).fetchone()
        return {"simulation_id": simulation_id, "status": row[0] if row else "paused",
                "interval_ms": row[1] if row else 1000, "error": row[2] if row else None}

    def playback_status(self, simulation_id):
        with self.connection() as connection:
            connection.execute("BEGIN")
            self.load(connection, simulation_id)
            return self.playback_row(connection, simulation_id)

    def world_view(self, simulation_id):
        with self.connection() as connection:
            connection.execute("BEGIN")
            view = self.load(connection, simulation_id).view()
            view["status"] = self.playback_row(connection, simulation_id)["status"]
            return view

    def control_playback(self, simulation_id, status, interval_ms=None, now=None):
        now = time.time() if now is None else now
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.load(connection, simulation_id)
            previous = self.playback_row(connection, simulation_id)
            interval = previous["interval_ms"] if interval_ms is None else interval_ms
            # Repeated identical Play requests do not postpone the next tick.
            if previous["status"] == status and previous["interval_ms"] == interval and previous["error"] is None:
                return previous
            connection.execute("""INSERT INTO playback VALUES (?, ?, ?, ?, NULL)
                ON CONFLICT(world_id) DO UPDATE SET status=excluded.status,
                interval_ms=excluded.interval_ms, next_due=excluded.next_due, error=NULL""",
                               (simulation_id, status, interval, now + interval / 1000))
            return self.playback_row(connection, simulation_id)

    def step_paused(self, simulation_id, ticks):
        def operation(world):
            # mutate holds the write lock, so Play cannot race this check.
            with self.connection() as connection:
                if self.playback_row(connection, simulation_id)["status"] == "running":
                    raise LedgerError("Pause the world before stepping manually")
            world.step(ticks)
            return world.view()
        return self.mutate(simulation_id, operation)

    def advance_due(self, now=None):
        now = time.time() if now is None else now
        with self.connection() as connection:
            rows = connection.execute("""SELECT world_id FROM playback
                WHERE status = 'running' AND next_due <= ? ORDER BY next_due LIMIT 10""", (now,)).fetchall()
        advanced = 0
        for (simulation_id,) in rows:
            try:
                with self.connection() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    row = connection.execute("""SELECT interval_ms FROM playback
                        WHERE world_id = ? AND status = 'running' AND next_due <= ?""",
                                             (simulation_id, now)).fetchone()
                    if row is None:
                        continue
                    world = self.load(connection, simulation_id)
                    world.step()
                    world.audit()
                    connection.execute("UPDATE worlds SET state = ? WHERE id = ?",
                                       (json.dumps(world.state), simulation_id))
                    connection.execute("UPDATE playback SET next_due = ? WHERE world_id = ?",
                                       (now + row[0] / 1000, simulation_id))
                    advanced += 1
            except Exception:
                # The failed tick rolled back. Never leave a broken world spinning.
                logging.getLogger(__name__).exception("Automatic tick failed for %s", simulation_id)
                with self.connection() as connection:
                    connection.execute("""UPDATE playback SET status = 'paused', error = ?
                        WHERE world_id = ? AND status = 'running' AND next_due <= ?""",
                        ("Automatic tick failed and was rolled back; inspect the world before resuming",
                         simulation_id, now))
        return advanced

    def reset_world(self, simulation_id, request_id):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            source = self.load(connection, simulation_id)
            previous = connection.execute("SELECT target_id FROM resets WHERE source_id = ? AND request_id = ?",
                                          (simulation_id, request_id)).fetchone()
            if previous:
                return {"source_simulation_id": simulation_id, "simulation_id": previous[0]}
            fresh = Economy.create(f"world_{uuid4().hex[:16]}", **source.state["config"])
            fresh.audit()
            connection.execute("INSERT INTO worlds VALUES (?, ?)",
                               (fresh.state["simulation_id"], json.dumps(fresh.state)))
            connection.execute("UPDATE playback SET status = 'paused', error = NULL WHERE world_id = ?",
                               (simulation_id,))
            connection.execute("INSERT INTO resets VALUES (?, ?, ?)",
                               (simulation_id, request_id, fresh.state["simulation_id"]))
            return {"source_simulation_id": simulation_id, "simulation_id": fresh.state["simulation_id"]}
