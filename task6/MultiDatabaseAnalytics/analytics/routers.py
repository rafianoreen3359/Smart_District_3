class AnalyticsRouter:

    # Send analytics models to analytics database
    def db_for_read(self, model, **hints):

        if model._meta.app_label == 'analytics':
            return 'analytics'

        return None

    def db_for_write(self, model, **hints):

        if model._meta.app_label == 'analytics':
            return 'analytics'

        return None

    # Control migrations
    def allow_migrate(
        self, db, app_label, model_name=None, **hints
    ):

        if db == 'analytics':
            return app_label == 'analytics'

        if app_label == 'analytics':
            return False

        return None