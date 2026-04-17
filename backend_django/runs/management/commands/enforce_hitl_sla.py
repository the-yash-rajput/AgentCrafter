"""
Management command: enforce_hitl_sla

Finds all interrupted runs whose SLA deadline has passed and auto-resolves them
according to their configured timeout_action (auto_approve or auto_fail).

Run via cron every 5 minutes:
    */5 * * * * python manage.py enforce_hitl_sla

For auto_approve: resumes the run with the original LLM response and executes
the graph synchronously (no background thread needed in cron context).

For auto_fail: marks the run as failed with a timeout error message.
"""
import threading

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Auto-resolve HITL runs that have exceeded their SLA deadline."

    def handle(self, *args, **options):
        from config.db import managed_db
        from services.run_service import RunService

        with managed_db() as db:
            service = RunService(db)
            expired_runs = service._get_expired_sla_runs()

        if not expired_runs:
            self.stdout.write("No SLA-expired runs found.")
            return

        self.stdout.write(f"Found {len(expired_runs)} SLA-expired run(s): {[r.id for r in expired_runs]}")

        for run in expired_runs:
            run_id = run.id
            meta = dict(run.interrupt_metadata or {})
            action = meta.get("timeout_action", "auto_approve")

            with managed_db() as db:
                service = RunService(db)
                db_run = service.get_run(run_id)
                new_run = service._auto_resolve_timeout(db_run)

            if new_run is None:
                self.stdout.write(f"  Run {run_id}: auto_failed (SLA expired).")
            else:
                # auto_approve: execute the graph synchronously in this process
                new_run_id = new_run.id
                agent_id = new_run.agent_id
                version_id = new_run.version_id
                session_id = new_run.session_id
                checkpoint_thread_id = new_run.checkpoint_thread_id
                effective_input = new_run._runtime_effective_input
                resumed_from_run_id = new_run._runtime_resumed_from_run_id
                resume_command = getattr(new_run, "_runtime_resume_command", None)

                def _execute(
                    _run_id=new_run_id,
                    _agent_id=agent_id,
                    _version_id=version_id,
                    _session_id=session_id,
                    _checkpoint=checkpoint_thread_id,
                    _input=effective_input,
                    _resumed_from=resumed_from_run_id,
                    _cmd=resume_command,
                ):
                    from config.db import managed_db as bg_managed_db
                    from services.run_service import RunService as BgRunService
                    with bg_managed_db() as bg_db:
                        BgRunService(bg_db).execute_run_background(
                            run_id=_run_id,
                            agent_id=_agent_id,
                            version_id=_version_id,
                            session_id=_session_id,
                            effective_input=_input,
                            conversation_history=[],
                            checkpoint_thread_id=_checkpoint,
                            resumed_from_run_id=_resumed_from,
                            resume_command=_cmd,
                        )

                t = threading.Thread(target=_execute, daemon=False)
                t.start()
                t.join()  # wait for completion in cron context
                self.stdout.write(f"  Run {run_id}: auto_approved → new run {new_run_id} completed.")
