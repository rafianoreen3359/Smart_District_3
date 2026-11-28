import csv
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from projects.models import Project
from tasks.models import Task

class Command(BaseCommand):
    help = "Export a project report (or all projects) to CSV or JSON"

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, help="Project ID (omit for all)")
        parser.add_argument("--format", choices=["csv", "json"], default="csv")
        parser.add_argument("--output", default="reports")
        parser.add_argument("--include-deleted", action="store_true")

    def handle(self, *a, **o):
        manager = Project.all_objects if o["include_deleted"] else Project.objects
        qs = manager.filter(pk=o["project"]) if o["project"] else manager.all()
        if not qs.exists():
            raise CommandError("No matching projects")
        out = Path(o["output"]); out.mkdir(parents=True, exist_ok=True)

        rows = []
        for p in qs:
            tasks = Task.objects.filter(project=p).select_related("assignee")
            overdue = set(tasks.overdue().values_list("id", flat=True))
            for t in tasks:
                rows.append({"project": p.name, "task_id": t.id, "title": t.title, "status": t.status,
                             "assignee": t.assignee.email if t.assignee else "",
                             "due": t.due_date.isoformat() if t.due_date else "",
                             "overdue": t.id in overdue})
        path = out / f"teamhub_report.{o['format']}"
        if o["format"] == "csv":
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else ["project"])
                w.writeheader(); w.writerows(rows)
        else:
            path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"{len(rows)} rows -> {path}"))