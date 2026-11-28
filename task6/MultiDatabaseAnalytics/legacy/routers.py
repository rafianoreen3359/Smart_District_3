from django.db import DatabaseError


class LegacyRouter:

    def db_for_read(self, model, **hints):

        if model._meta.app_label == 'legacy':
            return 'legacy'

        return None

    def db_for_write(self, model, **hints):

        if model._meta.app_label == 'legacy':
            raise DatabaseError(
                "Legacy database is read-only!"
            )

        return None

    def allow_migrate(
        self, db, app_label, model_name=None, **hints
    ):

        if db == 'legacy':
            return app_label == 'legacy'

        if app_label == 'legacy':
            return False

        return None