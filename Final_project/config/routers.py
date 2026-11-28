class ActivityRouter:
    app = "activity"
    def db_for_read(self, model, **h):  return "activity" if model._meta.app_label == self.app else None
    def db_for_write(self, model, **h): return "activity" if model._meta.app_label == self.app else None
    def allow_relation(self, a, b, **h):
        return True  # use user_id integers in ActivityLog to avoid cross-db FKs
    def allow_migrate(self, db, app_label, **h):
        return db == "activity" if app_label == self.app else db == "default"